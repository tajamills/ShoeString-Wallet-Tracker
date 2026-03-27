"""
Staged Proceeds Acquisition Application Service

Implements controlled, staged application of proceeds acquisitions with:
- Filtering by asset, date range, valuation status, confidence threshold
- Automatic validation after each batch
- Delta metrics (orphan disposals, validation status, can_export before/after)
- Safety blocks for low-confidence or wide-window approximates
- Full rollback capability by batch_id

Usage:
1. Preview candidates with filters
2. Apply exact-valuation candidates first
3. Review validation delta
4. Optionally apply approximate candidates with explicit override
"""

import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from enum import Enum

from constrained_proceeds_service import ConstrainedProceedsService, CandidateFix

logger = logging.getLogger(__name__)


class ValuationFilter(Enum):
    """Valuation status filter options"""
    EXACT_ONLY = "exact_only"           # Only exact price matches
    STABLECOIN_ONLY = "stablecoin_only"  # Only stablecoin disposals
    HIGH_CONFIDENCE = "high_confidence"   # Exact + high-confidence approximate (>=0.8)
    ALL_ELIGIBLE = "all_eligible"         # All eligible (exact + stablecoin + approximate >=0.7)


@dataclass
class StagedApplicationFilters:
    """Filters for staged application"""
    assets: Optional[List[str]] = None           # Filter by asset(s)
    date_from: Optional[str] = None              # Filter by date range start (YYYY-MM-DD)
    date_to: Optional[str] = None                # Filter by date range end (YYYY-MM-DD)
    valuation_filter: ValuationFilter = ValuationFilter.EXACT_ONLY
    min_confidence: float = 0.7                  # Minimum confidence threshold
    max_time_delta_hours: Optional[float] = None  # Max time delta for approximate matches
    exclude_wide_window: bool = True             # Block wide-window approximates (>12h)
    
    def to_dict(self) -> Dict:
        return {
            "assets": self.assets,
            "date_from": self.date_from,
            "date_to": self.date_to,
            "valuation_filter": self.valuation_filter.value,
            "min_confidence": self.min_confidence,
            "max_time_delta_hours": self.max_time_delta_hours,
            "exclude_wide_window": self.exclude_wide_window
        }


@dataclass
class ValidationDelta:
    """Delta metrics from before/after validation"""
    orphan_disposals_before: int = 0
    orphan_disposals_after: int = 0
    orphan_disposals_delta: int = 0
    
    validation_status_before: str = "unknown"
    validation_status_after: str = "unknown"
    
    can_export_before: bool = False
    can_export_after: bool = False
    
    blocking_issues_before: int = 0
    blocking_issues_after: int = 0
    blocking_issues_delta: int = 0
    
    new_warnings: List[str] = field(default_factory=list)
    new_errors: List[str] = field(default_factory=list)
    resolved_issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "orphan_disposals": {
                "before": self.orphan_disposals_before,
                "after": self.orphan_disposals_after,
                "delta": self.orphan_disposals_delta
            },
            "validation_status": {
                "before": self.validation_status_before,
                "after": self.validation_status_after
            },
            "can_export": {
                "before": self.can_export_before,
                "after": self.can_export_after
            },
            "blocking_issues": {
                "before": self.blocking_issues_before,
                "after": self.blocking_issues_after,
                "delta": self.blocking_issues_delta
            },
            "new_warnings": self.new_warnings,
            "new_errors": self.new_errors,
            "resolved_issues": self.resolved_issues
        }


@dataclass
class StagedApplicationResult:
    """Result of a staged application batch"""
    batch_id: str
    filters_applied: Dict
    candidates_matched: int = 0
    candidates_applied: int = 0
    candidates_blocked: int = 0
    blocked_reasons: Dict[str, int] = field(default_factory=dict)
    total_value: float = 0.0
    validation_delta: Optional[ValidationDelta] = None
    applied_records: List[Dict] = field(default_factory=list)
    blocked_records: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "batch_id": self.batch_id,
            "filters_applied": self.filters_applied,
            "candidates_matched": self.candidates_matched,
            "candidates_applied": self.candidates_applied,
            "candidates_blocked": self.candidates_blocked,
            "blocked_reasons": self.blocked_reasons,
            "total_value": round(self.total_value, 2),
            "validation_delta": self.validation_delta.to_dict() if self.validation_delta else None,
            "applied_records": self.applied_records,
            "blocked_records": self.blocked_records
        }


