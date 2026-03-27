"""
Regression Fixture System for Validated Accounts

Creates point-in-time snapshots of validated accounts for regression testing.
Ensures reproducibility by capturing:
- Raw transactions
- Normalized transfers
- Wallet linkage state
- Tax lots and disposals
- Validation state
- Final Form 8949 dataset

Automated tests can re-run the full pipeline and compare results.
"""

import logging
import uuid
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from decimal import Decimal

logger = logging.getLogger(__name__)


@dataclass
class FixtureMetadata:
    """Metadata for a regression fixture"""
    fixture_id: str
    version_tag: str  # e.g., "golden_account_v1"
    user_id: str
    created_at: str
    description: str
    
    # Snapshot counts for quick validation
    transaction_count: int = 0
    transfer_count: int = 0
    linkage_count: int = 0
    tax_lot_count: int = 0
    disposal_count: int = 0
    
    # Summary metrics for comparison
    total_proceeds: float = 0.0
    total_cost_basis: float = 0.0
    total_gain_loss: float = 0.0
    validation_status: str = "unknown"
    can_export: bool = False
    
    # Integrity hash for detecting tampering
    content_hash: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FixtureSnapshot:
    """Complete snapshot of account state"""
    metadata: FixtureMetadata
    
    # Raw data snapshots
    raw_transactions: List[Dict] = field(default_factory=list)
    normalized_transfers: List[Dict] = field(default_factory=list)
    wallet_linkages: List[Dict] = field(default_factory=list)
    tax_lots: List[Dict] = field(default_factory=list)
    tax_disposals: List[Dict] = field(default_factory=list)
    validation_state: Dict = field(default_factory=dict)
    form_8949_dataset: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "metadata": self.metadata.to_dict(),
            "raw_transactions": self.raw_transactions,
            "normalized_transfers": self.normalized_transfers,
            "wallet_linkages": self.wallet_linkages,
            "tax_lots": self.tax_lots,
            "tax_disposals": self.tax_disposals,
            "validation_state": self.validation_state,
            "form_8949_dataset": self.form_8949_dataset
        }


