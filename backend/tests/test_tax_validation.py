"""
Tax Validation Test Suite

Comprehensive tests for the Tax Validation and Invariant Enforcement Layer.
Covers all scenarios required by the specification.
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
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
    DisposalRecord
)


class TestTransactionClassification:
    """Test transaction classification logic"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_buy_classified_as_acquisition(self):
        """Buy transactions should be classified as acquisition"""
        tx = {"tx_type": "buy", "asset": "BTC", "amount": 1.0}
        classification, confidence = self.service.classify_transaction(tx)
        assert classification == TxClassification.ACQUISITION
        assert confidence == 1.0
    
    def test_sell_classified_as_disposal(self):
        """Sell transactions should be classified as disposal"""
        tx = {"tx_type": "sell", "asset": "BTC", "amount": 1.0}
        classification, confidence = self.service.classify_transaction(tx)
        assert classification == TxClassification.DISPOSAL
        assert confidence == 1.0
    
    def test_staking_classified_as_income(self):
        """Staking rewards should be classified as income"""
        tx = {"tx_type": "staking", "asset": "ETH", "amount": 0.1}
        classification, confidence = self.service.classify_transaction(tx)
        assert classification == TxClassification.INCOME
        assert confidence == 1.0
    
    def test_airdrop_classified_as_income(self):
        """Airdrops should be classified as income"""
        tx = {"tx_type": "airdrop", "asset": "UNI", "amount": 100}
        classification, confidence = self.service.classify_transaction(tx)
        assert classification == TxClassification.INCOME
        assert confidence == 1.0
    
    def test_linked_send_classified_as_internal(self):
        """Linked sends should be classified as internal transfer"""
        tx = {"tx_type": "send", "asset": "ETH", "amount": 1.0, "chain_status": "linked"}
        classification, confidence = self.service.classify_transaction(tx)
        assert classification == TxClassification.INTERNAL_TRANSFER
        assert confidence >= 0.9
    
    def test_external_send_classified_as_disposal(self):
        """External sends should be classified as disposal"""
        tx = {"tx_type": "send", "asset": "ETH", "amount": 1.0, "chain_status": "external"}
        classification, confidence = self.service.classify_transaction(tx)
        assert classification == TxClassification.DISPOSAL
        assert confidence >= 0.9
    
    def test_unresolved_send_classified_as_unknown(self):
        """Unresolved sends should be classified as unknown"""
        tx = {"tx_type": "send", "asset": "ETH", "amount": 1.0, "chain_status": "unlinked"}
        classification, confidence = self.service.classify_transaction(tx)
        assert classification == TxClassification.UNKNOWN
        assert confidence < 0.5
    
    def test_unknown_tx_needs_review(self):
        """Unknown classifications should need review"""
        tx = {"tx_type": "unknown_type", "asset": "BTC", "amount": 1.0}
        validated = self.service.validate_classification(tx)
        assert validated["needs_review"] == True
        assert validated["classification"] == TxClassification.UNKNOWN.value


