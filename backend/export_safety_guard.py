"""
Export Safety Guard

Prevents Form 8949 export unless validation passes.
Re-runs validation before every export attempt.

Requirements:
- validation_status == "valid"
- can_export == true

If not, export is blocked with structured error listing blocking issues.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class ExportBlockedError:
    """Structured error when export is blocked"""
    blocked: bool = True
    validation_status: str = "unknown"
    can_export: bool = False
    blocking_issues_count: int = 0
    blocking_issues: List[Dict] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    last_validation_timestamp: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PreExportSummary:
    """Summary metadata returned before export"""
    validation_status: str  # valid / invalid / needs_review
    can_export: bool
    proceeds_derived_count: int
    unresolved_review_count: int
    blocking_issues_count: int
    last_recompute_timestamp: str
    
    # Additional details
    total_disposals: int = 0
    total_proceeds: float = 0.0
    total_cost_basis: float = 0.0
    total_gain_loss: float = 0.0
    short_term_gain: float = 0.0
    long_term_gain: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ExportSafetyGuard:
    """
    Guard that ensures Form 8949 export only proceeds when validation passes.
    
    Re-runs validation before every export attempt.
    Blocks export with detailed error if validation fails.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def get_pre_export_summary(self, user_id: str, tax_year: int = None) -> PreExportSummary:
        """
        Get pre-export summary metadata.
        
        This MUST be called before export to ensure latest state.
        """
        # Get last recompute timestamp
        recompute_state = await self.db.recompute_state.find_one(
            {"user_id": user_id},
            {"_id": 0}
        )
        last_recompute = recompute_state.get("timestamp") if recompute_state else None
        
        # Get validation state
        validation = await self._run_validation(user_id)
        
        # Count derived proceeds
        proceeds_count = await self.db.exchange_transactions.count_documents({
            "user_id": user_id,
            "tx_type": {"$in": ["derived_proceeds_acquisition", "proceeds_acquisition"]}
        })
        
        # Count unresolved reviews
        unresolved_count = await self.db.review_queue.count_documents({
            "user_id": user_id,
            "review_status": "pending"
        })
        
        # Count blocking issues
        blocking_issues = [
            i for i in validation.get("issues", [])
            if i.get("severity") in ["critical", "high"]
        ]
        
        # Get disposal stats
        disposal_stats = await self._get_disposal_stats(user_id, tax_year)
        
        return PreExportSummary(
            validation_status=validation.get("validation_status", "unknown"),
            can_export=validation.get("can_export", False),
            proceeds_derived_count=proceeds_count,
            unresolved_review_count=unresolved_count,
            blocking_issues_count=len(blocking_issues),
            last_recompute_timestamp=last_recompute or "never",
            total_disposals=disposal_stats.get("count", 0),
            total_proceeds=disposal_stats.get("proceeds", 0.0),
            total_cost_basis=disposal_stats.get("cost_basis", 0.0),
            total_gain_loss=disposal_stats.get("gain_loss", 0.0),
            short_term_gain=disposal_stats.get("short_term", 0.0),
            long_term_gain=disposal_stats.get("long_term", 0.0)
        )
    
    async def check_export_allowed(
        self,
        user_id: str,
        tax_year: int = None
    ) -> Tuple[bool, Optional[ExportBlockedError]]:
        """
        Check if export is allowed.
        
        Re-runs validation and checks:
        - validation_status == "valid"
        - can_export == true
        
        Returns (allowed, error) tuple.
        """
        # Re-run validation (always fresh)
        validation = await self._run_validation(user_id)
        
        validation_status = validation.get("validation_status", "unknown")
        can_export = validation.get("can_export", False)
        
        # Check if export is allowed
        if validation_status == "valid" and can_export:
            return True, None
        
        # Export blocked - build error response
        blocking_issues = [
            i for i in validation.get("issues", [])
            if i.get("severity") in ["critical", "high"]
        ]
        
        recommendations = self._generate_recommendations(blocking_issues, validation)
        
        error = ExportBlockedError(
            blocked=True,
            validation_status=validation_status,
            can_export=can_export,
            blocking_issues_count=len(blocking_issues),
            blocking_issues=blocking_issues[:20],  # Limit to 20
            recommendations=recommendations,
            last_validation_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        return False, error
    
    async def safe_export(
        self,
        user_id: str,
        tax_year: int = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Safely export Form 8949 data.
        
        Always re-runs validation first.
        Blocks export if validation fails (unless force=True).
        """
        # Check if export is allowed
        allowed, error = await self.check_export_allowed(user_id, tax_year)
        
        if not allowed and not force:
            return {
                "success": False,
                "blocked": True,
                "error": error.to_dict() if error else {"message": "Export not allowed"}
            }
        
        # Get summary for metadata
        summary = await self.get_pre_export_summary(user_id, tax_year)
        
        # Generate export data
        export_data = await self._generate_export_data(user_id, tax_year)
        
        # Log export
        await self._log_export(user_id, summary, force)
        
        return {
            "success": True,
            "blocked": False,
            "forced": force,
            "summary": summary.to_dict(),
            "data": export_data
        }
    
    # === PRIVATE METHODS ===
    
    async def _run_validation(self, user_id: str) -> Dict:
        """Run fresh validation"""
        try:
            from beta_validation_harness import BetaValidationHarness
            harness = BetaValidationHarness(self.db)
            return await harness.validate_user_account(user_id)
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return {
                "validation_status": "error",
                "can_export": False,
                "issues": [{"severity": "critical", "message": str(e)}]
            }
    
    async def _get_disposal_stats(self, user_id: str, tax_year: int = None) -> Dict:
        """Get disposal statistics"""
        query = {"user_id": user_id}
        
        # Filter by tax year if specified
        if tax_year:
            query["disposal_date"] = {
                "$gte": f"{tax_year}-01-01",
                "$lt": f"{tax_year + 1}-01-01"
            }
        
        disposals = await self.db.tax_disposals.find(query).to_list(100000)
        
        total_proceeds = sum(d.get("proceeds", 0) or 0 for d in disposals)
        total_cost_basis = sum(d.get("cost_basis", 0) or 0 for d in disposals)
        total_gain_loss = sum(d.get("gain_loss", 0) or 0 for d in disposals)
        
        short_term = sum(
            d.get("gain_loss", 0) or 0 
            for d in disposals 
            if d.get("term") == "short"
        )
        long_term = sum(
            d.get("gain_loss", 0) or 0 
            for d in disposals 
            if d.get("term") == "long"
        )
        
        return {
            "count": len(disposals),
            "proceeds": round(total_proceeds, 2),
            "cost_basis": round(total_cost_basis, 2),
            "gain_loss": round(total_gain_loss, 2),
            "short_term": round(short_term, 2),
            "long_term": round(long_term, 2)
        }
    
    def _generate_recommendations(
        self,
        blocking_issues: List[Dict],
        validation: Dict
    ) -> List[str]:
        """Generate recommendations based on blocking issues"""
        recommendations = []
        
        # Check for common issues
        issue_types = [i.get("type", "") for i in blocking_issues]
        
        if "orphan_disposal" in str(issue_types).lower():
            recommendations.append(
                "Run price backfill and staged proceeds application to resolve orphan disposals"
            )
        
        if "unresolved_review" in str(issue_types).lower():
            recommendations.append(
                "Complete wallet ownership review in the Chain of Custody panel"
            )
        
        if "missing_cost_basis" in str(issue_types).lower():
            recommendations.append(
                "Import missing acquisition transactions or create manual tax lots"
            )
        
        if "invalid_linkage" in str(issue_types).lower():
            recommendations.append(
                "Review and fix wallet linkages in the Chain of Custody panel"
            )
        
        if not recommendations:
            recommendations.append(
                "Review blocking issues above and resolve them before exporting"
            )
        
        return recommendations
    
    async def _generate_export_data(self, user_id: str, tax_year: int = None) -> List[Dict]:
        """Generate Form 8949 export data"""
        query = {"user_id": user_id}
        
        if tax_year:
            query["disposal_date"] = {
                "$gte": f"{tax_year}-01-01",
                "$lt": f"{tax_year + 1}-01-01"
            }
        
        disposals = await self.db.tax_disposals.find(query).to_list(100000)
        
        export_rows = []
        for d in disposals:
            export_rows.append({
                "Description": f"{d.get('quantity', 0):.8f} {d.get('asset', 'UNKNOWN')}",
                "Date Acquired": d.get("acquisition_date", "VARIOUS"),
                "Date Sold": d.get("disposal_date", ""),
                "Proceeds": round(d.get("proceeds", 0) or 0, 2),
                "Cost Basis": round(d.get("cost_basis", 0) or 0, 2),
                "Gain or Loss": round(d.get("gain_loss", 0) or 0, 2),
                "Term": d.get("term", "short").upper()
            })
        
        return export_rows
    
    async def _log_export(self, user_id: str, summary: PreExportSummary, force: bool):
        """Log export in audit trail"""
        await self.db.tax_audit_trail.insert_one({
            "entry_id": str(__import__('uuid').uuid4()),
            "user_id": user_id,
            "action": "form_8949_export",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "forced": force,
                "summary": summary.to_dict()
            }
        })
