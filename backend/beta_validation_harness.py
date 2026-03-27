"""
Beta Account Validation Harness

Runs selected beta user accounts through the full tax pipeline and generates
human-reviewable validation reports before Form 8949 export.

Usage:
    harness = BetaValidationHarness(db)
    report = await harness.validate_account(user_id)
    harness.export_report(report, "/path/to/report.json")
"""

import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timezone
from decimal import Decimal
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import os

logger = logging.getLogger(__name__)


class SeverityLevel(str, Enum):
    """Severity levels for validation issues"""
    CRITICAL = "critical"  # Blocks export
    HIGH = "high"          # Likely incorrect, needs review
    MEDIUM = "medium"      # Potential issue
    LOW = "low"            # Minor concern
    INFO = "info"          # Informational only


class IssueType(str, Enum):
    """Types of validation issues"""
    ORPHAN_DISPOSAL = "orphan_disposal"
    BALANCE_MISMATCH = "balance_mismatch"
    COST_BASIS_INCONSISTENCY = "cost_basis_inconsistency"
    DUPLICATE_DISPOSAL_RISK = "duplicate_disposal_risk"
    UNRESOLVED_CHAIN_BREAK = "unresolved_chain_break"
    UNKNOWN_CLASSIFICATION = "unknown_classification"
    NEGATIVE_BALANCE = "negative_balance"
    MISSING_ACQUISITION = "missing_acquisition"
    INVALID_DATE_ORDER = "invalid_date_order"
    PRICE_DATA_MISSING = "price_data_missing"


@dataclass
class ValidationIssue:
    """A single validation issue found during analysis"""
    issue_type: IssueType
    severity: SeverityLevel
    asset: str
    description: str
    details: Dict[str, Any]
    transaction_ids: List[str] = field(default_factory=list)
    recommendation: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "asset": self.asset,
            "description": self.description,
            "details": self.details,
            "transaction_ids": self.transaction_ids,
            "recommendation": self.recommendation
        }


