"""
Tax Validation and Invariant Enforcement Layer

Ensures all generated tax records are accurate, internally consistent, and auditable.
Prevents silent errors by enforcing strict validation rules before any tax output is finalized.

Architecture:
- Validates transactions before entering tax logic
- Enforces invariants on cost basis and balance reconciliation
- Blocks tax output generation if validation fails
- Provides full audit trail for all calculations
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
import uuid

logger = logging.getLogger(__name__)


# ========================================
# CLASSIFICATION ENUM
# ========================================

class TxClassification(str, Enum):
    """
    Mandatory classification for all transactions.
    No transaction may proceed to tax calculation if classification is 'unknown'.
    """
    ACQUISITION = "acquisition"          # Buy, trade-in (adds to cost basis)
    DISPOSAL = "disposal"                # Sell, trade-out (triggers capital gains)
    INTERNAL_TRANSFER = "internal_transfer"  # Between owned wallets (no tax event)
    INCOME = "income"                    # Staking, rewards, airdrops (ordinary income + cost basis)
    UNKNOWN = "unknown"                  # Unclassified - MUST route to review queue


class ValidationStatus(str, Enum):
    """Status of tax validation"""
    VALID = "valid"
    INVALID = "invalid"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class InvariantType(str, Enum):
    """Types of invariant checks"""
    BALANCE_RECONCILIATION = "balance_reconciliation"
    COST_BASIS_CONSERVATION = "cost_basis_conservation"
    NO_DOUBLE_SPEND = "no_double_spend"
    NO_ORPHAN_DISPOSAL = "no_orphan_disposal"
    NEGATIVE_COST_BASIS = "negative_cost_basis"
    QUANTITY_EXCEEDED = "quantity_exceeded"


# ========================================
# DATA CLASSES FOR VALIDATION
# ========================================

@dataclass
class LotRecord:
    """Represents a tax lot for tracking"""
    lot_id: str
    tx_id: str
    asset: str
    acquisition_date: datetime
    quantity: Decimal
    remaining_quantity: Decimal
    cost_basis_per_unit: Decimal
    total_cost_basis: Decimal
    source: str  # exchange name or wallet address
    classification: TxClassification
    price_source: str  # Where price data came from
    is_disposed: bool = False
    disposed_quantity: Decimal = Decimal("0")
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['acquisition_date'] = self.acquisition_date.isoformat() if self.acquisition_date else None
        d['quantity'] = float(self.quantity)
        d['remaining_quantity'] = float(self.remaining_quantity)
        d['cost_basis_per_unit'] = float(self.cost_basis_per_unit)
        d['total_cost_basis'] = float(self.total_cost_basis)
        d['disposed_quantity'] = float(self.disposed_quantity)
        d['classification'] = self.classification.value
        return d


@dataclass
class DisposalRecord:
    """Represents a disposal event for tracking"""
    disposal_id: str
    tx_id: str
    asset: str
    disposal_date: datetime
    quantity: Decimal
    proceeds: Decimal
    matched_lots: List[Dict] = field(default_factory=list)  # Lot IDs and quantities matched
    total_cost_basis: Decimal = Decimal("0")
    gain_loss: Decimal = Decimal("0")
    holding_period: str = "unknown"
    is_validated: bool = False
    validation_errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['disposal_date'] = self.disposal_date.isoformat() if self.disposal_date else None
        d['quantity'] = float(self.quantity)
        d['proceeds'] = float(self.proceeds)
        d['total_cost_basis'] = float(self.total_cost_basis)
        d['gain_loss'] = float(self.gain_loss)
        return d


@dataclass
class InvariantViolation:
    """Records an invariant violation"""
    violation_id: str
    invariant_type: InvariantType
    asset: str
    severity: str  # "error", "warning"
    message: str
    details: Dict
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def to_dict(self) -> Dict:
        d = asdict(self)
        d['invariant_type'] = self.invariant_type.value
        d['detected_at'] = self.detected_at.isoformat()
        return d


@dataclass
class ValidationResult:
    """Complete validation result"""
    is_valid: bool
    status: ValidationStatus
    violations: List[InvariantViolation] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    transactions_validated: int = 0
    transactions_blocked: int = 0
    needs_review_count: int = 0
    audit_trail: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "status": self.status.value,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": self.warnings,
            "transactions_validated": self.transactions_validated,
            "transactions_blocked": self.transactions_blocked,
            "needs_review_count": self.needs_review_count,
            "audit_trail": self.audit_trail
        }


# ========================================
# TAX VALIDATION SERVICE
# ========================================

class TaxValidationService:
    """
    Core validation service that enforces tax integrity invariants.
    
    Responsibilities:
    1. Classify all transactions before tax logic
    2. Enforce strict lot tracking with FIFO
    3. Run invariant checks before tax output
    4. Block invalid states from generating tax reports
    5. Maintain full audit trail
    """
    
    # Confidence threshold below which transactions need review
    CONFIDENCE_THRESHOLD = 0.5
    
    # Maximum reasonable values (safety limits)
    MAX_QUANTITY_PER_TX = Decimal("1000000000")  # 1 billion units
    MAX_PRICE_USD = Decimal("1000000")  # $1M per unit
    MAX_TX_VALUE_USD = Decimal("100000000000")  # $100B per transaction
    
    def __init__(self):
        self.lots_by_asset: Dict[str, List[LotRecord]] = {}
        self.disposals: List[DisposalRecord] = []
        self.disposed_unit_ids: Set[str] = set()  # Track disposed units for double-spend detection
        self.violations: List[InvariantViolation] = []
        self.audit_trail: List[Dict] = []
        self.account_tax_state_valid: bool = True
    
    # ========================================
    # TRANSACTION CLASSIFICATION
    # ========================================
    
    def classify_transaction(self, tx: Dict) -> Tuple[TxClassification, float]:
        """
        Classify a transaction into one of the allowed types.
        
        Returns:
            Tuple of (classification, confidence)
        """
        tx_type = tx.get("tx_type", "").lower()
        chain_status = tx.get("chain_status", "")
        is_transfer = tx.get("is_transfer", False)
        
        # High confidence classifications
        if tx_type in ["buy", "trade"]:
            return (TxClassification.ACQUISITION, 1.0)
        
        if tx_type in ["sell"]:
            return (TxClassification.DISPOSAL, 1.0)
        
        if tx_type in ["reward", "staking", "airdrop", "mining", "interest"]:
            return (TxClassification.INCOME, 1.0)
        
        # Transfer classifications - depend on chain of custody
        if tx_type in ["send", "withdrawal"]:
            if chain_status == "linked":
                return (TxClassification.INTERNAL_TRANSFER, 0.95)
            elif chain_status == "external":
                return (TxClassification.DISPOSAL, 0.95)
            else:
                # Unresolved - needs review
                return (TxClassification.UNKNOWN, 0.3)
        
        if tx_type in ["receive", "deposit"]:
            if is_transfer or chain_status == "linked":
                return (TxClassification.INTERNAL_TRANSFER, 0.9)
            elif tx.get("is_new_acquisition", False):
                return (TxClassification.ACQUISITION, 0.8)
            else:
                # Could be transfer or acquisition - needs review
                return (TxClassification.UNKNOWN, 0.4)
        
        # Unknown type
        return (TxClassification.UNKNOWN, 0.0)
    
    def validate_classification(self, tx: Dict) -> Dict:
        """
        Validate and enrich transaction with classification.
        Routes unknown classifications to review queue.
        
        Returns:
            Transaction dict with classification fields added
        """
        classification, confidence = self.classify_transaction(tx)
        
        tx_validated = {
            **tx,
            "classification": classification.value,
            "classification_confidence": confidence,
            "needs_review": classification == TxClassification.UNKNOWN or confidence < self.CONFIDENCE_THRESHOLD,
            "validated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Log audit trail
        self._log_audit(
            action="classify_transaction",
            tx_id=tx.get("tx_id"),
            details={
                "original_type": tx.get("tx_type"),
                "classification": classification.value,
                "confidence": confidence,
                "needs_review": tx_validated["needs_review"]
            }
        )
        
        return tx_validated
    
    # ========================================
    # COST BASIS ENGINE WITH LOT TRACKING
    # ========================================
    
    def create_lot(
        self,
        tx_id: str,
        asset: str,
        acquisition_date: datetime,
        quantity: float,
        cost_basis_per_unit: float,
        source: str,
        classification: TxClassification,
        price_source: str = "original"
    ) -> LotRecord:
        """
        Create a new tax lot with strict validation.
        
        Constraints:
        - Cost basis must never be negative
        - Quantity must be positive
        """
        qty = Decimal(str(quantity))
        cost_per_unit = Decimal(str(cost_basis_per_unit))
        
        # Validate constraints
        if qty <= 0:
            raise ValueError(f"Lot quantity must be positive: {qty}")
        
        if cost_per_unit < 0:
            self._add_violation(
                InvariantType.NEGATIVE_COST_BASIS,
                asset,
                "error",
                f"Negative cost basis detected: ${cost_per_unit}",
                {"tx_id": tx_id, "cost_basis_per_unit": float(cost_per_unit)}
            )
            raise ValueError(f"Cost basis cannot be negative: {cost_per_unit}")
        
        if qty > self.MAX_QUANTITY_PER_TX:
            raise ValueError(f"Quantity exceeds maximum: {qty} > {self.MAX_QUANTITY_PER_TX}")
        
        if cost_per_unit > self.MAX_PRICE_USD:
            raise ValueError(f"Price exceeds maximum: ${cost_per_unit} > ${self.MAX_PRICE_USD}")
        
        lot = LotRecord(
            lot_id=str(uuid.uuid4()),
            tx_id=tx_id,
            asset=asset.upper(),
            acquisition_date=acquisition_date,
            quantity=qty,
            remaining_quantity=qty,
            cost_basis_per_unit=cost_per_unit,
            total_cost_basis=qty * cost_per_unit,
            source=source,
            classification=classification,
            price_source=price_source
        )
        
        # Add to tracking
        if asset.upper() not in self.lots_by_asset:
            self.lots_by_asset[asset.upper()] = []
        self.lots_by_asset[asset.upper()].append(lot)
        
        # Sort by acquisition date (FIFO)
        self.lots_by_asset[asset.upper()].sort(key=lambda x: x.acquisition_date)
        
        self._log_audit(
            action="create_lot",
            tx_id=tx_id,
            details={
                "lot_id": lot.lot_id,
                "asset": asset,
                "quantity": float(qty),
                "cost_basis_per_unit": float(cost_per_unit),
                "total_cost_basis": float(lot.total_cost_basis)
            }
        )
        
        return lot
    
    def dispose_from_lots(
        self,
        tx_id: str,
        asset: str,
        disposal_date: datetime,
        quantity: float,
        proceeds: float
    ) -> DisposalRecord:
        """
        Match disposal against existing lots using FIFO.
        
        Constraints:
        - Total disposed quantity must not exceed acquired quantity
        - Each unit can only be disposed once (no double spend)
        - Every disposal must have acquisition source, cost basis, timestamp, price
        """
        qty_to_dispose = Decimal(str(quantity))
        total_proceeds = Decimal(str(proceeds))
        asset_upper = asset.upper()
        
        # Check if we have lots for this asset
        if asset_upper not in self.lots_by_asset or not self.lots_by_asset[asset_upper]:
            self._add_violation(
                InvariantType.NO_ORPHAN_DISPOSAL,
                asset,
                "error",
                f"Disposal of {quantity} {asset} has no acquisition source",
                {"tx_id": tx_id, "quantity": quantity}
            )
            raise ValueError(f"No lots available for disposal: {asset}")
        
        # Check total available quantity
        total_available = sum(lot.remaining_quantity for lot in self.lots_by_asset[asset_upper])
        if qty_to_dispose > total_available:
            self._add_violation(
                InvariantType.QUANTITY_EXCEEDED,
                asset,
                "error",
                f"Disposal quantity {quantity} exceeds available {float(total_available)} {asset}",
                {"tx_id": tx_id, "disposal_qty": quantity, "available_qty": float(total_available)}
            )
            raise ValueError(f"Insufficient quantity: trying to dispose {quantity} but only {total_available} available")
        
        # FIFO matching
        disposal = DisposalRecord(
            disposal_id=str(uuid.uuid4()),
            tx_id=tx_id,
            asset=asset_upper,
            disposal_date=disposal_date,
            quantity=qty_to_dispose,
            proceeds=total_proceeds
        )
        
        remaining_to_dispose = qty_to_dispose
        total_cost_basis = Decimal("0")
        matched_lots = []
        earliest_acquisition = None
        
        for lot in self.lots_by_asset[asset_upper]:
            if remaining_to_dispose <= 0:
                break
            
            if lot.remaining_quantity <= 0:
                continue
            
            # Calculate match
            match_qty = min(lot.remaining_quantity, remaining_to_dispose)
            match_cost = match_qty * lot.cost_basis_per_unit
            
            # Generate unique unit ID for double-spend tracking
            unit_id = f"{lot.lot_id}:{float(lot.quantity - lot.remaining_quantity):.8f}-{float(lot.quantity - lot.remaining_quantity + match_qty):.8f}"
            
            # Check for double spend
            if unit_id in self.disposed_unit_ids:
                self._add_violation(
                    InvariantType.NO_DOUBLE_SPEND,
                    asset,
                    "error",
                    f"Double spend detected: units from lot {lot.lot_id} already disposed",
                    {"tx_id": tx_id, "lot_id": lot.lot_id, "unit_id": unit_id}
                )
                raise ValueError(f"Double spend detected for lot {lot.lot_id}")
            
            # Validate lot has required data
            if not lot.acquisition_date:
                disposal.validation_errors.append(f"Lot {lot.lot_id} missing acquisition date")
            if lot.cost_basis_per_unit is None:
                disposal.validation_errors.append(f"Lot {lot.lot_id} missing cost basis")
            
            # Record the match
            self.disposed_unit_ids.add(unit_id)
            lot.remaining_quantity -= match_qty
            lot.disposed_quantity += match_qty
            
            if lot.remaining_quantity <= 0:
                lot.is_disposed = True
            
            matched_lots.append({
                "lot_id": lot.lot_id,
                "quantity_matched": float(match_qty),
                "cost_basis_matched": float(match_cost),
                "acquisition_date": lot.acquisition_date.isoformat(),
                "cost_basis_per_unit": float(lot.cost_basis_per_unit)
            })
            
            total_cost_basis += match_cost
            remaining_to_dispose -= match_qty
            
            if earliest_acquisition is None or lot.acquisition_date < earliest_acquisition:
                earliest_acquisition = lot.acquisition_date
        
        # Complete disposal record
        disposal.matched_lots = matched_lots
        disposal.total_cost_basis = total_cost_basis
        disposal.gain_loss = total_proceeds - total_cost_basis
        disposal.holding_period = self._calculate_holding_period(earliest_acquisition, disposal_date)
        disposal.is_validated = len(disposal.validation_errors) == 0
        
        self.disposals.append(disposal)
        
        self._log_audit(
            action="dispose_from_lots",
            tx_id=tx_id,
            details={
                "disposal_id": disposal.disposal_id,
                "asset": asset,
                "quantity": float(qty_to_dispose),
                "proceeds": float(total_proceeds),
                "cost_basis": float(total_cost_basis),
                "gain_loss": float(disposal.gain_loss),
                "lots_matched": len(matched_lots),
                "holding_period": disposal.holding_period
            }
        )
        
        return disposal
    
    # ========================================
    # INVARIANT CHECKS
    # ========================================
    
    def check_balance_reconciliation(self, asset: str, starting_balance: float, ending_balance: float) -> bool:
        """
        Invariant A: Balance Reconciliation
        starting_balance + acquisitions - disposals = ending_balance
        """
        asset_upper = asset.upper()
        
        # Calculate acquisitions
        acquisitions = Decimal("0")
        if asset_upper in self.lots_by_asset:
            acquisitions = sum(lot.quantity for lot in self.lots_by_asset[asset_upper])
        
        # Calculate disposals
        disposals = Decimal("0")
        for disposal in self.disposals:
            if disposal.asset == asset_upper:
                disposals += disposal.quantity
        
        # Check reconciliation
        expected_ending = Decimal(str(starting_balance)) + acquisitions - disposals
        actual_ending = Decimal(str(ending_balance))
        
        # Allow small tolerance for floating point
        tolerance = Decimal("0.00000001")
        is_valid = abs(expected_ending - actual_ending) <= tolerance
        
        if not is_valid:
            self._add_violation(
                InvariantType.BALANCE_RECONCILIATION,
                asset,
                "error",
                f"Balance reconciliation failed: {starting_balance} + {float(acquisitions)} - {float(disposals)} = {float(expected_ending)}, but actual ending is {ending_balance}",
                {
                    "starting_balance": starting_balance,
                    "acquisitions": float(acquisitions),
                    "disposals": float(disposals),
                    "expected_ending": float(expected_ending),
                    "actual_ending": ending_balance,
                    "difference": float(expected_ending - actual_ending)
                }
            )
        
        self._log_audit(
            action="check_balance_reconciliation",
            tx_id=None,
            details={
                "asset": asset,
                "starting_balance": starting_balance,
                "acquisitions": float(acquisitions),
                "disposals": float(disposals),
                "expected_ending": float(expected_ending),
                "actual_ending": ending_balance,
                "is_valid": is_valid
            }
        )
        
        return is_valid
    
    def check_cost_basis_conservation(self, internal_transfers: List[Dict]) -> bool:
        """
        Invariant B: Cost Basis Conservation
        Internal transfers must NOT change total cost basis
        """
        is_valid = True
        
        for transfer in internal_transfers:
            source_cost = Decimal(str(transfer.get("source_cost_basis", 0)))
            dest_cost = Decimal(str(transfer.get("destination_cost_basis", 0)))
            
            if source_cost != dest_cost:
                is_valid = False
                self._add_violation(
                    InvariantType.COST_BASIS_CONSERVATION,
                    transfer.get("asset", "UNKNOWN"),
                    "error",
                    f"Internal transfer changed cost basis: ${source_cost} -> ${dest_cost}",
                    {
                        "tx_id": transfer.get("tx_id"),
                        "source_cost_basis": float(source_cost),
                        "destination_cost_basis": float(dest_cost),
                        "difference": float(dest_cost - source_cost)
                    }
                )
        
        return is_valid
    
    def check_no_double_spend(self) -> bool:
        """
        Invariant C: No Double Spend
        Each unit of asset can only be disposed once
        (Already enforced in dispose_from_lots, this is a verification check)
        """
        # Check for any lots where disposed_quantity > quantity
        is_valid = True
        
        for asset, lots in self.lots_by_asset.items():
            for lot in lots:
                if lot.disposed_quantity > lot.quantity:
                    is_valid = False
                    self._add_violation(
                        InvariantType.NO_DOUBLE_SPEND,
                        asset,
                        "error",
                        f"Lot {lot.lot_id} over-disposed: {float(lot.disposed_quantity)} > {float(lot.quantity)}",
                        {
                            "lot_id": lot.lot_id,
                            "quantity": float(lot.quantity),
                            "disposed_quantity": float(lot.disposed_quantity)
                        }
                    )
        
        return is_valid
    
    def check_no_orphan_disposals(self) -> bool:
        """
        Invariant D: No Orphan Disposals
        Every disposal must have: acquisition source, cost basis, timestamp, price
        """
        is_valid = True
        
        for disposal in self.disposals:
            if not disposal.matched_lots:
                is_valid = False
                self._add_violation(
                    InvariantType.NO_ORPHAN_DISPOSAL,
                    disposal.asset,
                    "error",
                    f"Disposal {disposal.disposal_id} has no matched acquisition lots",
                    {"disposal_id": disposal.disposal_id, "tx_id": disposal.tx_id}
                )
            
            for lot_match in disposal.matched_lots:
                if not lot_match.get("acquisition_date"):
                    is_valid = False
                    disposal.validation_errors.append("Missing acquisition date")
                if lot_match.get("cost_basis_per_unit") is None:
                    is_valid = False
                    disposal.validation_errors.append("Missing cost basis")
        
        return is_valid
    
    def run_all_invariant_checks(self, balances: Dict[str, Dict] = None) -> ValidationResult:
        """
        Run all invariant checks and return comprehensive result.
        
        Args:
            balances: Dict of {asset: {"starting": X, "ending": Y}} for balance reconciliation
        
        Returns:
            ValidationResult with all violations and audit trail
        """
        self.violations = []  # Reset violations
        
        # Run all checks
        checks_passed = 0
        checks_failed = 0
        
        # Balance reconciliation for each asset
        if balances:
            for asset, bal in balances.items():
                if self.check_balance_reconciliation(asset, bal.get("starting", 0), bal.get("ending", 0)):
                    checks_passed += 1
                else:
                    checks_failed += 1
        
        # Cost basis conservation (internal transfers)
        # This would need internal transfer data passed in
        
        # No double spend
        if self.check_no_double_spend():
            checks_passed += 1
        else:
            checks_failed += 1
        
        # No orphan disposals
        if self.check_no_orphan_disposals():
            checks_passed += 1
        else:
            checks_failed += 1
        
        # Determine overall status
        has_errors = any(v.severity == "error" for v in self.violations)
        has_warnings = any(v.severity == "warning" for v in self.violations)
        
        if has_errors:
            status = ValidationStatus.INVALID
            self.account_tax_state_valid = False
        elif has_warnings:
            status = ValidationStatus.NEEDS_REVIEW
        else:
            status = ValidationStatus.VALID
        
        return ValidationResult(
            is_valid=not has_errors,
            status=status,
            violations=self.violations,
            warnings=[v.message for v in self.violations if v.severity == "warning"],
            transactions_validated=checks_passed + checks_failed,
            transactions_blocked=checks_failed,
            audit_trail=self.audit_trail
        )
    
    # ========================================
    # FORM 8949 VALIDATION
    # ========================================
    
    def validate_form_8949_record(self, record: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a single Form 8949 record before export.
        
        Required fields:
        - description (asset)
        - date acquired
        - date disposed
        - proceeds
        - cost basis
        - gain/loss
        
        Returns:
            Tuple of (is_valid, list of errors)
        """
        errors = []
        
        # Check required fields
        required_fields = [
            ("description", "Description of property"),
            ("date_acquired", "Date acquired"),
            ("date_sold", "Date sold/disposed"),
            ("proceeds", "Proceeds"),
            ("cost_basis", "Cost basis"),
            ("gain_or_loss", "Gain or loss")
        ]
        
        for field_name, label in required_fields:
            if field_name not in record or record[field_name] is None or record[field_name] == "":
                errors.append(f"Missing required field: {label}")
        
        # Check for negative values where inappropriate
        if record.get("proceeds") is not None and float(record.get("proceeds", 0)) < 0:
            errors.append(f"Proceeds cannot be negative: {record.get('proceeds')}")
        
        if record.get("cost_basis") is not None and float(record.get("cost_basis", 0)) < 0:
            errors.append(f"Cost basis cannot be negative: {record.get('cost_basis')}")
        
        # Verify gain/loss calculation
        if all(record.get(f) is not None for f in ["proceeds", "cost_basis", "gain_or_loss"]):
            expected_gain = float(record["proceeds"]) - float(record["cost_basis"])
            actual_gain = float(record["gain_or_loss"])
            if abs(expected_gain - actual_gain) > 0.01:  # Allow 1 cent tolerance
                errors.append(f"Gain/loss calculation mismatch: {actual_gain} != {record['proceeds']} - {record['cost_basis']}")
        
        return (len(errors) == 0, errors)
    
    def validate_form_8949_export(self, records: List[Dict]) -> Tuple[bool, ValidationResult]:
        """
        Validate entire Form 8949 export before generating.
        
        Checks:
        - All records have required fields
        - No negative or invalid values
        - Totals reconcile with underlying transactions
        
        Returns:
            Tuple of (can_export, ValidationResult)
        """
        all_errors = []
        total_proceeds = Decimal("0")
        total_cost_basis = Decimal("0")
        total_gain_loss = Decimal("0")
        
        for i, record in enumerate(records):
            is_valid, errors = self.validate_form_8949_record(record)
            if not is_valid:
                for error in errors:
                    all_errors.append(f"Record {i+1}: {error}")
            else:
                total_proceeds += Decimal(str(record.get("proceeds", 0)))
                total_cost_basis += Decimal(str(record.get("cost_basis", 0)))
                total_gain_loss += Decimal(str(record.get("gain_or_loss", 0)))
        
        # Verify totals reconcile
        expected_gain_loss = total_proceeds - total_cost_basis
        if abs(expected_gain_loss - total_gain_loss) > Decimal("0.01"):
            all_errors.append(f"Total gain/loss mismatch: sum of records ({float(total_gain_loss)}) != proceeds ({float(total_proceeds)}) - cost basis ({float(total_cost_basis)})")
        
        # Check against internal disposal records
        internal_gain_loss = sum(d.gain_loss for d in self.disposals)
        if abs(Decimal(str(internal_gain_loss)) - total_gain_loss) > Decimal("1.00"):  # Allow $1 tolerance
            all_errors.append(f"Export total ({float(total_gain_loss)}) doesn't match internal records ({float(internal_gain_loss)})")
        
        can_export = len(all_errors) == 0
        
        if not can_export:
            for error in all_errors:
                self._add_violation(
                    InvariantType.NO_ORPHAN_DISPOSAL,  # Using as general validation error
                    "FORM_8949",
                    "error",
                    error,
                    {"record_count": len(records)}
                )
        
        result = ValidationResult(
            is_valid=can_export,
            status=ValidationStatus.VALID if can_export else ValidationStatus.BLOCKED,
            violations=self.violations,
            transactions_validated=len(records),
            transactions_blocked=len(all_errors),
            audit_trail=self.audit_trail
        )
        
        self._log_audit(
            action="validate_form_8949_export",
            tx_id=None,
            details={
                "record_count": len(records),
                "total_proceeds": float(total_proceeds),
                "total_cost_basis": float(total_cost_basis),
                "total_gain_loss": float(total_gain_loss),
                "can_export": can_export,
                "error_count": len(all_errors)
            }
        )
        
        return (can_export, result)
    
    # ========================================
    # RECOMPUTE LOGIC
    # ========================================
    
    def trigger_full_recompute(self, reason: str) -> Dict:
        """
        Trigger full recomputation of cost basis and tax events.
        Called when:
        - Wallet linkage changes
        - Classification changes
        - Transaction data changes
        
        No partial updates allowed.
        """
        self._log_audit(
            action="trigger_full_recompute",
            tx_id=None,
            details={"reason": reason, "timestamp": datetime.now(timezone.utc).isoformat()}
        )
        
        # Clear all computed state
        old_lots_count = sum(len(lots) for lots in self.lots_by_asset.values())
        old_disposals_count = len(self.disposals)
        
        self.lots_by_asset = {}
        self.disposals = []
        self.disposed_unit_ids = set()
        self.violations = []
        
        return {
            "recompute_triggered": True,
            "reason": reason,
            "cleared_lots": old_lots_count,
            "cleared_disposals": old_disposals_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    def _calculate_holding_period(self, acquisition_date: datetime, disposal_date: datetime) -> str:
        """Calculate if holding period is short-term or long-term"""
        if not acquisition_date or not disposal_date:
            return "unknown"
        
        try:
            days_held = (disposal_date - acquisition_date).days
            return "long-term" if days_held > 365 else "short-term"
        except Exception:
            return "unknown"
    
    def _add_violation(
        self,
        invariant_type: InvariantType,
        asset: str,
        severity: str,
        message: str,
        details: Dict
    ):
        """Record an invariant violation"""
        violation = InvariantViolation(
            violation_id=str(uuid.uuid4()),
            invariant_type=invariant_type,
            asset=asset,
            severity=severity,
            message=message,
            details=details
        )
        self.violations.append(violation)
        
        logger.warning(f"INVARIANT VIOLATION [{invariant_type.value}]: {message}")
        
        if severity == "error":
            self.account_tax_state_valid = False
    
    def _log_audit(self, action: str, tx_id: Optional[str], details: Dict):
        """Log action to audit trail"""
        entry = {
            "audit_id": str(uuid.uuid4()),
            "action": action,
            "tx_id": tx_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details
        }
        self.audit_trail.append(entry)
        
        # Keep audit trail bounded
        if len(self.audit_trail) > 10000:
            self.audit_trail = self.audit_trail[-5000:]
    
    def get_audit_trail(self, limit: int = 100) -> List[Dict]:
        """Get recent audit trail entries"""
        return self.audit_trail[-limit:]
    
    def get_lot_status(self, asset: str) -> Dict:
        """Get current lot status for an asset"""
        asset_upper = asset.upper()
        
        if asset_upper not in self.lots_by_asset:
            return {"asset": asset, "lots": [], "total_quantity": 0, "total_cost_basis": 0}
        
        lots = self.lots_by_asset[asset_upper]
        
        return {
            "asset": asset,
            "lots": [lot.to_dict() for lot in lots],
            "total_quantity": float(sum(lot.remaining_quantity for lot in lots)),
            "total_cost_basis": float(sum(lot.remaining_quantity * lot.cost_basis_per_unit for lot in lots)),
            "fully_disposed_lots": len([lot for lot in lots if lot.is_disposed]),
            "partial_lots": len([lot for lot in lots if not lot.is_disposed and lot.remaining_quantity < lot.quantity])
        }
    
    def is_account_tax_state_valid(self) -> bool:
        """Check if account is in a valid tax state for export"""
        return self.account_tax_state_valid


# Singleton instance
tax_validation_service = TaxValidationService()