class TestCostBasisEngine:
    """Test FIFO lot tracking and cost basis calculations"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_create_lot_basic(self):
        """Test basic lot creation"""
        lot = self.service.create_lot(
            tx_id="tx1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION,
            price_source="exchange"
        )
        
        assert lot.asset == "BTC"
        assert lot.quantity == Decimal("1.0")
        assert lot.remaining_quantity == Decimal("1.0")
        assert lot.cost_basis_per_unit == Decimal("40000.0")
        assert lot.total_cost_basis == Decimal("40000.0")
    
    def test_create_lot_negative_cost_basis_fails(self):
        """Negative cost basis should raise error"""
        with pytest.raises(ValueError, match="negative"):
            self.service.create_lot(
                tx_id="tx1",
                asset="BTC",
                acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
                quantity=1.0,
                cost_basis_per_unit=-100.0,
                source="coinbase",
                classification=TxClassification.ACQUISITION
            )
    
    def test_create_lot_zero_quantity_fails(self):
        """Zero quantity should raise error"""
        with pytest.raises(ValueError, match="positive"):
            self.service.create_lot(
                tx_id="tx1",
                asset="BTC",
                acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
                quantity=0,
                cost_basis_per_unit=40000.0,
                source="coinbase",
                classification=TxClassification.ACQUISITION
            )
    
    def test_simple_buy_sell(self):
        """Test simple buy followed by sell"""
        # Buy 1 BTC at $40,000
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Sell 1 BTC at $45,000
        disposal = self.service.dispose_from_lots(
            tx_id="sell1",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=45000.0
        )
        
        assert float(disposal.quantity) == 1.0
        assert float(disposal.proceeds) == 45000.0
        assert float(disposal.total_cost_basis) == 40000.0
        assert float(disposal.gain_loss) == 5000.0
        assert disposal.holding_period == "short-term"
    
    def test_fifo_order(self):
        """Test FIFO ordering - first in, first out"""
        # Buy 1 BTC at $30,000 (Jan)
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=30000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Buy 1 BTC at $40,000 (Feb)
        self.service.create_lot(
            tx_id="buy2",
            asset="BTC",
            acquisition_date=datetime(2024, 2, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Sell 1 BTC at $45,000 - should use FIRST lot ($30k cost basis)
        disposal = self.service.dispose_from_lots(
            tx_id="sell1",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=45000.0
        )
        
        # Should match against $30k lot (FIFO), not $40k lot
        assert float(disposal.total_cost_basis) == 30000.0
        assert float(disposal.gain_loss) == 15000.0
    
    def test_partial_lot_disposal(self):
        """Test partial disposal from a lot"""
        # Buy 2 BTC at $40,000 each
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=2.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Sell 0.5 BTC at $50,000
        disposal = self.service.dispose_from_lots(
            tx_id="sell1",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=0.5,
            proceeds=25000.0
        )
        
        assert float(disposal.quantity) == 0.5
        assert float(disposal.total_cost_basis) == 20000.0  # 0.5 * $40k
        assert float(disposal.gain_loss) == 5000.0  # $25k - $20k
        
        # Check remaining lot
        lot_status = self.service.get_lot_status("BTC")
        assert float(lot_status["total_quantity"]) == 1.5
        assert float(lot_status["total_cost_basis"]) == 60000.0  # 1.5 * $40k
    
    def test_multi_wallet_transfers(self):
        """Test tracking across multiple wallets"""
        # Buy on Coinbase
        self.service.create_lot(
            tx_id="buy1",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=10.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Buy on Kraken (different source)
        self.service.create_lot(
            tx_id="buy2",
            asset="ETH",
            acquisition_date=datetime(2024, 2, 15, tzinfo=timezone.utc),
            quantity=5.0,
            cost_basis_per_unit=2500.0,
            source="kraken",
            classification=TxClassification.ACQUISITION
        )
        
        # Sell 12 ETH (spans both sources)
        disposal = self.service.dispose_from_lots(
            tx_id="sell1",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=12.0,
            proceeds=36000.0  # $3000/ETH
        )
        
        # FIFO: 10 from Coinbase ($2000 each) + 2 from Kraken ($2500 each)
        expected_cost_basis = (10 * 2000) + (2 * 2500)  # $25,000
        assert float(disposal.total_cost_basis) == expected_cost_basis
        assert float(disposal.gain_loss) == 36000.0 - expected_cost_basis  # $11,000
        
        # Should have matched 2 lots
        assert len(disposal.matched_lots) == 2
    
    def test_long_term_holding_period(self):
        """Test long-term capital gains (>365 days)"""
        # Buy BTC in 2023
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2023, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=20000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Sell in 2025 (>1 year later)
        disposal = self.service.dispose_from_lots(
            tx_id="sell1",
            asset="BTC",
            disposal_date=datetime(2025, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=100000.0
        )
        
        assert disposal.holding_period == "long-term"
    
    def test_disposal_exceeds_available_quantity(self):
        """Test that disposal fails if quantity exceeds available"""
        # Buy only 1 BTC
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Try to sell 2 BTC - should fail
        with pytest.raises(ValueError, match="Insufficient quantity"):
            self.service.dispose_from_lots(
                tx_id="sell1",
                asset="BTC",
                disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
                quantity=2.0,
                proceeds=90000.0
            )
    
    def test_orphan_disposal_fails(self):
        """Test that disposal without any lots fails"""
        # No lots created for ETH
        with pytest.raises(ValueError, match="No lots available"):
            self.service.dispose_from_lots(
                tx_id="sell1",
                asset="ETH",
                disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
                quantity=1.0,
                proceeds=3000.0
            )


class TestInvariantChecks:
    """Test invariant enforcement"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_balance_reconciliation_pass(self):
        """Test balance reconciliation with correct balances"""
        # Start with 0, buy 2, sell 1, should end with 1
        self.service.create_lot(
            tx_id="buy1",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=2.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        self.service.dispose_from_lots(
            tx_id="sell1",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=2500.0
        )
        
        is_valid = self.service.check_balance_reconciliation("ETH", 0, 1.0)
        assert is_valid == True
    
    def test_balance_reconciliation_fail(self):
        """Test balance reconciliation with incorrect balances"""
        self.service.create_lot(
            tx_id="buy1",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=2.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        # Claim ending balance of 5 when it should be 2
        is_valid = self.service.check_balance_reconciliation("ETH", 0, 5.0)
        assert is_valid == False
        assert len(self.service.violations) > 0
        assert self.service.violations[0].invariant_type == InvariantType.BALANCE_RECONCILIATION
    
    def test_no_double_spend_pass(self):
        """Test that normal disposals don't trigger double spend"""
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        self.service.dispose_from_lots(
            tx_id="sell1",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=45000.0
        )
        
        is_valid = self.service.check_no_double_spend()
        assert is_valid == True
    
    def test_no_orphan_disposals_pass(self):
        """Test that valid disposals have all required data"""
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        self.service.dispose_from_lots(
            tx_id="sell1",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=45000.0
        )
        
        is_valid = self.service.check_no_orphan_disposals()
        assert is_valid == True
    
    def test_run_all_invariants(self):
        """Test running all invariant checks together"""
        self.service.create_lot(
            tx_id="buy1",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=5.0,
            cost_basis_per_unit=2000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        self.service.dispose_from_lots(
            tx_id="sell1",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=2.0,
            proceeds=5000.0
        )
        
        result = self.service.run_all_invariant_checks(
            balances={"ETH": {"starting": 0, "ending": 3.0}}
        )
        
        assert result.is_valid == True
        assert result.status == ValidationStatus.VALID


class TestForm8949Validation:
    """Test Form 8949 export validation"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_valid_8949_record(self):
        """Test validation of valid Form 8949 record"""
        record = {
            "description": "1.0 BTC",
            "date_acquired": "2024-01-15",
            "date_sold": "2024-06-15",
            "proceeds": 45000.0,
            "cost_basis": 40000.0,
            "gain_or_loss": 5000.0
        }
        
        is_valid, errors = self.service.validate_form_8949_record(record)
        assert is_valid == True
        assert len(errors) == 0
    
    def test_missing_field_fails(self):
        """Test that missing required field fails validation"""
        record = {
            "description": "1.0 BTC",
            "date_acquired": "2024-01-15",
            # Missing date_sold
            "proceeds": 45000.0,
            "cost_basis": 40000.0,
            "gain_or_loss": 5000.0
        }
        
        is_valid, errors = self.service.validate_form_8949_record(record)
        assert is_valid == False
        assert any("Date sold" in e for e in errors)
    
    def test_negative_proceeds_fails(self):
        """Test that negative proceeds fails validation"""
        record = {
            "description": "1.0 BTC",
            "date_acquired": "2024-01-15",
            "date_sold": "2024-06-15",
            "proceeds": -1000.0,  # Invalid
            "cost_basis": 40000.0,
            "gain_or_loss": -41000.0
        }
        
        is_valid, errors = self.service.validate_form_8949_record(record)
        assert is_valid == False
        assert any("negative" in e.lower() for e in errors)
    
    def test_gain_loss_calculation_mismatch(self):
        """Test that incorrect gain/loss calculation fails"""
        record = {
            "description": "1.0 BTC",
            "date_acquired": "2024-01-15",
            "date_sold": "2024-06-15",
            "proceeds": 45000.0,
            "cost_basis": 40000.0,
            "gain_or_loss": 10000.0  # Wrong! Should be 5000
        }
        
        is_valid, errors = self.service.validate_form_8949_record(record)
        assert is_valid == False
        assert any("mismatch" in e.lower() for e in errors)
    
    def test_full_export_validation(self):
        """Test validation of complete Form 8949 export"""
        # Create valid disposal
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        self.service.dispose_from_lots(
            tx_id="sell1",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=45000.0
        )
        
        records = [{
            "description": "1.0 BTC",
            "date_acquired": "2024-01-15",
            "date_sold": "2024-06-15",
            "proceeds": 45000.0,
            "cost_basis": 40000.0,
            "gain_or_loss": 5000.0
        }]
        
        can_export, result = self.service.validate_form_8949_export(records)
        assert can_export == True
        assert result.is_valid == True


class TestBridgeTransactions:
    """Test bridge transaction handling"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_bridge_internal_transfer(self):
        """Test that resolved bridge transfers don't create tax events"""
        # Buy ETH on Ethereum
        self.service.create_lot(
            tx_id="buy1",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=10.0,
            cost_basis_per_unit=2000.0,
            source="ethereum_wallet",
            classification=TxClassification.ACQUISITION
        )
        
        # Bridge to Arbitrum (internal transfer - classified as such after review)
        # This should NOT create a disposal or change cost basis
        
        # Verify cost basis preserved
        lot_status = self.service.get_lot_status("ETH")
        assert float(lot_status["total_quantity"]) == 10.0
        assert float(lot_status["total_cost_basis"]) == 20000.0
    
    def test_bridge_external_transfer(self):
        """Test that unresolved bridge marked external creates tax event"""
        # Buy ETH
        self.service.create_lot(
            tx_id="buy1",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=10.0,
            cost_basis_per_unit=2000.0,
            source="ethereum_wallet",
            classification=TxClassification.ACQUISITION
        )
        
        # Bridge marked as external (not user's wallet on other side)
        # Creates disposal at current FMV
        disposal = self.service.dispose_from_lots(
            tx_id="bridge1",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=10.0,
            proceeds=30000.0  # FMV at time of bridge
        )
        
        assert float(disposal.total_cost_basis) == 20000.0
        assert float(disposal.gain_loss) == 10000.0


class TestIncomeHandling:
    """Test staking rewards and income handling"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_staking_creates_cost_basis(self):
        """Test that staking rewards create cost basis at FMV"""
        # Receive staking reward
        lot = self.service.create_lot(
            tx_id="stake1",
            asset="ETH",
            acquisition_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=0.1,
            cost_basis_per_unit=3000.0,  # FMV at receipt
            source="staking_pool",
            classification=TxClassification.INCOME
        )
        
        assert lot.classification == TxClassification.INCOME
        assert float(lot.total_cost_basis) == 300.0  # 0.1 * $3000
    
    def test_sell_staking_rewards(self):
        """Test selling staking rewards calculates gains correctly"""
        # Receive staking reward at $3000/ETH
        self.service.create_lot(
            tx_id="stake1",
            asset="ETH",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=3000.0,
            source="staking_pool",
            classification=TxClassification.INCOME
        )
        
        # Sell at $3500/ETH
        disposal = self.service.dispose_from_lots(
            tx_id="sell1",
            asset="ETH",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=3500.0
        )
        
        # Gain should be $500 (proceeds - FMV at receipt)
        assert float(disposal.total_cost_basis) == 3000.0
        assert float(disposal.gain_loss) == 500.0


class TestFeeDeductions:
    """Test fee handling in transactions"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_buy_with_fee(self):
        """Test that fees can be added to cost basis"""
        # Buy 1 BTC at $40,000 with $50 fee
        # Total cost basis should include fee
        lot = self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40050.0,  # Price + fee
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        assert float(lot.total_cost_basis) == 40050.0


class TestRecomputeLogic:
    """Test recompute trigger functionality"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_recompute_clears_state(self):
        """Test that recompute clears all computed state"""
        # Create some state
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        self.service.dispose_from_lots(
            tx_id="sell1",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=45000.0
        )
        
        # Trigger recompute
        result = self.service.trigger_full_recompute("linkage_change")
        
        assert result["recompute_triggered"] == True
        assert result["cleared_lots"] == 1
        assert result["cleared_disposals"] == 1
        
        # Verify state is cleared
        lot_status = self.service.get_lot_status("BTC")
        assert lot_status["total_quantity"] == 0


class TestAuditTrail:
    """Test audit trail functionality"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_audit_trail_created(self):
        """Test that operations create audit trail entries"""
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        audit_trail = self.service.get_audit_trail()
        assert len(audit_trail) > 0
        assert audit_trail[-1]["action"] == "create_lot"
        assert audit_trail[-1]["details"]["asset"] == "BTC"
    
    def test_audit_trail_disposal(self):
        """Test that disposals are audited"""
        self.service.create_lot(
            tx_id="buy1",
            asset="BTC",
            acquisition_date=datetime(2024, 1, 15, tzinfo=timezone.utc),
            quantity=1.0,
            cost_basis_per_unit=40000.0,
            source="coinbase",
            classification=TxClassification.ACQUISITION
        )
        
        self.service.dispose_from_lots(
            tx_id="sell1",
            asset="BTC",
            disposal_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
            quantity=1.0,
            proceeds=45000.0
        )
        
        audit_trail = self.service.get_audit_trail()
        disposal_entries = [e for e in audit_trail if e["action"] == "dispose_from_lots"]
        assert len(disposal_entries) == 1
        assert disposal_entries[0]["details"]["gain_loss"] == 5000.0


class TestUnresolvedChainBreaks:
    """Test handling of unresolved chain breaks"""
    
    def setup_method(self):
        self.service = TaxValidationService()
    
    def test_unresolved_defaults_to_external(self):
        """Test that unresolved chain breaks default to external (taxable)"""
        tx = {
            "tx_type": "send",
            "asset": "ETH",
            "amount": 5.0,
            "chain_status": "unlinked"  # Unresolved
        }
        
        classification, confidence = self.service.classify_transaction(tx)
        
        # Unresolved should be UNKNOWN with low confidence
        assert classification == TxClassification.UNKNOWN
        assert confidence < 0.5
        
        # Validated transaction should need review
        validated = self.service.validate_classification(tx)
        assert validated["needs_review"] == True


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