class StagedProceedsService:
    """
    Service for staged, controlled application of proceeds acquisitions.
    
    Safety Features:
    - Exact-valuation candidates applied first by default
    - Low-confidence approximates blocked unless explicitly overridden
    - Wide-window approximates (>12h time delta) blocked by default
    - Automatic validation after each batch with delta reporting
    - Full rollback by batch_id
    """
    
    # Safety thresholds
    HIGH_CONFIDENCE_THRESHOLD = 0.8
    DEFAULT_MIN_CONFIDENCE = 0.7
    WIDE_WINDOW_HOURS = 12.0
    
    def __init__(self, db):
        self.db = db
        self.proceeds_service = ConstrainedProceedsService(db)
    
    async def preview_staged(
        self,
        user_id: str,
        filters: Optional[StagedApplicationFilters] = None
    ) -> Dict[str, Any]:
        """
        Preview candidates with filtering applied.
        
        Returns candidates grouped by valuation quality for staged application.
        """
        if filters is None:
            filters = StagedApplicationFilters()
        
        # Get all candidates from base service
        summary = await self.proceeds_service.preview_candidates(user_id)
        
        # Get disposal details for filtering (we need backfill info)
        disposal_map = await self._get_disposal_backfill_info(user_id)
        
        # Filter and categorize candidates
        exact_candidates = []
        stablecoin_candidates = []
        high_confidence_candidates = []
        low_confidence_candidates = []
        blocked_candidates = []
        
        for candidate in summary.candidates:
            tx_id = candidate.source_disposal_tx_id
            backfill_info = disposal_map.get(tx_id, {})
            
            # Apply filters
            if not self._passes_filters(candidate, backfill_info, filters):
                continue
            
            # Categorize by valuation quality
            valuation_status = backfill_info.get("valuation_status", "unknown")
            confidence = backfill_info.get("confidence", candidate.confidence)
            time_delta = backfill_info.get("time_delta_hours", 0)
            
            # Check safety blocks
            block_reason = self._check_safety_blocks(
                valuation_status, confidence, time_delta, filters
            )
            
            if block_reason:
                blocked_candidates.append({
                    "candidate": candidate.to_dict(),
                    "block_reason": block_reason,
                    "valuation_status": valuation_status,
                    "confidence": confidence,
                    "time_delta_hours": time_delta
                })
                continue
            
            # Categorize eligible candidates
            if valuation_status == "stablecoin":
                stablecoin_candidates.append(candidate)
            elif valuation_status == "exact":
                exact_candidates.append(candidate)
            elif confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
                high_confidence_candidates.append(candidate)
            else:
                low_confidence_candidates.append(candidate)
        
        return {
            "filters_applied": filters.to_dict(),
            "summary": {
                "total_candidates": len(summary.candidates),
                "filtered_candidates": len(exact_candidates) + len(stablecoin_candidates) + 
                                       len(high_confidence_candidates) + len(low_confidence_candidates),
                "blocked_by_safety": len(blocked_candidates)
            },
            "by_valuation_quality": {
                "exact": {
                    "count": len(exact_candidates),
                    "total_value": sum(c.proceeds_amount for c in exact_candidates),
                    "recommended_action": "apply_first",
                    "candidates": [c.to_dict() for c in exact_candidates[:20]]
                },
                "stablecoin": {
                    "count": len(stablecoin_candidates),
                    "total_value": sum(c.proceeds_amount for c in stablecoin_candidates),
                    "recommended_action": "apply_first",
                    "candidates": [c.to_dict() for c in stablecoin_candidates[:20]]
                },
                "high_confidence_approximate": {
                    "count": len(high_confidence_candidates),
                    "total_value": sum(c.proceeds_amount for c in high_confidence_candidates),
                    "recommended_action": "review_then_apply",
                    "candidates": [c.to_dict() for c in high_confidence_candidates[:20]]
                },
                "low_confidence_approximate": {
                    "count": len(low_confidence_candidates),
                    "total_value": sum(c.proceeds_amount for c in low_confidence_candidates),
                    "recommended_action": "manual_review_required",
                    "candidates": [c.to_dict() for c in low_confidence_candidates[:20]]
                }
            },
            "blocked": {
                "count": len(blocked_candidates),
                "records": blocked_candidates[:20]
            }
        }
    
    async def apply_staged(
        self,
        user_id: str,
        filters: Optional[StagedApplicationFilters] = None,
        dry_run: bool = True,
        force_override: bool = False  # Override safety blocks
    ) -> StagedApplicationResult:
        """
        Apply proceeds acquisitions with filters and safety controls.
        
        Args:
            user_id: User ID
            filters: Filtering criteria
            dry_run: If True, preview only
            force_override: If True, bypass safety blocks (requires explicit flag)
        
        Returns:
            StagedApplicationResult with validation delta
        """
        if filters is None:
            filters = StagedApplicationFilters()
        
        batch_id = str(uuid.uuid4()) if not dry_run else None
        
        result = StagedApplicationResult(
            batch_id=batch_id or "dry_run",
            filters_applied=filters.to_dict()
        )
        
        # Get validation state BEFORE
        validation_before = await self._get_validation_state(user_id)
        
        # Get all candidates
        summary = await self.proceeds_service.preview_candidates(user_id)
        disposal_map = await self._get_disposal_backfill_info(user_id)
        
        # Filter candidates
        eligible_candidates = []
        for candidate in summary.candidates:
            tx_id = candidate.source_disposal_tx_id
            backfill_info = disposal_map.get(tx_id, {})
            
            # Apply filters
            if not self._passes_filters(candidate, backfill_info, filters):
                continue
            
            result.candidates_matched += 1
            
            # Check safety blocks
            valuation_status = backfill_info.get("valuation_status", "unknown")
            confidence = backfill_info.get("confidence", candidate.confidence)
            time_delta = backfill_info.get("time_delta_hours", 0)
            
            block_reason = self._check_safety_blocks(
                valuation_status, confidence, time_delta, filters
            )
            
            if block_reason and not force_override:
                result.candidates_blocked += 1
                result.blocked_reasons[block_reason] = result.blocked_reasons.get(block_reason, 0) + 1
                result.blocked_records.append({
                    "tx_id": tx_id,
                    "asset": candidate.source_asset,
                    "block_reason": block_reason
                })
                continue
            
            eligible_candidates.append(candidate)
            result.total_value += candidate.proceeds_amount
        
        if dry_run:
            result.candidates_applied = len(eligible_candidates)
            result.applied_records = [c.to_dict() for c in eligible_candidates[:50]]
            return result
        
        # Actually apply the candidates
        if eligible_candidates:
            tx_ids = [c.source_disposal_tx_id for c in eligible_candidates]
            apply_result = await self._apply_with_batch_id(
                user_id, tx_ids, batch_id
            )
            result.candidates_applied = apply_result["created_count"]
            result.applied_records = apply_result.get("created_records", [])[:50]
        
        # Get validation state AFTER
        validation_after = await self._get_validation_state(user_id)
        
        # Calculate delta
        result.validation_delta = self._calculate_validation_delta(
            validation_before, validation_after
        )
        
        return result
    
    async def apply_exact_only(
        self,
        user_id: str,
        assets: Optional[List[str]] = None,
        dry_run: bool = True
    ) -> StagedApplicationResult:
        """
        Convenience method: Apply only exact-valuation candidates.
        
        This is the safest application mode with highest confidence.
        """
        filters = StagedApplicationFilters(
            assets=assets,
            valuation_filter=ValuationFilter.EXACT_ONLY,
            min_confidence=0.9,
            exclude_wide_window=True
        )
        return await self.apply_staged(user_id, filters, dry_run)
    
    async def apply_stablecoins_only(
        self,
        user_id: str,
        dry_run: bool = True
    ) -> StagedApplicationResult:
        """
        Convenience method: Apply only stablecoin candidates.
        
        Stablecoins have 1:1 USD peg, so confidence is always 1.0.
        """
        filters = StagedApplicationFilters(
            valuation_filter=ValuationFilter.STABLECOIN_ONLY,
            min_confidence=1.0
        )
        return await self.apply_staged(user_id, filters, dry_run)
    
    async def apply_high_confidence(
        self,
        user_id: str,
        assets: Optional[List[str]] = None,
        dry_run: bool = True
    ) -> StagedApplicationResult:
        """
        Convenience method: Apply exact + high-confidence approximate.
        """
        filters = StagedApplicationFilters(
            assets=assets,
            valuation_filter=ValuationFilter.HIGH_CONFIDENCE,
            min_confidence=0.8,
            exclude_wide_window=True
        )
        return await self.apply_staged(user_id, filters, dry_run)
    
    async def get_application_stages(self, user_id: str) -> Dict[str, Any]:
        """
        Get recommended application stages for the user.
        
        Returns a plan for staged application with estimated impact.
        """
        preview = await self.preview_staged(user_id, StagedApplicationFilters(
            valuation_filter=ValuationFilter.ALL_ELIGIBLE
        ))
        
        stages = []
        
        # Stage 1: Exact valuations
        exact_count = preview["by_valuation_quality"]["exact"]["count"]
        stablecoin_count = preview["by_valuation_quality"]["stablecoin"]["count"]
        if exact_count > 0 or stablecoin_count > 0:
            stages.append({
                "stage": 1,
                "name": "Exact + Stablecoin Valuations",
                "candidates": exact_count + stablecoin_count,
                "total_value": (
                    preview["by_valuation_quality"]["exact"]["total_value"] +
                    preview["by_valuation_quality"]["stablecoin"]["total_value"]
                ),
                "risk_level": "low",
                "recommended": True,
                "action": "apply_exact_only"
            })
        
        # Stage 2: High-confidence approximate
        high_conf_count = preview["by_valuation_quality"]["high_confidence_approximate"]["count"]
        if high_conf_count > 0:
            stages.append({
                "stage": 2,
                "name": "High-Confidence Approximate",
                "candidates": high_conf_count,
                "total_value": preview["by_valuation_quality"]["high_confidence_approximate"]["total_value"],
                "risk_level": "medium",
                "recommended": True,
                "action": "apply_high_confidence"
            })
        
        # Stage 3: Low-confidence (requires manual review)
        low_conf_count = preview["by_valuation_quality"]["low_confidence_approximate"]["count"]
        if low_conf_count > 0:
            stages.append({
                "stage": 3,
                "name": "Low-Confidence Approximate",
                "candidates": low_conf_count,
                "total_value": preview["by_valuation_quality"]["low_confidence_approximate"]["total_value"],
                "risk_level": "high",
                "recommended": False,
                "action": "manual_review_required",
                "warning": "Requires force_override=True and manual review"
            })
        
        return {
            "total_candidates": preview["summary"]["total_candidates"],
            "stages": stages,
            "blocked_by_safety": preview["blocked"]["count"]
        }
    
    # === PRIVATE METHODS ===
    
    async def _get_disposal_backfill_info(self, user_id: str) -> Dict[str, Dict]:
        """Get backfill info for all disposals"""
        disposals = await self.db.exchange_transactions.find({
            "user_id": user_id,
            "tx_type": "sell"
        }).to_list(100000)
        
        return {
            d.get("tx_id"): d.get("price_backfill", {})
            for d in disposals
        }
    
    def _passes_filters(
        self,
        candidate: CandidateFix,
        backfill_info: Dict,
        filters: StagedApplicationFilters
    ) -> bool:
        """Check if candidate passes all filters"""
        # Asset filter
        if filters.assets:
            if candidate.source_asset not in filters.assets:
                return False
        
        # Date range filter
        if filters.date_from or filters.date_to:
            try:
                # Parse candidate timestamp
                ts_str = candidate.disposal_timestamp
                for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        ts = datetime.strptime(ts_str[:19], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return False
                
                if filters.date_from:
                    date_from = datetime.strptime(filters.date_from, "%Y-%m-%d")
                    if ts < date_from:
                        return False
                
                if filters.date_to:
                    date_to = datetime.strptime(filters.date_to, "%Y-%m-%d")
                    if ts > date_to:
                        return False
            except Exception:
                return False
        
        # Valuation status filter
        valuation_status = backfill_info.get("valuation_status", "unknown")
        if filters.valuation_filter == ValuationFilter.EXACT_ONLY:
            if valuation_status not in ["exact", "stablecoin"]:
                return False
        elif filters.valuation_filter == ValuationFilter.STABLECOIN_ONLY:
            if valuation_status != "stablecoin":
                return False
        elif filters.valuation_filter == ValuationFilter.HIGH_CONFIDENCE:
            confidence = backfill_info.get("confidence", candidate.confidence)
            if valuation_status not in ["exact", "stablecoin"] and confidence < 0.8:
                return False
        
        # Confidence threshold
        confidence = backfill_info.get("confidence", candidate.confidence)
        if confidence < filters.min_confidence:
            return False
        
        # Max time delta
        if filters.max_time_delta_hours is not None:
            time_delta = backfill_info.get("time_delta_hours", 0)
            if time_delta and time_delta > filters.max_time_delta_hours:
                return False
        
        return True
    
    def _check_safety_blocks(
        self,
        valuation_status: str,
        confidence: float,
        time_delta: float,
        filters: StagedApplicationFilters
    ) -> Optional[str]:
        """Check if candidate should be blocked by safety controls"""
        # Block low-confidence
        if confidence < filters.min_confidence:
            return f"low_confidence_{confidence:.2f}"
        
        # Block wide-window approximates
        if filters.exclude_wide_window:
            if valuation_status == "approximate" and time_delta > self.WIDE_WINDOW_HOURS:
                return f"wide_window_{time_delta:.1f}h"
        
        # Block unavailable valuations
        if valuation_status == "unavailable":
            return "unavailable_valuation"
        
        return None
    
    async def _get_validation_state(self, user_id: str) -> Dict[str, Any]:
        """Get current validation state for delta calculation"""
        try:
            # Import here to avoid circular imports
            from beta_validation_harness import BetaValidationHarness
            harness = BetaValidationHarness(self.db)
            report = await harness.validate_user_account(user_id)
            
            # Count orphan disposals from issues
            orphan_count = 0
            blocking_issues = 0
            for issue in report.get("issues", []):
                if "orphan" in issue.get("type", "").lower():
                    orphan_count += 1
                if issue.get("severity") in ["critical", "high"]:
                    blocking_issues += 1
            
            return {
                "validation_status": report.get("validation_status", "unknown"),
                "can_export": report.get("can_export", False),
                "orphan_disposals": orphan_count,
                "blocking_issues": blocking_issues,
                "issues": report.get("issues", [])
            }
        except Exception as e:
            logger.warning(f"Could not get validation state: {e}")
            # Fallback to simple check
            return await self._get_simple_validation_state(user_id)
    
    async def _get_simple_validation_state(self, user_id: str) -> Dict[str, Any]:
        """Simple validation state fallback"""
        # Count orphan disposals by checking disposals without matching acquisitions
        pipeline = [
            {"$match": {"user_id": user_id, "tx_type": "sell"}},
            {"$group": {
                "_id": "$asset",
                "disposed": {"$sum": {"$ifNull": ["$quantity", "$amount"]}}
            }}
        ]
        disposed_by_asset = await self.db.exchange_transactions.aggregate(pipeline).to_list(1000)
        
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "tx_type": {"$in": ["buy", "receive", "reward", "staking", "airdrop", 
                                    "derived_proceeds_acquisition", "proceeds_acquisition"]}
            }},
            {"$group": {
                "_id": "$asset",
                "acquired": {"$sum": {"$ifNull": ["$quantity", "$amount"]}}
            }}
        ]
        acquired_by_asset = await self.db.exchange_transactions.aggregate(pipeline).to_list(1000)
        
        acquired_map = {a["_id"]: a["acquired"] for a in acquired_by_asset}
        
        orphan_count = 0
        for d in disposed_by_asset:
            asset = d["_id"]
            disposed = d["disposed"]
            acquired = acquired_map.get(asset, 0)
            if disposed > acquired:
                orphan_count += 1
        
        return {
            "validation_status": "needs_review" if orphan_count > 0 else "valid",
            "can_export": orphan_count == 0,
            "orphan_disposals": orphan_count,
            "blocking_issues": orphan_count,
            "issues": []
        }
    
    def _calculate_validation_delta(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any]
    ) -> ValidationDelta:
        """Calculate delta between validation states"""
        delta = ValidationDelta(
            orphan_disposals_before=before.get("orphan_disposals", 0),
            orphan_disposals_after=after.get("orphan_disposals", 0),
            validation_status_before=before.get("validation_status", "unknown"),
            validation_status_after=after.get("validation_status", "unknown"),
            can_export_before=before.get("can_export", False),
            can_export_after=after.get("can_export", False),
            blocking_issues_before=before.get("blocking_issues", 0),
            blocking_issues_after=after.get("blocking_issues", 0)
        )
        
        delta.orphan_disposals_delta = delta.orphan_disposals_after - delta.orphan_disposals_before
        delta.blocking_issues_delta = delta.blocking_issues_after - delta.blocking_issues_before
        
        # Find new and resolved issues
        before_issues = {i.get("id", str(i)): i for i in before.get("issues", [])}
        after_issues = {i.get("id", str(i)): i for i in after.get("issues", [])}
        
        for issue_id, issue in after_issues.items():
            if issue_id not in before_issues:
                severity = issue.get("severity", "low")
                msg = issue.get("message", str(issue))[:100]
                if severity in ["critical", "high"]:
                    delta.new_errors.append(msg)
                else:
                    delta.new_warnings.append(msg)
        
        for issue_id, issue in before_issues.items():
            if issue_id not in after_issues:
                msg = issue.get("message", str(issue))[:100]
                delta.resolved_issues.append(msg)
        
        return delta
    
    async def _apply_with_batch_id(
        self,
        user_id: str,
        tx_ids: List[str],
        batch_id: str
    ) -> Dict[str, Any]:
        """Apply proceeds acquisitions with a specific batch_id"""
        # Get candidates for these tx_ids
        summary = await self.proceeds_service.preview_candidates(user_id)
        candidates = [c for c in summary.candidates if c.source_disposal_tx_id in tx_ids]
        
        if not candidates:
            return {"created_count": 0, "created_records": []}
        
        created_records = []
        audit_entries = []
        
        for candidate in candidates:
            record = {
                "user_id": user_id,
                "tx_id": f"derived_proceeds_{candidate.source_disposal_tx_id}",
                "exchange": candidate.exchange,
                "tx_type": "derived_proceeds_acquisition",
                "asset": candidate.proceeds_asset,
                "quantity": candidate.proceeds_amount,
                "amount": candidate.proceeds_amount,
                "price_usd": 1.0,
                "total_usd": candidate.proceeds_amount,
                "timestamp": candidate.disposal_timestamp,
                "chain_status": "verified_proceeds",
                "source_disposal": {
                    "tx_id": candidate.source_disposal_tx_id,
                    "asset": candidate.source_asset,
                    "quantity": candidate.source_quantity,
                    "proceeds": candidate.proceeds_amount
                },
                "price_source": candidate.price_source,
                "derived_record": True,
                "rollback_batch_id": batch_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "staged_proceeds_service",
                "notes": f"Staged application: {candidate.proceeds_amount:.2f} {candidate.proceeds_asset} from {candidate.source_asset}"
            }
            created_records.append(record)
            
            audit_entries.append({
                "entry_id": str(uuid.uuid4()),
                "user_id": user_id,
                "action": "staged_proceeds_acquisition",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "rollback_batch_id": batch_id,
                "details": {
                    "derived_tx_id": record["tx_id"],
                    "source_disposal_tx_id": candidate.source_disposal_tx_id,
                    "source_asset": candidate.source_asset,
                    "proceeds_asset": candidate.proceeds_asset,
                    "proceeds_amount": candidate.proceeds_amount,
                    "confidence": candidate.confidence
                }
            })
        
        if created_records:
            await self.db.exchange_transactions.insert_many(created_records)
        
        if audit_entries:
            await self.db.tax_audit_trail.insert_many(audit_entries)
        
        return {
            "created_count": len(created_records),
            "created_records": [
                {
                    "tx_id": r["tx_id"],
                    "asset": r["asset"],
                    "amount": r["quantity"],
                    "source": r["source_disposal"]["tx_id"]
                }
                for r in created_records
            ]
        }