@dataclass
class ClassificationSummary:
    """Summary of transaction classifications"""
    total_transactions: int = 0
    acquisitions: int = 0
    disposals: int = 0
    internal_transfers: int = 0
    income: int = 0
    unknown: int = 0
    needs_review: int = 0
    by_asset: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class LotReconciliationSummary:
    """Summary of lot tracking and reconciliation"""
    total_lots: int = 0
    fully_disposed_lots: int = 0
    partial_lots: int = 0
    open_lots: int = 0
    total_cost_basis: float = 0.0
    by_asset: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class DisposalSummary:
    """Summary of all disposals"""
    total_disposals: int = 0
    total_proceeds: float = 0.0
    total_cost_basis: float = 0.0
    total_gain_loss: float = 0.0
    short_term_count: int = 0
    long_term_count: int = 0
    short_term_gain_loss: float = 0.0
    long_term_gain_loss: float = 0.0
    by_asset: Dict[str, Dict[str, float]] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class InvariantCheckResult:
    """Result of a single invariant check"""
    check_name: str
    passed: bool
    details: Dict[str, Any]
    affected_assets: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class AccountValidationReport:
    """Complete validation report for a single account"""
    # Metadata (required)
    user_id: str
    user_email: str
    generated_at: str
    tax_year: int
    
    # Status (with defaults for initialization)
    validation_status: str = "pending"  # "valid", "invalid", "needs_review", "pending"
    can_export: bool = False
    export_blocked_reason: Optional[str] = None
    
    # Summaries
    classification_summary: ClassificationSummary = field(default_factory=ClassificationSummary)
    lot_reconciliation: LotReconciliationSummary = field(default_factory=LotReconciliationSummary)
    disposal_summary: DisposalSummary = field(default_factory=DisposalSummary)
    
    # Review items
    unresolved_review_items: List[Dict] = field(default_factory=list)
    
    # Invariant checks
    invariant_checks: List[InvariantCheckResult] = field(default_factory=list)
    invariants_passed: int = 0
    invariants_failed: int = 0
    
    # Issues (highlighted problems)
    issues: List[ValidationIssue] = field(default_factory=list)
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    low_issues: int = 0
    
    # Raw data for deep inspection
    transactions_analyzed: int = 0
    review_queue_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "metadata": {
                "user_id": self.user_id,
                "user_email": self.user_email,
                "generated_at": self.generated_at,
                "tax_year": self.tax_year
            },
            "status": {
                "validation_status": self.validation_status,
                "can_export": self.can_export,
                "export_blocked_reason": self.export_blocked_reason
            },
            "summaries": {
                "classification": self.classification_summary.to_dict(),
                "lot_reconciliation": self.lot_reconciliation.to_dict(),
                "disposals": self.disposal_summary.to_dict()
            },
            "unresolved_review_items": self.unresolved_review_items,
            "invariant_checks": {
                "total": len(self.invariant_checks),
                "passed": self.invariants_passed,
                "failed": self.invariants_failed,
                "results": [c.to_dict() for c in self.invariant_checks]
            },
            "issues": {
                "total": len(self.issues),
                "by_severity": {
                    "critical": self.critical_issues,
                    "high": self.high_issues,
                    "medium": self.medium_issues,
                    "low": self.low_issues
                },
                "details": [i.to_dict() for i in self.issues]
            },
            "statistics": {
                "transactions_analyzed": self.transactions_analyzed,
                "review_queue_count": self.review_queue_count
            }
        }
    
    def to_human_readable(self) -> str:
        """Generate human-readable report text"""
        lines = []
        lines.append("=" * 80)
        lines.append("BETA ACCOUNT VALIDATION REPORT")
        lines.append("=" * 80)
        lines.append("")
        
        # Header
        lines.append(f"User ID: {self.user_id}")
        lines.append(f"Email: {self.user_email}")
        lines.append(f"Tax Year: {self.tax_year}")
        lines.append(f"Generated: {self.generated_at}")
        lines.append("")
        
        # Status Box
        status_icon = "✅" if self.can_export else "❌"
        lines.append("-" * 40)
        lines.append(f"STATUS: {self.validation_status.upper()} {status_icon}")
        lines.append(f"CAN EXPORT FORM 8949: {'YES' if self.can_export else 'NO'}")
        if self.export_blocked_reason:
            lines.append(f"BLOCKED REASON: {self.export_blocked_reason}")
        lines.append("-" * 40)
        lines.append("")
        
        # Classification Summary
        lines.append("TRANSACTION CLASSIFICATION SUMMARY")
        lines.append("-" * 40)
        cs = self.classification_summary
        lines.append(f"  Total Transactions: {cs.total_transactions}")
        lines.append(f"  Acquisitions:       {cs.acquisitions}")
        lines.append(f"  Disposals:          {cs.disposals}")
        lines.append(f"  Internal Transfers: {cs.internal_transfers}")
        lines.append(f"  Income:             {cs.income}")
        lines.append(f"  Unknown:            {cs.unknown} {'⚠️' if cs.unknown > 0 else ''}")
        lines.append(f"  Needs Review:       {cs.needs_review} {'⚠️' if cs.needs_review > 0 else ''}")
        lines.append("")
        
        # Unresolved Review Items
        if self.unresolved_review_items:
            lines.append("⚠️ UNRESOLVED REVIEW ITEMS")
            lines.append("-" * 40)
            for item in self.unresolved_review_items[:10]:  # Show first 10
                lines.append(f"  - TX: {item.get('tx_id', 'N/A')[:20]}...")
                lines.append(f"    Asset: {item.get('asset', 'N/A')}, Amount: {item.get('quantity', 'N/A')}")
                lines.append(f"    Status: {item.get('review_status', 'pending')}")
            if len(self.unresolved_review_items) > 10:
                lines.append(f"  ... and {len(self.unresolved_review_items) - 10} more")
            lines.append("")
        
        # Lot Reconciliation
        lines.append("LOT RECONCILIATION SUMMARY")
        lines.append("-" * 40)
        lr = self.lot_reconciliation
        lines.append(f"  Total Lots:         {lr.total_lots}")
        lines.append(f"  Fully Disposed:     {lr.fully_disposed_lots}")
        lines.append(f"  Partial:            {lr.partial_lots}")
        lines.append(f"  Open (Available):   {lr.open_lots}")
        lines.append(f"  Total Cost Basis:   ${lr.total_cost_basis:,.2f}")
        lines.append("")
        
        if lr.by_asset:
            lines.append("  By Asset:")
            for asset, data in lr.by_asset.items():
                lines.append(f"    {asset}: {data.get('quantity', 0)} units, ${data.get('cost_basis', 0):,.2f} basis")
            lines.append("")
        
        # Disposal Summary
        lines.append("DISPOSAL SUMMARY")
        lines.append("-" * 40)
        ds = self.disposal_summary
        lines.append(f"  Total Disposals:    {ds.total_disposals}")
        lines.append(f"  Total Proceeds:     ${ds.total_proceeds:,.2f}")
        lines.append(f"  Total Cost Basis:   ${ds.total_cost_basis:,.2f}")
        lines.append(f"  Net Gain/Loss:      ${ds.total_gain_loss:,.2f} {'📈' if ds.total_gain_loss >= 0 else '📉'}")
        lines.append("")
        lines.append(f"  Short-Term ({ds.short_term_count}):   ${ds.short_term_gain_loss:,.2f}")
        lines.append(f"  Long-Term ({ds.long_term_count}):    ${ds.long_term_gain_loss:,.2f}")
        lines.append("")
        
        # Invariant Checks
        lines.append("INVARIANT CHECKS")
        lines.append("-" * 40)
        lines.append(f"  Passed: {self.invariants_passed}/{len(self.invariant_checks)}")
        for check in self.invariant_checks:
            icon = "✅" if check.passed else "❌"
            lines.append(f"  {icon} {check.check_name}")
            if not check.passed and check.affected_assets:
                lines.append(f"      Affected: {', '.join(check.affected_assets)}")
        lines.append("")
        
        # Issues (Highlighted Problems)
        if self.issues:
            lines.append("⚠️ HIGHLIGHTED ISSUES")
            lines.append("-" * 40)
            lines.append(f"  Critical: {self.critical_issues}")
            lines.append(f"  High:     {self.high_issues}")
            lines.append(f"  Medium:   {self.medium_issues}")
            lines.append(f"  Low:      {self.low_issues}")
            lines.append("")
            
            # Group by severity
            for severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.LOW]:
                severity_issues = [i for i in self.issues if i.severity == severity]
                if severity_issues:
                    lines.append(f"  [{severity.value.upper()}]")
                    for issue in severity_issues:
                        lines.append(f"    • {issue.issue_type.value}: {issue.description}")
                        lines.append(f"      Asset: {issue.asset}")
                        if issue.recommendation:
                            lines.append(f"      Recommendation: {issue.recommendation}")
                    lines.append("")
        
        # Footer
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)
        
        return "\n".join(lines)


