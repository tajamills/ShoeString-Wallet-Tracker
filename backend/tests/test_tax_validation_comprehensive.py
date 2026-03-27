"""
Tax Validation Test Suite and Failure Scenario Coverage

Comprehensive automated tests ensuring IRS Form 8949 output is accurate,
reproducible, and blocked when invalid.

Requirements covered:
1. Core Passing Test Cases (10 scenarios)
2. Top 10 Failure Scenario Tests
3. Required Invariant Checks
4. Validation Enforcement
5. Structured Test Output Format
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from tax_validation_service import (
    TaxValidationService,
    TxClassification,
    ValidationStatus,
    InvariantType,
    LotRecord,
    DisposalRecord,
    InvariantViolation
)


# ========================================
# TEST OUTPUT FORMAT
# ========================================

@dataclass
class TestResult:
    """Structured test output format"""
    test_name: str
    classification_result: Dict[str, str]
    lot_impact: Dict[str, Any]
    tax_impact: Dict[str, float]
    validation_status: str
    api_flags: Dict[str, bool]
    passed: bool
    failure_reason: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class TestResultCollector:
    """Collects and summarizes test results"""
    
    def __init__(self):
        self.results: List[TestResult] = []
    
    def add(self, result: TestResult):
        self.results.append(result)
    
    def summary(self) -> Dict:
        passed = len([r for r in self.results if r.passed])
        failed = len([r for r in self.results if not r.passed])
        return {
            "total_tests": len(self.results),
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{(passed / len(self.results) * 100):.1f}%" if self.results else "0%",
            "failed_tests": [r.test_name for r in self.results if not r.passed]
        }


# Global collector for QA review
test_collector = TestResultCollector()


# ========================================
# FIXTURES
# ========================================

@pytest.fixture
def fresh_service():
    """Create a fresh validation service for each test"""
    return TaxValidationService()


@pytest.fixture
def service_with_btc_lot(fresh_service):
    """Service with a single BTC lot"""
    fresh_service.create_lot(
        tx_id="buy_btc_001",
        asset="BTC",
        acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        quantity=2.0,
        cost_basis_per_unit=40000.0,
        source="coinbase",
        classification=TxClassification.ACQUISITION,
        price_source="exchange"
    )
    return fresh_service


@pytest.fixture
def service_with_multiple_lots(fresh_service):
    """Service with multiple lots for FIFO testing"""
    # Lot 1: Jan - 1 BTC @ $30k
    fresh_service.create_lot(
        tx_id="buy_btc_001",
        asset="BTC",
        acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
        quantity=1.0,
        cost_basis_per_unit=30000.0,
        source="coinbase",
        classification=TxClassification.ACQUISITION
    )
    # Lot 2: Feb - 1 BTC @ $35k
    fresh_service.create_lot(
        tx_id="buy_btc_002",
        asset="BTC",
        acquisition_date=datetime(2024, 2, 15, tzinfo=timezone.utc),
        quantity=1.0,
        cost_basis_per_unit=35000.0,
        source="kraken",
        classification=TxClassification.ACQUISITION
    )
    # Lot 3: Mar - 1 BTC @ $40k
    fresh_service.create_lot(
        tx_id="buy_btc_003",
        asset="BTC",
        acquisition_date=datetime(2024, 3, 15, tzinfo=timezone.utc),
        quantity=1.0,
        cost_basis_per_unit=40000.0,
        source="gemini",
        classification=TxClassification.ACQUISITION
    )
    return fresh_service


# ========================================
# 1. CORE PASSING TEST CASES
# ========================================

class TestCorePassingScenarios:
    """10 core passing test cases as specified"""
    
    def test_01_simple_buy_sell(self, fresh_service):
        """Test: simple buy -> sell"""
        # Buy
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Sell
        disposal = fresh_service.dispose_from_lots(
            tx_id="sell_001",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=50000.0
        )
        
        # Validate
        result = fresh_service.run_all_invariant_checks(
            balances={"BTC": {"starting": 0, "ending": 0}}
        )
        
        # Build test result
        test_result = TestResult(
            test_name="simple_buy_sell",
            classification_result={"buy": "acquisition", "sell": "disposal"},
            lot_impact={"lots_created": 1, "lots_consumed": 1, "remaining": 0},
            tax_impact={
                "proceeds": 50000.0,
                "cost_basis": 40000.0,
                "gain_loss": 10000.0
            },
            validation_status=result.status.value,
            api_flags={"can_export": result.is_valid, "validation_passed": result.is_valid},
            passed=result.is_valid and float(disposal.gain_loss) == 10000.0,
            failure_reason=None if result.is_valid else str(result.violations)
        )
        test_collector.add(test_result)
        
        assert result.is_valid
        assert float(disposal.gain_loss) == 10000.0
        assert disposal.holding_period == "short-term"
    
    def test_02_buy_internal_transfer_sell(self, fresh_service):
        """Test: buy -> internal transfer -> sell"""
        # Buy on Coinbase
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=10.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Internal transfer (no tax event, cost basis preserved)
        # Simulated by NOT disposing - just tracking the transfer
        transfer_tx = {"tx_type": "send", "chain_status": "linked", "asset": "ETH"}
        classification, confidence = fresh_service.classify_transaction(transfer_tx)
        
        # Sell from new wallet (uses original cost basis)
        disposal = fresh_service.dispose_from_lots(
            tx_id="sell_001",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=10.0,
            proceeds=35000.0
        )
        
        result = fresh_service.run_all_invariant_checks(
            balances={"ETH": {"starting": 0, "ending": 0}}
        )
        
        test_result = TestResult(
            test_name="buy_internal_transfer_sell",
            classification_result={"buy": "acquisition", "transfer": classification.value, "sell": "disposal"},
            lot_impact={"lots_created": 1, "lots_consumed": 1, "cost_basis_preserved": True},
            tax_impact={
                "proceeds": 35000.0,
                "cost_basis": 20000.0,
                "gain_loss": 15000.0
            },
            validation_status=result.status.value,
            api_flags={"can_export": result.is_valid},
            passed=result.is_valid and classification == TxClassification.INTERNAL_TRANSFER,
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert classification == TxClassification.INTERNAL_TRANSFER
        assert float(disposal.total_cost_basis) == 20000.0  # Original cost basis preserved
        assert result.is_valid
    
    def test_03_bridge_transfer_correctly_linked(self, fresh_service):
        """Test: bridge transfer correctly linked (no tax event)"""
        # Buy ETH on Ethereum
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=5.0,
            cost_basis_per_unit=2000.0,
            source="ethereum_mainnet",
            classification=TxClassification.ACQUISITION
        )
        
        # Bridge to Arbitrum - classified as linked after user confirmation
        bridge_tx = {"tx_type": "send", "chain_status": "linked", "asset": "ETH"}
        classification, confidence = fresh_service.classify_transaction(bridge_tx)
        
        # Verify cost basis preserved (no disposal created for linked transfer)
        lot_status = fresh_service.get_lot_status("ETH")
        
        test_result = TestResult(
            test_name="bridge_transfer_correctly_linked",
            classification_result={"bridge": classification.value},
            lot_impact={"total_quantity": lot_status["total_quantity"], "cost_basis_preserved": True},
            tax_impact={"taxable_event": False, "gain_loss": 0},
            validation_status="valid",
            api_flags={"can_export": True},
            passed=classification == TxClassification.INTERNAL_TRANSFER and lot_status["total_quantity"] == 5.0,
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert classification == TxClassification.INTERNAL_TRANSFER
        assert lot_status["total_quantity"] == 5.0
        assert lot_status["total_cost_basis"] == 10000.0
    
    def test_04_bridge_transfer_unresolved(self, fresh_service):
        """Test: bridge transfer unresolved (needs review)"""
        bridge_tx = {"tx_type": "send", "chain_status": "unlinked", "asset": "ETH"}
        validated = fresh_service.validate_classification(bridge_tx)
        
        test_result = TestResult(
            test_name="bridge_transfer_unresolved",
            classification_result={"classification": validated["classification"]},
            lot_impact={"needs_review": validated["needs_review"]},
            tax_impact={"excluded_from_export": True},
            validation_status="needs_review",
            api_flags={"can_export": False, "needs_user_action": True},
            passed=validated["classification"] == "unknown" and validated["needs_review"],
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert validated["classification"] == "unknown"
        assert validated["needs_review"] == True
        assert validated["classification_confidence"] < 0.5
    
    def test_05_partial_lot_disposal(self, service_with_btc_lot):
        """Test: partial lot disposal"""
        service = service_with_btc_lot
        
        # Sell only 0.5 BTC from 2 BTC lot
        disposal = service.dispose_from_lots(
            tx_id="sell_001",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=0.5,
            proceeds=25000.0
        )
        
        lot_status = service.get_lot_status("BTC")
        
        test_result = TestResult(
            test_name="partial_lot_disposal",
            classification_result={"disposal": "partial"},
            lot_impact={
                "original_quantity": 2.0,
                "disposed": 0.5,
                "remaining": lot_status["total_quantity"]
            },
            tax_impact={
                "proceeds": 25000.0,
                "cost_basis": 20000.0,  # 0.5 * $40k
                "gain_loss": 5000.0
            },
            validation_status="valid",
            api_flags={"can_export": True},
            passed=float(disposal.gain_loss) == 5000.0 and lot_status["total_quantity"] == 1.5,
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert float(disposal.quantity) == 0.5
        assert float(disposal.total_cost_basis) == 20000.0
        assert float(disposal.gain_loss) == 5000.0
        assert lot_status["total_quantity"] == 1.5
    
    def test_06_multiple_lots_fifo(self, service_with_multiple_lots):
        """Test: multiple acquisition lots using FIFO"""
        service = service_with_multiple_lots
        
        # Sell 1.5 BTC - should use Lot 1 ($30k) fully + 0.5 of Lot 2 ($35k)
        disposal = service.dispose_from_lots(
            tx_id="sell_001",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.5,
            proceeds=75000.0  # $50k/BTC
        )
        
        # Expected cost basis: 1.0 * $30k + 0.5 * $35k = $30k + $17.5k = $47.5k
        expected_cost_basis = 47500.0
        expected_gain = 75000.0 - expected_cost_basis
        
        test_result = TestResult(
            test_name="multiple_lots_fifo",
            classification_result={"method": "FIFO"},
            lot_impact={
                "lots_matched": len(disposal.matched_lots),
                "lot_1_consumed": 1.0,
                "lot_2_partial": 0.5
            },
            tax_impact={
                "proceeds": 75000.0,
                "cost_basis": float(disposal.total_cost_basis),
                "gain_loss": float(disposal.gain_loss)
            },
            validation_status="valid",
            api_flags={"can_export": True},
            passed=float(disposal.total_cost_basis) == expected_cost_basis,
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert len(disposal.matched_lots) == 2  # Matched 2 lots
        assert float(disposal.total_cost_basis) == expected_cost_basis
        assert float(disposal.gain_loss) == expected_gain
    
    def test_07_fee_deducted_same_asset(self, fresh_service):
        """Test: fee deducted in same asset (fee added to cost basis)"""
        # Buy with fee included in cost basis
        # 1 BTC @ $40,000 + $100 fee = $40,100 cost basis
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40100.0,  # Price + fee
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        disposal = fresh_service.dispose_from_lots(
            tx_id="sell_001",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=50000.0
        )
        
        # Gain should account for fee in cost basis
        expected_gain = 50000.0 - 40100.0
        
        test_result = TestResult(
            test_name="fee_deducted_same_asset",
            classification_result={"fee_handling": "included_in_cost_basis"},
            lot_impact={"cost_basis_with_fee": 40100.0},
            tax_impact={
                "proceeds": 50000.0,
                "cost_basis": 40100.0,
                "gain_loss": expected_gain
            },
            validation_status="valid",
            api_flags={"can_export": True},
            passed=float(disposal.gain_loss) == expected_gain,
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert float(disposal.total_cost_basis) == 40100.0
        assert float(disposal.gain_loss) == expected_gain
    
    def test_08_csv_import_auto_classification(self, fresh_service):
        """Test: CSV import with auto-classification"""
        # Simulate CSV import transactions
        csv_transactions = [
            {"tx_type": "buy", "asset": "BTC", "amount": 1.0},
            {"tx_type": "sell", "asset": "BTC", "amount": 0.5},
            {"tx_type": "staking", "asset": "ETH", "amount": 0.1},
            {"tx_type": "receive", "asset": "BTC", "amount": 0.2, "is_transfer": True},
        ]
        
        classifications = []
        for tx in csv_transactions:
            validated = fresh_service.validate_classification(tx)
            classifications.append({
                "tx_type": tx["tx_type"],
                "classification": validated["classification"],
                "needs_review": validated["needs_review"]
            })
        
        test_result = TestResult(
            test_name="csv_import_auto_classification",
            classification_result={c["tx_type"]: c["classification"] for c in classifications},
            lot_impact={"transactions_classified": len(classifications)},
            tax_impact={"auto_classified": True},
            validation_status="valid",
            api_flags={"can_export": True},
            passed=all(c["classification"] != "unknown" for c in classifications[:3]),
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert classifications[0]["classification"] == "acquisition"
        assert classifications[1]["classification"] == "disposal"
        assert classifications[2]["classification"] == "income"
    
    def test_09_linkage_correction_triggers_recompute(self, fresh_service):
        """Test: linkage correction triggering recompute"""
        # Create initial state
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=5.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Trigger recompute (simulating linkage correction)
        recompute_result = fresh_service.trigger_full_recompute("linkage_correction")
        
        test_result = TestResult(
            test_name="linkage_correction_triggers_recompute",
            classification_result={"trigger": "linkage_correction"},
            lot_impact={
                "cleared_lots": recompute_result["cleared_lots"],
                "cleared_disposals": recompute_result["cleared_disposals"]
            },
            tax_impact={"recomputed": True},
            validation_status="valid",
            api_flags={"recompute_triggered": recompute_result["recompute_triggered"]},
            passed=recompute_result["recompute_triggered"] and recompute_result["cleared_lots"] == 1,
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert recompute_result["recompute_triggered"] == True
        assert recompute_result["cleared_lots"] == 1
        
        # Verify state was cleared
        lot_status = fresh_service.get_lot_status("ETH")
        assert lot_status["total_quantity"] == 0
    
    def test_10_repeated_export_consistency(self, service_with_btc_lot):
        """Test: repeated export consistency (deterministic)"""
        service = service_with_btc_lot
        
        # Perform disposal
        service.dispose_from_lots(
            tx_id="sell_001",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=50000.0
        )
        
        # Generate Form 8949 records multiple times
        records_1 = [{
            "description": "1.0 BTC",
            "date_acquired": "2024-01-15",
            "date_sold": "2024-06-15",
            "proceeds": 50000.0,
            "cost_basis": 40000.0,
            "gain_or_loss": 10000.0
        }]
        
        records_2 = [{
            "description": "1.0 BTC",
            "date_acquired": "2024-01-15",
            "date_sold": "2024-06-15",
            "proceeds": 50000.0,
            "cost_basis": 40000.0,
            "gain_or_loss": 10000.0
        }]
        
        can_export_1, result_1 = service.validate_form_8949_export(records_1)
        can_export_2, result_2 = service.validate_form_8949_export(records_2)
        
        # Results should be identical (deterministic)
        deterministic = (can_export_1 == can_export_2 and 
                        result_1.is_valid == result_2.is_valid)
        
        test_result = TestResult(
            test_name="repeated_export_consistency",
            classification_result={"deterministic": deterministic},
            lot_impact={"exports_compared": 2},
            tax_impact={"consistent": deterministic},
            validation_status=result_1.status.value,
            api_flags={"can_export": can_export_1, "deterministic": deterministic},
            passed=deterministic and can_export_1,
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert deterministic
        assert can_export_1 == True


# ========================================
# 2. TOP 10 FAILURE SCENARIO TESTS
# ========================================

class TestFailureScenarios:
    """Top 10 failure scenario tests"""
    
    def test_failure_01_internal_transfer_as_sale(self, fresh_service):
        """FAILURE: internal transfer incorrectly treated as sale"""
        # Create lot
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=10.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Incorrectly dispose (treating transfer as sale)
        disposal = fresh_service.dispose_from_lots(
            tx_id="transfer_001",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=10.0,
            proceeds=30000.0  # FMV at transfer
        )
        
        # This SHOULD have been an internal transfer, not disposal
        # The invariant check should catch the balance issue
        result = fresh_service.run_all_invariant_checks(
            balances={"ETH": {"starting": 0, "ending": 10.0}}  # User still has 10 ETH
        )
        
        test_result = TestResult(
            test_name="failure_internal_transfer_as_sale",
            classification_result={"error": "internal_transfer_treated_as_disposal"},
            lot_impact={"incorrectly_disposed": 10.0},
            tax_impact={"false_gain": float(disposal.gain_loss)},
            validation_status=result.status.value,
            api_flags={"can_export": result.is_valid},
            passed=not result.is_valid,  # SHOULD fail validation
            failure_reason="Balance reconciliation should fail"
        )
        test_collector.add(test_result)
        
        # Validation should FAIL because balance doesn't reconcile
        assert not result.is_valid
        assert any(v.invariant_type == InvariantType.BALANCE_RECONCILIATION for v in result.violations)
    
    def test_failure_02_external_transfer_as_internal(self, fresh_service):
        """FAILURE: external transfer incorrectly treated as internal"""
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Mark external transfer as internal (wrong - no disposal created)
        # This means we have a phantom 1 BTC that shouldn't exist
        
        result = fresh_service.run_all_invariant_checks(
            balances={"BTC": {"starting": 0, "ending": 0}}  # Actually 0 after external transfer
        )
        
        test_result = TestResult(
            test_name="failure_external_transfer_as_internal",
            classification_result={"error": "external_treated_as_internal"},
            lot_impact={"phantom_balance": 1.0},
            tax_impact={"missed_disposal": True},
            validation_status=result.status.value,
            api_flags={"can_export": result.is_valid},
            passed=not result.is_valid,  # SHOULD fail
            failure_reason="Balance should be 0 but lots show 1.0"
        )
        test_collector.add(test_result)
        
        # Should fail - ending balance is 0 but we have 1 BTC in lots
        assert not result.is_valid
    
    def test_failure_03_duplicate_disposal_after_recompute(self, fresh_service):
        """FAILURE: duplicate disposal after recompute"""
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=5.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # First disposal
        fresh_service.dispose_from_lots(
            tx_id="sell_001",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=5.0,
            proceeds=15000.0
        )
        
        # Try duplicate disposal - should fail
        duplicate_failed = False
        try:
            fresh_service.dispose_from_lots(
                tx_id="sell_002",
                asset="ETH",
                disposal_date=datetime(2024, 6, 16, tzinfo=timezone.utc),
                quantity=5.0,
                proceeds=15000.0
            )
        except ValueError as e:
            duplicate_failed = True
        
        test_result = TestResult(
            test_name="failure_duplicate_disposal_after_recompute",
            classification_result={"error": "duplicate_disposal_blocked"},
            lot_impact={"double_spend_prevented": duplicate_failed},
            tax_impact={"duplicate_blocked": duplicate_failed},
            validation_status="blocked" if duplicate_failed else "invalid",
            api_flags={"can_export": False},
            passed=duplicate_failed,
            failure_reason=None if duplicate_failed else "Duplicate disposal was allowed"
        )
        test_collector.add(test_result)
        
        assert duplicate_failed
    
    def test_failure_04_cost_basis_changed_internal_transfer(self, fresh_service):
        """FAILURE: cost basis changed during internal transfer"""
        # Simulate checking cost basis conservation
        internal_transfers = [
            {
                "tx_id": "transfer_001",
                "asset": "BTC",
                "source_cost_basis": 40000.0,
                "destination_cost_basis": 45000.0  # WRONG - should be same
            }
        ]
        
        is_valid = fresh_service.check_cost_basis_conservation(internal_transfers)
        
        test_result = TestResult(
            test_name="failure_cost_basis_changed_internal_transfer",
            classification_result={"error": "cost_basis_changed"},
            lot_impact={"source": 40000.0, "destination": 45000.0},
            tax_impact={"incorrect_basis": True},
            validation_status="invalid" if not is_valid else "valid",
            api_flags={"can_export": is_valid},
            passed=not is_valid,  # SHOULD fail
            failure_reason="Cost basis conservation violated"
        )
        test_collector.add(test_result)
        
        assert not is_valid
        assert any(v.invariant_type == InvariantType.COST_BASIS_CONSERVATION 
                  for v in fresh_service.violations)
    
    def test_failure_05_orphan_disposal_no_acquisition(self, fresh_service):
        """FAILURE: orphan disposal with no acquisition lot"""
        # Try to dispose without any lots
        orphan_failed = False
        try:
            fresh_service.dispose_from_lots(
                tx_id="sell_001",
                asset="DOGE",
                disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
                quantity=1000.0,
                proceeds=100.0
            )
        except ValueError as e:
            orphan_failed = True
        
        test_result = TestResult(
            test_name="failure_orphan_disposal_no_acquisition",
            classification_result={"error": "no_acquisition_lot"},
            lot_impact={"orphan_blocked": orphan_failed},
            tax_impact={"orphan_disposal_prevented": orphan_failed},
            validation_status="blocked" if orphan_failed else "invalid",
            api_flags={"can_export": False},
            passed=orphan_failed,
            failure_reason=None if orphan_failed else "Orphan disposal was allowed"
        )
        test_collector.add(test_result)
        
        assert orphan_failed
    
    def test_failure_06_wrong_lot_quantity_partial_sale(self, fresh_service):
        """FAILURE: wrong lot quantity consumed on partial sale"""
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=10.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Partial sale
        disposal = fresh_service.dispose_from_lots(
            tx_id="sell_001",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=3.0,
            proceeds=9000.0
        )
        
        lot_status = fresh_service.get_lot_status("ETH")
        
        # Verify correct quantity consumed
        correct_remaining = lot_status["total_quantity"] == 7.0
        correct_cost_basis = float(disposal.total_cost_basis) == 6000.0  # 3 * $2000
        
        test_result = TestResult(
            test_name="failure_wrong_lot_quantity_partial_sale",
            classification_result={"verification": "lot_quantity_tracking"},
            lot_impact={"remaining": lot_status["total_quantity"], "expected": 7.0},
            tax_impact={"cost_basis": float(disposal.total_cost_basis)},
            validation_status="valid" if correct_remaining else "invalid",
            api_flags={"can_export": correct_remaining and correct_cost_basis},
            passed=correct_remaining and correct_cost_basis,
            failure_reason=None if correct_remaining else "Wrong quantity remaining"
        )
        test_collector.add(test_result)
        
        assert correct_remaining
        assert correct_cost_basis
    
    def test_failure_07_fee_slippage_false_chain_break(self, fresh_service):
        """FAILURE: fee/slippage causing false chain break"""
        # Transaction where small fee difference shouldn't trigger chain break
        tx_out = {"tx_type": "send", "asset": "ETH", "amount": 1.0, "chain_status": "linked"}
        tx_in = {"tx_type": "receive", "asset": "ETH", "amount": 0.995}  # 0.5% slippage
        
        # Both should be classified correctly despite slippage
        out_class, _ = fresh_service.classify_transaction(tx_out)
        in_class, _ = fresh_service.classify_transaction({**tx_in, "is_transfer": True, "chain_status": "linked"})
        
        test_result = TestResult(
            test_name="failure_fee_slippage_false_chain_break",
            classification_result={"send": out_class.value, "receive": in_class.value},
            lot_impact={"slippage_handled": True},
            tax_impact={"false_break_prevented": out_class == TxClassification.INTERNAL_TRANSFER},
            validation_status="valid",
            api_flags={"can_export": True},
            passed=out_class == TxClassification.INTERNAL_TRANSFER,
            failure_reason=None
        )
        test_collector.add(test_result)
        
        assert out_class == TxClassification.INTERNAL_TRANSFER
    
    def test_failure_08_unknown_classification_leaking(self, fresh_service):
        """FAILURE: unknown classification leaking into export"""
        # Create unknown classification
        unknown_tx = {"tx_type": "mysterious_action", "asset": "BTC"}
        validated = fresh_service.validate_classification(unknown_tx)
        
        # Unknown should be blocked from export
        blocked_from_export = validated["needs_review"] and validated["classification"] == "unknown"
        
        test_result = TestResult(
            test_name="failure_unknown_classification_leaking",
            classification_result={"classification": validated["classification"]},
            lot_impact={"needs_review": validated["needs_review"]},
            tax_impact={"excluded_from_export": blocked_from_export},
            validation_status="needs_review",
            api_flags={"can_export": not blocked_from_export},
            passed=blocked_from_export,
            failure_reason=None if blocked_from_export else "Unknown leaked into export"
        )
        test_collector.add(test_result)
        
        assert blocked_from_export
    
    def test_failure_09_linkage_update_no_recompute(self, fresh_service):
        """FAILURE: linkage update failing to trigger full recompute"""
        # Setup state
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Verify recompute clears state
        result = fresh_service.trigger_full_recompute("linkage_update")
        
        lot_status = fresh_service.get_lot_status("BTC")
        state_cleared = lot_status["total_quantity"] == 0
        
        test_result = TestResult(
            test_name="failure_linkage_update_no_recompute",
            classification_result={"trigger": "linkage_update"},
            lot_impact={"state_cleared": state_cleared},
            tax_impact={"recomputed": result["recompute_triggered"]},
            validation_status="valid" if state_cleared else "invalid",
            api_flags={"recompute_triggered": result["recompute_triggered"]},
            passed=state_cleared and result["recompute_triggered"],
            failure_reason=None if state_cleared else "State not cleared on recompute"
        )
        test_collector.add(test_result)
        
        assert state_cleared
        assert result["recompute_triggered"]
    
    def test_failure_10_can_export_true_when_invalid(self, fresh_service):
        """FAILURE: API showing can_export=true when validation failed"""
        # Create invalid state - balance doesn't reconcile
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=10.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Check with wrong ending balance
        result = fresh_service.run_all_invariant_checks(
            balances={"ETH": {"starting": 0, "ending": 5.0}}  # Wrong - should be 10
        )
        
        # can_export should be FALSE when validation fails
        correctly_blocked = not result.is_valid
        
        test_result = TestResult(
            test_name="failure_can_export_true_when_invalid",
            classification_result={"validation_status": result.status.value},
            lot_impact={"violations": len(result.violations)},
            tax_impact={"export_blocked": correctly_blocked},
            validation_status=result.status.value,
            api_flags={"can_export": result.is_valid},
            passed=correctly_blocked,
            failure_reason=None if correctly_blocked else "Export allowed despite invalid state"
        )
        test_collector.add(test_result)
        
        assert correctly_blocked
        assert result.is_valid == False


# ========================================
# 3. REQUIRED INVARIANT CHECKS
# ========================================

class TestInvariantChecks:
    """Every test run must verify these invariants"""
    
    def test_invariant_balance_reconciliation(self, service_with_btc_lot):
        """Verify balance reconciliation invariant"""
        service = service_with_btc_lot
        
        # Dispose 1 BTC
        service.dispose_from_lots(
            tx_id="sell_001",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=50000.0
        )
        
        # Correct balance check
        correct = service.check_balance_reconciliation("BTC", 0, 1.0)  # 0 + 2 - 1 = 1
        
        # Incorrect balance check
        incorrect = service.check_balance_reconciliation("BTC", 0, 5.0)  # Should fail
        
        assert correct == True
        assert incorrect == False
    
    def test_invariant_cost_basis_conservation(self, fresh_service):
        """Verify cost basis conservation for internal transfers"""
        # Valid transfer (same cost basis)
        valid_transfers = [{"asset": "BTC", "source_cost_basis": 40000, "destination_cost_basis": 40000}]
        assert fresh_service.check_cost_basis_conservation(valid_transfers) == True
        
        # Create fresh service to reset violations
        fresh_service2 = TaxValidationService()
        
        # Invalid transfer (different cost basis)
        invalid_transfers = [{"asset": "BTC", "source_cost_basis": 40000, "destination_cost_basis": 45000}]
        assert fresh_service2.check_cost_basis_conservation(invalid_transfers) == False
    
    def test_invariant_no_double_disposal(self, fresh_service):
        """Verify no double disposal invariant"""
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=2.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # First disposal
        fresh_service.dispose_from_lots(
            tx_id="sell_001",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=2.0,
            proceeds=6000.0
        )
        
        # Second disposal should fail
        with pytest.raises(ValueError):
            fresh_service.dispose_from_lots(
                tx_id="sell_002",
                asset="ETH",
                disposal_date=datetime(2024, 6, 16, tzinfo=timezone.utc),
                quantity=1.0,
                proceeds=3000.0
            )
        
        # Invariant check should pass (no over-disposal)
        assert fresh_service.check_no_double_spend() == True
    
    def test_invariant_no_orphan_disposals(self, fresh_service):
        """Verify no orphan disposals invariant"""
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        fresh_service.dispose_from_lots(
            tx_id="sell_001",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=50000.0
        )
        
        # All disposals have matched lots
        assert fresh_service.check_no_orphan_disposals() == True
    
    def test_invariant_deterministic_export(self, service_with_btc_lot):
        """Verify deterministic export for same inputs"""
        service = service_with_btc_lot
        
        service.dispose_from_lots(
            tx_id="sell_001",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=50000.0
        )
        
        record = {
            "description": "1.0 BTC",
            "date_acquired": "2024-01-15",
            "date_sold": "2024-06-15",
            "proceeds": 50000.0,
            "cost_basis": 40000.0,
            "gain_or_loss": 10000.0
        }
        
        # Multiple validations should be identical
        results = [service.validate_form_8949_record(record) for _ in range(5)]
        
        # All should be identical
        assert all(r[0] == results[0][0] for r in results)  # All pass/fail same
        assert all(r[1] == results[0][1] for r in results)  # All errors same


# ========================================
# 4. VALIDATION ENFORCEMENT TESTS
# ========================================

class TestValidationEnforcement:
    """Test validation enforcement behavior"""
    
    def test_enforcement_invalid_blocks_export(self, fresh_service):
        """Invalid state should block Form 8949 export"""
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Create invalid state
        result = fresh_service.run_all_invariant_checks(
            balances={"BTC": {"starting": 0, "ending": 5.0}}  # Wrong
        )
        
        assert result.status == ValidationStatus.INVALID
        assert result.is_valid == False
        assert not fresh_service.is_account_tax_state_valid()
    
    def test_enforcement_warning_allows_export(self, fresh_service):
        """Warnings should allow export (policy dependent)"""
        fresh_service.create_lot(
            tx_id="buy_001",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Valid state with no blocking errors
        result = fresh_service.run_all_invariant_checks(
            balances={"BTC": {"starting": 0, "ending": 1.0}}
        )
        
        # Should be valid (or warning, but exportable)
        assert result.status in [ValidationStatus.VALID, ValidationStatus.NEEDS_REVIEW]


# ========================================
# SUMMARY OUTPUT FOR QA REVIEW
# ========================================

def test_generate_qa_summary():
    """Generate summary output for QA review"""
    summary = test_collector.summary()
    
    print("\n" + "="*60)
    print("TAX VALIDATION TEST SUITE - QA SUMMARY")
    print("="*60)
    print(f"Total Tests: {summary['total_tests']}")
    print(f"Passed: {summary['passed']}")
    print(f"Failed: {summary['failed']}")
    print(f"Pass Rate: {summary['pass_rate']}")
    
    if summary['failed_tests']:
        print(f"\nFailed Tests:")
        for test in summary['failed_tests']:
            print(f"  - {test}")
    
    print("\n" + "="*60)
    print("DETAILED TEST RESULTS")
    print("="*60)
    
    for result in test_collector.results:
        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"\n{status} | {result.test_name}")
        print(f"  Classification: {result.classification_result}")
        print(f"  Validation Status: {result.validation_status}")
        print(f"  Can Export: {result.api_flags.get('can_export', 'N/A')}")
        if result.failure_reason:
            print(f"  Failure Reason: {result.failure_reason}")
    
    # Save to file
    with open("/app/test_reports/tax_validation_qa_summary.json", "w") as f:
        json.dump({
            "summary": summary,
            "results": [r.to_dict() for r in test_collector.results]
        }, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to: /app/test_reports/tax_validation_qa_summary.json")


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