@dataclass
class RegressionTestResult:
    """Result of regression test comparison"""
    passed: bool
    fixture_id: str
    version_tag: str
    test_timestamp: str
    
    # Comparison details
    disposal_count_match: bool = True
    proceeds_match: bool = True
    cost_basis_match: bool = True
    gain_loss_match: bool = True
    validation_status_match: bool = True
    can_export_match: bool = True
    
    # Actual vs expected
    expected_disposal_count: int = 0
    actual_disposal_count: int = 0
    expected_proceeds: float = 0.0
    actual_proceeds: float = 0.0
    expected_cost_basis: float = 0.0
    actual_cost_basis: float = 0.0
    expected_gain_loss: float = 0.0
    actual_gain_loss: float = 0.0
    expected_validation_status: str = ""
    actual_validation_status: str = ""
    expected_can_export: bool = False
    actual_can_export: bool = False
    
    # Detailed mismatches
    mismatches: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class RegressionFixtureService:
    """
    Service for creating and testing regression fixtures.
    
    Ensures validated accounts remain stable across code changes.
    """
    
    # Tolerance for floating point comparisons (0.01 = 1 cent)
    FLOAT_TOLERANCE = 0.01
    
    def __init__(self, db):
        self.db = db
    
    async def create_fixture(
        self,
        user_id: str,
        version_tag: str,
        description: str = ""
    ) -> FixtureSnapshot:
        """
        Create a regression fixture for a validated account.
        
        Captures complete point-in-time state for regression testing.
        """
        fixture_id = str(uuid.uuid4())
        
        # Capture raw transactions
        raw_transactions = await self._get_raw_transactions(user_id)
        
        # Capture normalized transfers (sends/receives with chain_status)
        normalized_transfers = await self._get_normalized_transfers(user_id)
        
        # Capture wallet linkages
        wallet_linkages = await self._get_wallet_linkages(user_id)
        
        # Capture tax lots
        tax_lots = await self._get_tax_lots(user_id)
        
        # Capture tax disposals
        tax_disposals = await self._get_tax_disposals(user_id)
        
        # Capture validation state
        validation_state = await self._get_validation_state(user_id)
        
        # Generate Form 8949 dataset
        form_8949_dataset = await self._get_form_8949_dataset(user_id)
        
        # Calculate summary metrics
        total_proceeds = sum(d.get("proceeds", 0) or 0 for d in form_8949_dataset)
        total_cost_basis = sum(d.get("cost_basis", 0) or 0 for d in form_8949_dataset)
        total_gain_loss = sum(d.get("gain_loss", 0) or 0 for d in form_8949_dataset)
        
        # Create metadata
        metadata = FixtureMetadata(
            fixture_id=fixture_id,
            version_tag=version_tag,
            user_id=user_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            description=description,
            transaction_count=len(raw_transactions),
            transfer_count=len(normalized_transfers),
            linkage_count=len(wallet_linkages),
            tax_lot_count=len(tax_lots),
            disposal_count=len(tax_disposals),
            total_proceeds=round(total_proceeds, 2),
            total_cost_basis=round(total_cost_basis, 2),
            total_gain_loss=round(total_gain_loss, 2),
            validation_status=validation_state.get("validation_status", "unknown"),
            can_export=validation_state.get("can_export", False)
        )
        
        # Create snapshot
        snapshot = FixtureSnapshot(
            metadata=metadata,
            raw_transactions=raw_transactions,
            normalized_transfers=normalized_transfers,
            wallet_linkages=wallet_linkages,
            tax_lots=tax_lots,
            tax_disposals=tax_disposals,
            validation_state=validation_state,
            form_8949_dataset=form_8949_dataset
        )
        
        # Calculate content hash for integrity
        content = json.dumps(snapshot.to_dict(), sort_keys=True, default=str)
        metadata.content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        
        # Store fixture
        await self._store_fixture(snapshot)
        
        return snapshot
    
    async def run_regression_test(
        self,
        fixture_id: str,
        recompute: bool = True
    ) -> RegressionTestResult:
        """
        Run regression test against a stored fixture.
        
        Re-runs the full pipeline and compares results.
        """
        # Load fixture
        fixture = await self._load_fixture(fixture_id)
        if not fixture:
            raise ValueError(f"Fixture {fixture_id} not found")
        
        user_id = fixture.metadata.user_id
        
        # Optionally trigger recompute
        if recompute:
            await self._trigger_recompute(user_id)
        
        # Get current state
        current_validation = await self._get_validation_state(user_id)
        current_8949 = await self._get_form_8949_dataset(user_id)
        current_disposals = await self._get_tax_disposals(user_id)
        
        # Calculate current metrics
        actual_proceeds = sum(d.get("proceeds", 0) or 0 for d in current_8949)
        actual_cost_basis = sum(d.get("cost_basis", 0) or 0 for d in current_8949)
        actual_gain_loss = sum(d.get("gain_loss", 0) or 0 for d in current_8949)
        
        # Create result
        result = RegressionTestResult(
            passed=True,
            fixture_id=fixture_id,
            version_tag=fixture.metadata.version_tag,
            test_timestamp=datetime.now(timezone.utc).isoformat(),
            
            expected_disposal_count=fixture.metadata.disposal_count,
            actual_disposal_count=len(current_disposals),
            expected_proceeds=fixture.metadata.total_proceeds,
            actual_proceeds=round(actual_proceeds, 2),
            expected_cost_basis=fixture.metadata.total_cost_basis,
            actual_cost_basis=round(actual_cost_basis, 2),
            expected_gain_loss=fixture.metadata.total_gain_loss,
            actual_gain_loss=round(actual_gain_loss, 2),
            expected_validation_status=fixture.metadata.validation_status,
            actual_validation_status=current_validation.get("validation_status", "unknown"),
            expected_can_export=fixture.metadata.can_export,
            actual_can_export=current_validation.get("can_export", False)
        )
        
        # Compare values
        if result.expected_disposal_count != result.actual_disposal_count:
            result.disposal_count_match = False
            result.passed = False
            result.mismatches.append(
                f"Disposal count mismatch: expected {result.expected_disposal_count}, got {result.actual_disposal_count}"
            )
        
        if abs(result.expected_proceeds - result.actual_proceeds) > self.FLOAT_TOLERANCE:
            result.proceeds_match = False
            result.passed = False
            result.mismatches.append(
                f"Proceeds mismatch: expected ${result.expected_proceeds:.2f}, got ${result.actual_proceeds:.2f}"
            )
        
        if abs(result.expected_cost_basis - result.actual_cost_basis) > self.FLOAT_TOLERANCE:
            result.cost_basis_match = False
            result.passed = False
            result.mismatches.append(
                f"Cost basis mismatch: expected ${result.expected_cost_basis:.2f}, got ${result.actual_cost_basis:.2f}"
            )
        
        if abs(result.expected_gain_loss - result.actual_gain_loss) > self.FLOAT_TOLERANCE:
            result.gain_loss_match = False
            result.passed = False
            result.mismatches.append(
                f"Gain/loss mismatch: expected ${result.expected_gain_loss:.2f}, got ${result.actual_gain_loss:.2f}"
            )
        
        if result.expected_validation_status != result.actual_validation_status:
            result.validation_status_match = False
            result.passed = False
            result.mismatches.append(
                f"Validation status mismatch: expected '{result.expected_validation_status}', got '{result.actual_validation_status}'"
            )
        
        if result.expected_can_export != result.actual_can_export:
            result.can_export_match = False
            result.passed = False
            result.mismatches.append(
                f"can_export mismatch: expected {result.expected_can_export}, got {result.actual_can_export}"
            )
        
        # Store test result
        await self._store_test_result(result)
        
        return result
    
    async def list_fixtures(self, user_id: Optional[str] = None) -> List[Dict]:
        """List all fixtures, optionally filtered by user_id"""
        query = {}
        if user_id:
            query["metadata.user_id"] = user_id
        
        fixtures = await self.db.regression_fixtures.find(
            query,
            {"metadata": 1}
        ).to_list(1000)
        
        return [f["metadata"] for f in fixtures]
    
    async def delete_fixture(self, fixture_id: str) -> bool:
        """Delete a fixture"""
        result = await self.db.regression_fixtures.delete_one({"metadata.fixture_id": fixture_id})
        return result.deleted_count > 0
    
    # === PRIVATE METHODS ===
    
    async def _get_raw_transactions(self, user_id: str) -> List[Dict]:
        """Get all raw transactions for user"""
        transactions = await self.db.exchange_transactions.find(
            {"user_id": user_id},
            {"_id": 0}
        ).to_list(100000)
        return transactions
    
    async def _get_normalized_transfers(self, user_id: str) -> List[Dict]:
        """Get normalized transfers (sends/receives)"""
        transfers = await self.db.exchange_transactions.find(
            {
                "user_id": user_id,
                "tx_type": {"$in": ["send", "receive", "transfer"]}
            },
            {"_id": 0}
        ).to_list(100000)
        return transfers
    
    async def _get_wallet_linkages(self, user_id: str) -> List[Dict]:
        """Get wallet linkage edges"""
        linkages = await self.db.linkage_edges.find(
            {"user_id": user_id},
            {"_id": 0}
        ).to_list(10000)
        return linkages
    
    async def _get_tax_lots(self, user_id: str) -> List[Dict]:
        """Get tax lots"""
        lots = await self.db.tax_lots.find(
            {"user_id": user_id},
            {"_id": 0}
        ).to_list(100000)
        return lots
    
    async def _get_tax_disposals(self, user_id: str) -> List[Dict]:
        """Get tax disposals"""
        disposals = await self.db.tax_disposals.find(
            {"user_id": user_id},
            {"_id": 0}
        ).to_list(100000)
        return disposals
    
    async def _get_validation_state(self, user_id: str) -> Dict:
        """Get current validation state"""
        try:
            from beta_validation_harness import BetaValidationHarness
            harness = BetaValidationHarness(self.db)
            report = await harness.validate_user_account(user_id)
            return {
                "validation_status": report.get("validation_status", "unknown"),
                "can_export": report.get("can_export", False),
                "blocking_issues_count": len([
                    i for i in report.get("issues", [])
                    if i.get("severity") in ["critical", "high"]
                ]),
                "issues": report.get("issues", [])
            }
        except Exception as e:
            logger.warning(f"Could not get validation state: {e}")
            return {"validation_status": "unknown", "can_export": False}
    
    async def _get_form_8949_dataset(self, user_id: str) -> List[Dict]:
        """Generate Form 8949 dataset"""
        try:
            from exchange_tax_service import exchange_tax_service
            events = await exchange_tax_service.calculate_tax_events(user_id, self.db)
            
            # Convert to 8949 format
            dataset = []
            for event in events:
                if event.get("type") in ["sell", "disposal", "external_transfer"]:
                    dataset.append({
                        "asset": event.get("asset"),
                        "quantity": event.get("quantity", 0),
                        "date_acquired": event.get("acquisition_date"),
                        "date_sold": event.get("disposal_date") or event.get("timestamp"),
                        "proceeds": event.get("proceeds", 0) or event.get("total_usd", 0),
                        "cost_basis": event.get("cost_basis", 0),
                        "gain_loss": event.get("gain_loss", 0),
                        "term": event.get("term", "short")
                    })
            return dataset
        except Exception as e:
            logger.warning(f"Could not generate Form 8949 dataset: {e}")
            return []
    
    async def _store_fixture(self, snapshot: FixtureSnapshot):
        """Store fixture in database"""
        await self.db.regression_fixtures.replace_one(
            {"metadata.fixture_id": snapshot.metadata.fixture_id},
            snapshot.to_dict(),
            upsert=True
        )
    
    async def _load_fixture(self, fixture_id: str) -> Optional[FixtureSnapshot]:
        """Load fixture from database"""
        doc = await self.db.regression_fixtures.find_one(
            {"metadata.fixture_id": fixture_id},
            {"_id": 0}
        )
        if not doc:
            return None
        
        metadata = FixtureMetadata(**doc["metadata"])
        return FixtureSnapshot(
            metadata=metadata,
            raw_transactions=doc.get("raw_transactions", []),
            normalized_transfers=doc.get("normalized_transfers", []),
            wallet_linkages=doc.get("wallet_linkages", []),
            tax_lots=doc.get("tax_lots", []),
            tax_disposals=doc.get("tax_disposals", []),
            validation_state=doc.get("validation_state", {}),
            form_8949_dataset=doc.get("form_8949_dataset", [])
        )
    
    async def _trigger_recompute(self, user_id: str):
        """Trigger full recompute for user"""
        try:
            from recompute_service import RecomputeService
            service = RecomputeService(self.db)
            await service.full_recompute(user_id)
        except Exception as e:
            logger.warning(f"Could not trigger recompute: {e}")
    
    async def _store_test_result(self, result: RegressionTestResult):
        """Store test result in database"""
        await self.db.regression_test_results.insert_one(result.to_dict())