class BetaValidationHarness:
    """
    Validation harness for beta testing real user accounts.
    
    Runs accounts through the full tax pipeline and generates
    human-reviewable validation reports.
    """
    
    def __init__(self, db):
        """
        Initialize the harness with database connection.
        
        Args:
            db: MongoDB database instance
        """
        self.db = db
    
    async def validate_account(
        self,
        user_id: str,
        tax_year: int = 2024,
        include_all_transactions: bool = True
    ) -> AccountValidationReport:
        """
        Run full validation on a single account.
        
        Args:
            user_id: The user ID to validate
            tax_year: Tax year to analyze
            include_all_transactions: Whether to include all years for lot tracking
        
        Returns:
            AccountValidationReport with complete analysis
        """
        logger.info(f"Starting validation for user {user_id}, tax year {tax_year}")
        
        # Get user info
        user = await self.db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            raise ValueError(f"User not found: {user_id}")
        
        # Initialize report
        report = AccountValidationReport(
            user_id=user_id,
            user_email=user.get("email", "unknown"),
            generated_at=datetime.now(timezone.utc).isoformat(),
            tax_year=tax_year
        )
        
        # 1. Fetch all transactions
        transactions = await self._fetch_transactions(user_id, tax_year, include_all_transactions)
        report.transactions_analyzed = len(transactions)
        
        # 2. Generate classification summary
        report.classification_summary = await self._analyze_classifications(transactions)
        
        # 3. Fetch unresolved review items
        report.unresolved_review_items = await self._fetch_review_queue(user_id)
        report.review_queue_count = len(report.unresolved_review_items)
        
        # 4. Analyze lots and build reconciliation
        report.lot_reconciliation = await self._analyze_lots(user_id, transactions)
        
        # 5. Analyze disposals
        report.disposal_summary = await self._analyze_disposals(user_id, tax_year)
        
        # 6. Run invariant checks
        report.invariant_checks = await self._run_invariant_checks(user_id, transactions, report)
        report.invariants_passed = len([c for c in report.invariant_checks if c.passed])
        report.invariants_failed = len([c for c in report.invariant_checks if not c.passed])
        
        # 7. Highlight issues
        report.issues = await self._detect_issues(user_id, transactions, report)
        report.critical_issues = len([i for i in report.issues if i.severity == SeverityLevel.CRITICAL])
        report.high_issues = len([i for i in report.issues if i.severity == SeverityLevel.HIGH])
        report.medium_issues = len([i for i in report.issues if i.severity == SeverityLevel.MEDIUM])
        report.low_issues = len([i for i in report.issues if i.severity == SeverityLevel.LOW])
        
        # 8. Determine final status
        report = self._determine_status(report)
        
        logger.info(f"Validation complete for {user_id}: status={report.validation_status}, can_export={report.can_export}")
        
        return report
    
    async def validate_multiple_accounts(
        self,
        user_ids: List[str],
        tax_year: int = 2024
    ) -> Dict[str, AccountValidationReport]:
        """
        Run validation on multiple accounts.
        
        Args:
            user_ids: List of user IDs to validate
            tax_year: Tax year to analyze
        
        Returns:
            Dict mapping user_id to their validation report
        """
        reports = {}
        for user_id in user_ids:
            try:
                reports[user_id] = await self.validate_account(user_id, tax_year)
            except Exception as e:
                logger.error(f"Failed to validate {user_id}: {e}")
                # Create error report
                reports[user_id] = AccountValidationReport(
                    user_id=user_id,
                    user_email="error",
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    tax_year=tax_year,
                    validation_status="error",
                    can_export=False,
                    export_blocked_reason=str(e)
                )
        return reports
    
    async def _fetch_transactions(
        self,
        user_id: str,
        tax_year: int,
        include_all: bool
    ) -> List[Dict]:
        """Fetch transactions for analysis"""
        query = {"user_id": user_id}
        
        if not include_all:
            # Only transactions in the tax year
            query["timestamp"] = {
                "$gte": f"{tax_year}-01-01",
                "$lte": f"{tax_year}-12-31"
            }
        
        transactions = await self.db.exchange_transactions.find(
            query, {"_id": 0}
        ).sort("timestamp", 1).to_list(100000)
        
        return transactions
    
    async def _analyze_classifications(self, transactions: List[Dict]) -> ClassificationSummary:
        """Analyze transaction classifications"""
        summary = ClassificationSummary()
        summary.total_transactions = len(transactions)
        
        for tx in transactions:
            tx_type = tx.get("tx_type", "").lower()
            asset = tx.get("asset", "UNKNOWN")
            chain_status = tx.get("chain_status", "")
            
            # Initialize asset tracking
            if asset not in summary.by_asset:
                summary.by_asset[asset] = {
                    "acquisitions": 0, "disposals": 0, "transfers": 0, "income": 0, "unknown": 0
                }
            
            # Classify
            if tx_type in ["buy", "trade"]:
                summary.acquisitions += 1
                summary.by_asset[asset]["acquisitions"] += 1
            elif tx_type in ["sell"]:
                summary.disposals += 1
                summary.by_asset[asset]["disposals"] += 1
            elif tx_type in ["send", "receive", "deposit", "withdrawal"]:
                if chain_status == "linked":
                    summary.internal_transfers += 1
                    summary.by_asset[asset]["transfers"] += 1
                elif chain_status == "external":
                    summary.disposals += 1
                    summary.by_asset[asset]["disposals"] += 1
                else:
                    summary.unknown += 1
                    summary.needs_review += 1
                    summary.by_asset[asset]["unknown"] += 1
            elif tx_type in ["reward", "staking", "airdrop", "mining", "interest"]:
                summary.income += 1
                summary.by_asset[asset]["income"] += 1
            else:
                summary.unknown += 1
                summary.by_asset[asset]["unknown"] += 1
        
        return summary
    
    async def _fetch_review_queue(self, user_id: str) -> List[Dict]:
        """Fetch unresolved review queue items"""
        items = await self.db.review_queue.find(
            {"user_id": user_id, "review_status": {"$in": ["pending", "flagged"]}},
            {"_id": 0}
        ).to_list(10000)
        return items
    
    async def _analyze_lots(self, user_id: str, transactions: List[Dict]) -> LotReconciliationSummary:
        """Analyze lot tracking and reconciliation"""
        summary = LotReconciliationSummary()
        
        # Build lot inventory from acquisitions
        lots_by_asset: Dict[str, List[Dict]] = {}
        
        for tx in transactions:
            tx_type = tx.get("tx_type", "").lower()
            asset = tx.get("asset", "UNKNOWN")
            
            if tx_type in ["buy", "trade", "reward", "staking", "airdrop", "mining", "interest"]:
                if asset not in lots_by_asset:
                    lots_by_asset[asset] = []
                
                quantity = float(tx.get("quantity", 0) or tx.get("amount", 0) or 0)
                cost_basis = float(tx.get("total_usd", 0) or 0)
                
                lots_by_asset[asset].append({
                    "tx_id": tx.get("tx_id"),
                    "quantity": quantity,
                    "remaining": quantity,
                    "cost_basis": cost_basis,
                    "date": tx.get("timestamp")
                })
                summary.total_lots += 1
        
        # Process disposals (FIFO)
        for tx in transactions:
            tx_type = tx.get("tx_type", "").lower()
            asset = tx.get("asset", "UNKNOWN")
            chain_status = tx.get("chain_status", "")
            
            is_disposal = tx_type == "sell" or (tx_type == "send" and chain_status == "external")
            
            if is_disposal and asset in lots_by_asset:
                qty_to_dispose = float(tx.get("quantity", 0) or tx.get("amount", 0) or 0)
                
                for lot in lots_by_asset[asset]:
                    if qty_to_dispose <= 0:
                        break
                    if lot["remaining"] <= 0:
                        continue
                    
                    match = min(lot["remaining"], qty_to_dispose)
                    lot["remaining"] -= match
                    qty_to_dispose -= match
        
        # Summarize lots
        for asset, lots in lots_by_asset.items():
            total_qty = sum(l["remaining"] for l in lots)
            total_basis = sum(
                l["cost_basis"] * (l["remaining"] / l["quantity"]) if l["quantity"] > 0 else 0
                for l in lots
            )
            
            summary.by_asset[asset] = {
                "quantity": total_qty,
                "cost_basis": total_basis,
                "lot_count": len(lots)
            }
            
            summary.total_cost_basis += total_basis
            
            for lot in lots:
                if lot["remaining"] <= 0:
                    summary.fully_disposed_lots += 1
                elif lot["remaining"] < lot["quantity"]:
                    summary.partial_lots += 1
                else:
                    summary.open_lots += 1
        
        return summary
    
    async def _analyze_disposals(self, user_id: str, tax_year: int) -> DisposalSummary:
        """Analyze disposal transactions and tax events"""
        summary = DisposalSummary()
        
        # Fetch tax events for the year
        events = await self.db.tax_events.find({
            "user_id": user_id,
            "is_active": True,
            "date_disposed": {
                "$gte": f"{tax_year}-01-01",
                "$lte": f"{tax_year}-12-31"
            }
        }, {"_id": 0}).to_list(100000)
        
        for event in events:
            summary.total_disposals += 1
            
            proceeds = float(event.get("proceeds", 0))
            cost_basis = float(event.get("cost_basis", 0))
            gain_loss = float(event.get("gain_loss", proceeds - cost_basis))
            holding_period = event.get("holding_period", "short-term")
            asset = event.get("asset", "UNKNOWN")
            
            summary.total_proceeds += proceeds
            summary.total_cost_basis += cost_basis
            summary.total_gain_loss += gain_loss
            
            if holding_period == "long-term":
                summary.long_term_count += 1
                summary.long_term_gain_loss += gain_loss
            else:
                summary.short_term_count += 1
                summary.short_term_gain_loss += gain_loss
            
            if asset not in summary.by_asset:
                summary.by_asset[asset] = {"proceeds": 0, "cost_basis": 0, "gain_loss": 0, "count": 0}
            
            summary.by_asset[asset]["proceeds"] += proceeds
            summary.by_asset[asset]["cost_basis"] += cost_basis
            summary.by_asset[asset]["gain_loss"] += gain_loss
            summary.by_asset[asset]["count"] += 1
        
        return summary
    
    async def _run_invariant_checks(
        self,
        user_id: str,
        transactions: List[Dict],
        report: AccountValidationReport
    ) -> List[InvariantCheckResult]:
        """Run all invariant checks"""
        checks = []
        
        # 1. Balance Reconciliation Check
        balance_check = await self._check_balance_reconciliation(user_id, transactions)
        checks.append(balance_check)
        
        # 2. No Orphan Disposals Check
        orphan_check = await self._check_orphan_disposals(user_id, transactions)
        checks.append(orphan_check)
        
        # 3. Cost Basis Non-Negative Check
        cost_basis_check = await self._check_cost_basis_validity(transactions)
        checks.append(cost_basis_check)
        
        # 4. No Double Disposal Check
        double_check = await self._check_double_disposal(user_id, transactions)
        checks.append(double_check)
        
        # 5. Classification Completeness Check
        classification_check = InvariantCheckResult(
            check_name="Classification Completeness",
            passed=report.classification_summary.unknown == 0,
            details={"unknown_count": report.classification_summary.unknown},
            affected_assets=list(
                asset for asset, data in report.classification_summary.by_asset.items()
                if data.get("unknown", 0) > 0
            )
        )
        checks.append(classification_check)
        
        # 6. Review Queue Empty Check
        review_check = InvariantCheckResult(
            check_name="Review Queue Resolved",
            passed=len(report.unresolved_review_items) == 0,
            details={"unresolved_count": len(report.unresolved_review_items)},
            affected_assets=list(set(
                item.get("asset", "UNKNOWN") for item in report.unresolved_review_items
            ))
        )
        checks.append(review_check)
        
        return checks
    
    async def _check_balance_reconciliation(
        self,
        user_id: str,
        transactions: List[Dict]
    ) -> InvariantCheckResult:
        """Check if balances reconcile"""
        balances: Dict[str, Decimal] = {}
        affected = []
        
        for tx in transactions:
            asset = tx.get("asset", "UNKNOWN")
            tx_type = tx.get("tx_type", "").lower()
            chain_status = tx.get("chain_status", "")
            qty = Decimal(str(tx.get("quantity", 0) or tx.get("amount", 0) or 0))
            
            if asset not in balances:
                balances[asset] = Decimal("0")
            
            # Acquisitions add to balance
            if tx_type in ["buy", "trade", "reward", "staking", "airdrop", "mining", "interest", "receive", "deposit"]:
                if not (tx_type in ["receive", "deposit"] and chain_status == "linked"):
                    balances[asset] += qty
            
            # Disposals subtract from balance
            if tx_type == "sell" or (tx_type == "send" and chain_status == "external"):
                balances[asset] -= qty
        
        # Check for negative balances
        for asset, balance in balances.items():
            if balance < 0:
                affected.append(asset)
        
        return InvariantCheckResult(
            check_name="Balance Reconciliation",
            passed=len(affected) == 0,
            details={
                "balances": {k: float(v) for k, v in balances.items()},
                "negative_balances": affected
            },
            affected_assets=affected
        )
    
    async def _check_orphan_disposals(
        self,
        user_id: str,
        transactions: List[Dict]
    ) -> InvariantCheckResult:
        """Check for disposals without acquisitions"""
        acquired: Dict[str, Decimal] = {}
        disposed: Dict[str, Decimal] = {}
        orphans = []
        
        for tx in transactions:
            asset = tx.get("asset", "UNKNOWN")
            tx_type = tx.get("tx_type", "").lower()
            chain_status = tx.get("chain_status", "")
            qty = Decimal(str(tx.get("quantity", 0) or tx.get("amount", 0) or 0))
            
            if asset not in acquired:
                acquired[asset] = Decimal("0")
                disposed[asset] = Decimal("0")
            
            if tx_type in ["buy", "trade", "reward", "staking", "airdrop", "mining", "interest"]:
                acquired[asset] += qty
            elif tx_type == "sell" or (tx_type == "send" and chain_status == "external"):
                disposed[asset] += qty
        
        for asset in disposed:
            if disposed[asset] > acquired.get(asset, Decimal("0")):
                orphans.append(asset)
        
        return InvariantCheckResult(
            check_name="No Orphan Disposals",
            passed=len(orphans) == 0,
            details={
                "acquired": {k: float(v) for k, v in acquired.items()},
                "disposed": {k: float(v) for k, v in disposed.items()},
                "orphan_assets": orphans
            },
            affected_assets=orphans
        )
    
    async def _check_cost_basis_validity(self, transactions: List[Dict]) -> InvariantCheckResult:
        """Check for negative or invalid cost basis"""
        invalid = []
        
        for tx in transactions:
            cost_basis = tx.get("total_usd", 0) or tx.get("cost_basis", 0) or 0
            if cost_basis < 0:
                invalid.append(tx.get("tx_id", "unknown"))
        
        return InvariantCheckResult(
            check_name="Cost Basis Validity",
            passed=len(invalid) == 0,
            details={"invalid_transactions": invalid},
            affected_assets=[]
        )
    
    async def _check_double_disposal(
        self,
        user_id: str,
        transactions: List[Dict]
    ) -> InvariantCheckResult:
        """Check for potential double disposals"""
        disposal_ids: Set[str] = set()
        duplicates = []
        
        for tx in transactions:
            tx_id = tx.get("tx_id", "")
            tx_type = tx.get("tx_type", "").lower()
            
            if tx_type == "sell":
                if tx_id in disposal_ids:
                    duplicates.append(tx_id)
                disposal_ids.add(tx_id)
        
        return InvariantCheckResult(
            check_name="No Double Disposal",
            passed=len(duplicates) == 0,
            details={"duplicate_tx_ids": duplicates},
            affected_assets=[]
        )
    
    async def _detect_issues(
        self,
        user_id: str,
        transactions: List[Dict],
        report: AccountValidationReport
    ) -> List[ValidationIssue]:
        """Detect and highlight specific issues"""
        issues = []
        
        # 1. Check for orphan disposals
        for check in report.invariant_checks:
            if check.check_name == "No Orphan Disposals" and not check.passed:
                for asset in check.affected_assets:
                    issues.append(ValidationIssue(
                        issue_type=IssueType.ORPHAN_DISPOSAL,
                        severity=SeverityLevel.CRITICAL,
                        asset=asset,
                        description=f"Disposed more {asset} than acquired",
                        details=check.details,
                        recommendation="Review acquisitions or check for missing buy transactions"
                    ))
        
        # 2. Check for balance mismatches
        for check in report.invariant_checks:
            if check.check_name == "Balance Reconciliation" and not check.passed:
                for asset in check.affected_assets:
                    issues.append(ValidationIssue(
                        issue_type=IssueType.BALANCE_MISMATCH,
                        severity=SeverityLevel.CRITICAL,
                        asset=asset,
                        description=f"Negative balance detected for {asset}",
                        details={"balance": check.details.get("balances", {}).get(asset, 0)},
                        recommendation="Check for missing deposits or incorrect disposal amounts"
                    ))
        
        # 3. Check for unresolved chain breaks
        for item in report.unresolved_review_items:
            issues.append(ValidationIssue(
                issue_type=IssueType.UNRESOLVED_CHAIN_BREAK,
                severity=SeverityLevel.HIGH,
                asset=item.get("asset", "UNKNOWN"),
                description="Unresolved transfer requires user decision",
                details=item,
                transaction_ids=[item.get("tx_id", "")],
                recommendation="User must resolve as 'Mine' or 'External'"
            ))
        
        # 4. Check for unknown classifications
        if report.classification_summary.unknown > 0:
            for asset, data in report.classification_summary.by_asset.items():
                if data.get("unknown", 0) > 0:
                    issues.append(ValidationIssue(
                        issue_type=IssueType.UNKNOWN_CLASSIFICATION,
                        severity=SeverityLevel.HIGH,
                        asset=asset,
                        description=f"{data['unknown']} transactions with unknown classification",
                        details={"count": data["unknown"]},
                        recommendation="Review and classify these transactions"
                    ))
        
        # 5. Check for missing price data (cost basis = 0 on acquisitions)
        for tx in transactions:
            tx_type = tx.get("tx_type", "").lower()
            cost_basis = tx.get("total_usd", 0) or 0
            
            if tx_type in ["buy", "trade"] and cost_basis == 0:
                issues.append(ValidationIssue(
                    issue_type=IssueType.PRICE_DATA_MISSING,
                    severity=SeverityLevel.MEDIUM,
                    asset=tx.get("asset", "UNKNOWN"),
                    description="Acquisition with zero cost basis",
                    details={"tx_id": tx.get("tx_id")},
                    transaction_ids=[tx.get("tx_id", "")],
                    recommendation="Verify price data for this transaction"
                ))
        
        return issues
    
    def _determine_status(self, report: AccountValidationReport) -> AccountValidationReport:
        """Determine final validation status"""
        # Critical issues block export
        if report.critical_issues > 0:
            report.validation_status = "invalid"
            report.can_export = False
            report.export_blocked_reason = f"{report.critical_issues} critical issues found"
            return report
        
        # Failed invariants block export
        if report.invariants_failed > 0:
            report.validation_status = "invalid"
            report.can_export = False
            report.export_blocked_reason = f"{report.invariants_failed} invariant checks failed"
            return report
        
        # Unresolved review items block export
        if report.review_queue_count > 0:
            report.validation_status = "needs_review"
            report.can_export = False
            report.export_blocked_reason = f"{report.review_queue_count} items need user review"
            return report
        
        # High issues are warnings but don't block
        if report.high_issues > 0:
            report.validation_status = "needs_review"
            report.can_export = True  # Allow with warning
            return report
        
        # All good
        report.validation_status = "valid"
        report.can_export = True
        return report
    
    def export_report(self, report: AccountValidationReport, filepath: str, format: str = "both"):
        """
        Export validation report to file.
        
        Args:
            report: The validation report to export
            filepath: Base path for the report (extension added based on format)
            format: "json", "text", or "both"
        """
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        if format in ["json", "both"]:
            json_path = filepath if filepath.endswith(".json") else f"{filepath}.json"
            with open(json_path, "w") as f:
                json.dump(report.to_dict(), f, indent=2, default=str)
            logger.info(f"JSON report exported to: {json_path}")
        
        if format in ["text", "both"]:
            text_path = filepath.replace(".json", ".txt") if filepath.endswith(".json") else f"{filepath}.txt"
            with open(text_path, "w") as f:
                f.write(report.to_human_readable())
            logger.info(f"Text report exported to: {text_path}")
    
    def generate_batch_summary(self, reports: Dict[str, AccountValidationReport]) -> Dict:
        """Generate summary for batch validation"""
        summary = {
            "total_accounts": len(reports),
            "valid": 0,
            "needs_review": 0,
            "invalid": 0,
            "error": 0,
            "can_export": 0,
            "blocked": 0,
            "total_issues": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            },
            "accounts": []
        }
        
        for user_id, report in reports.items():
            status = report.validation_status
            summary[status] = summary.get(status, 0) + 1
            
            if report.can_export:
                summary["can_export"] += 1
            else:
                summary["blocked"] += 1
            
            summary["total_issues"]["critical"] += report.critical_issues
            summary["total_issues"]["high"] += report.high_issues
            summary["total_issues"]["medium"] += report.medium_issues
            summary["total_issues"]["low"] += report.low_issues
            
            summary["accounts"].append({
                "user_id": user_id,
                "email": report.user_email,
                "status": status,
                "can_export": report.can_export,
                "issues": report.critical_issues + report.high_issues
            })
        
        return summary


# Factory function for easy access
def create_validation_harness(db) -> BetaValidationHarness:
    """Create a new validation harness instance"""
    return BetaValidationHarness(db)
