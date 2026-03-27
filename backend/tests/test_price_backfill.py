"""
Tests for Price Backfill Pipeline

Ensures the service correctly:
- Fetches historical prices for disposals missing USD valuation
- Categorizes valuations as exact, approximate, or unavailable
- Creates audit trails for all backfilled prices
- Supports dry-run mode and rollback
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from price_backfill_service import (
    PriceBackfillService,
    ValuationStatus,
    PriceSource,
    PriceBackfillResult,
    BackfillSummary
)


class MockCollection:
    """Mock MongoDB collection for testing"""
    
    def __init__(self, data=None):
        self.data = data or []
        self.inserted = []
        self.updated = []
        self._aggregation_results = []
    
    def find(self, query, projection=None):
        # Simple query matching
        filtered = []
        for item in self.data:
            match = True
            for key, value in query.items():
                if key == "$or":
                    or_match = False
                    for or_cond in value:
                        for or_key, or_val in or_cond.items():
                            if isinstance(or_val, dict):
                                if "$exists" in or_val and not or_val["$exists"] and or_key not in item:
                                    or_match = True
                            elif item.get(or_key) == or_val:
                                or_match = True
                    if not or_match:
                        match = False
                elif isinstance(value, dict):
                    if "$exists" in value:
                        if value["$exists"] and key not in item:
                            match = False
                else:
                    if item.get(key) != value:
                        match = False
            if match:
                filtered.append(item)
        self._filtered = filtered
        return self
    
    async def to_list(self, limit):
        if hasattr(self, '_aggregation_results') and self._aggregation_results:
            results = self._aggregation_results
            self._aggregation_results = []
            return results
        if hasattr(self, '_filtered'):
            return self._filtered
        return self.data
    
    def aggregate(self, pipeline):
        self._aggregation_results = []
        return self
    
    async def update_one(self, query, update):
        self.updated.append({"query": query, "update": update})
        return MagicMock(modified_count=1)
    
    async def update_many(self, query, update):
        self.updated.append({"query": query, "update": update})
        return MagicMock(modified_count=len(self.data))
    
    async def insert_many(self, records):
        self.inserted.extend(records)
        return MagicMock(inserted_ids=[f"id_{i}" for i in range(len(records))])
    
    async def insert_one(self, record):
        self.inserted.append(record)
        return MagicMock(inserted_id="inserted_id")


class MockDB:
    """Mock database for testing"""
    
    def __init__(self):
        self.exchange_transactions = MockCollection()
        self.tax_audit_trail = MockCollection()


# === TESTS FOR VALUATION STATUS ===

@pytest.mark.asyncio
async def test_stablecoin_valuation():
    """Test that stablecoins get STABLECOIN valuation status"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "usdc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "USDC",
            "quantity": 1000,
            "total_usd": None,
            "timestamp": "2024-01-15T10:30:00Z"
        }
    ]
    
    service = PriceBackfillService(db)
    summary = await service.preview_backfill("test_user")
    
    assert summary.total_missing == 1
    assert summary.successfully_backfilled == 1
    assert len(summary.results) == 1
    
    result = summary.results[0]
    assert result.valuation_status == ValuationStatus.STABLECOIN
    assert result.price_source == PriceSource.STABLECOIN_PEG
    assert result.price_usd == 1.0
    assert result.total_usd == 1000.0
    assert result.confidence == 1.0


@pytest.mark.asyncio
async def test_missing_timestamp_unavailable():
    """Test that disposals without timestamp get UNAVAILABLE status"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "btc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "BTC",
            "quantity": 0.5,
            "total_usd": None,
            "timestamp": None  # Missing!
        }
    ]
    
    service = PriceBackfillService(db)
    summary = await service.preview_backfill("test_user")
    
    assert summary.total_missing == 1
    assert summary.still_missing == 1
    
    result = summary.results[0]
    assert result.valuation_status == ValuationStatus.UNAVAILABLE
    assert result.error == "Missing transaction timestamp"


@pytest.mark.asyncio
@patch('price_backfill_service.price_service')
async def test_exact_match_from_cryptocompare(mock_price_service):
    """Test that exact price match gets EXACT status"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "btc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "BTC",
            "quantity": 0.5,
            "total_usd": None,
            "timestamp": "2024-01-15T10:30:00Z"
        }
    ]
    
    # Mock bulk prices to return data for this date
    mock_price_service.get_bulk_historical_prices.return_value = {
        "15-01-2024": 42000.0
    }
    
    service = PriceBackfillService(db)
    summary = await service.preview_backfill("test_user")
    
    assert summary.total_missing == 1
    assert summary.successfully_backfilled == 1
    
    result = summary.results[0]
    assert result.valuation_status == ValuationStatus.EXACT
    assert result.price_source == PriceSource.CRYPTOCOMPARE
    assert result.price_usd == 42000.0
    assert result.total_usd == 21000.0  # 0.5 * 42000
    assert result.confidence >= 0.9


# === TESTS FOR DRY-RUN AND APPLY ===

@pytest.mark.asyncio
async def test_dry_run_does_not_modify_database():
    """Test that dry_run mode does not modify the database"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "usdc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "USDC",
            "quantity": 1000,
            "total_usd": None,
            "timestamp": "2024-01-15T10:30:00Z"
        }
    ]
    
    service = PriceBackfillService(db)
    results = await service.apply_backfill("test_user", dry_run=True)
    
    assert results["dry_run"] == True
    assert results["backfill_batch_id"] is None
    assert results["applied_count"] == 0
    assert len(db.exchange_transactions.updated) == 0
    assert len(db.tax_audit_trail.inserted) == 0


@pytest.mark.asyncio
async def test_apply_creates_audit_trail():
    """Test that applying backfill creates audit trail entries"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "usdc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "USDC",
            "quantity": 1000,
            "total_usd": None,
            "timestamp": "2024-01-15T10:30:00Z"
        }
    ]
    
    service = PriceBackfillService(db)
    results = await service.apply_backfill("test_user", dry_run=False)
    
    assert results["dry_run"] == False
    assert results["backfill_batch_id"] is not None
    assert results["applied_count"] == 1
    assert len(db.tax_audit_trail.inserted) == 1
    
    audit_entry = db.tax_audit_trail.inserted[0]
    assert audit_entry["action"] == "price_backfill"
    assert audit_entry["details"]["valuation_status"] == "stablecoin"


@pytest.mark.asyncio
async def test_apply_stores_backfill_metadata():
    """Test that applied backfills include proper metadata"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "usdc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "USDC",
            "quantity": 1000,
            "total_usd": None,
            "timestamp": "2024-01-15T10:30:00Z"
        }
    ]
    
    service = PriceBackfillService(db)
    results = await service.apply_backfill("test_user", dry_run=False)
    
    # Check that the update includes backfill metadata
    assert len(db.exchange_transactions.updated) == 1
    update = db.exchange_transactions.updated[0]["update"]["$set"]
    
    assert "price_usd" in update
    assert "total_usd" in update
    assert "price_backfill" in update
    
    backfill_meta = update["price_backfill"]
    assert backfill_meta["valuation_status"] == "stablecoin"
    assert backfill_meta["price_source"] == "stablecoin_peg"
    assert backfill_meta["confidence"] == 1.0
    assert "backfill_batch_id" in backfill_meta


# === TESTS FOR SUMMARY REPORT ===

@pytest.mark.asyncio
async def test_summary_report_counts():
    """Test that summary report has correct counts"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        # Stablecoin - should be backfillable
        {"tx_id": "usdc_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "USDC", "quantity": 1000, "total_usd": None, "timestamp": "2024-01-15T10:30:00Z"},
        # Missing timestamp - should be unavailable
        {"tx_id": "btc_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "BTC", "quantity": 0.5, "total_usd": None, "timestamp": None},
    ]
    
    service = PriceBackfillService(db)
    summary = await service.preview_backfill("test_user")
    
    assert summary.total_missing == 2
    assert summary.successfully_backfilled == 1
    assert summary.still_missing == 1
    assert "stablecoin" in summary.by_status
    assert "unavailable" in summary.by_status


@pytest.mark.asyncio
async def test_summary_report_by_asset():
    """Test that summary report groups by asset correctly"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {"tx_id": "usdc_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "USDC", "quantity": 1000, "total_usd": None, "timestamp": "2024-01-15T10:30:00Z"},
        {"tx_id": "usdc_sell_2", "user_id": "test_user", "tx_type": "sell", "asset": "USDC", "quantity": 500, "total_usd": None, "timestamp": "2024-01-16T10:30:00Z"},
        {"tx_id": "usdt_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "USDT", "quantity": 200, "total_usd": None, "timestamp": "2024-01-17T10:30:00Z"},
    ]
    
    service = PriceBackfillService(db)
    summary = await service.preview_backfill("test_user")
    
    assert "USDC" in summary.by_asset
    assert summary.by_asset["USDC"]["total"] == 2
    assert summary.by_asset["USDC"]["backfillable"] == 2
    
    assert "USDT" in summary.by_asset
    assert summary.by_asset["USDT"]["total"] == 1


# === TESTS FOR ELIGIBILITY CHECK ===

def test_valuation_eligible_original_price_data():
    """Test that transactions with original price data are eligible"""
    db = MockDB()
    service = PriceBackfillService(db)
    
    tx = {"total_usd": 5000.0}
    eligible, reason = service.check_valuation_eligible_for_proceeds(tx)
    
    assert eligible == True
    assert reason == "original_price_data"


def test_valuation_eligible_exact_backfill():
    """Test that exact backfill valuations are eligible"""
    db = MockDB()
    service = PriceBackfillService(db)
    
    tx = {
        "total_usd": 5000.0,
        "price_backfill": {
            "valuation_status": "exact",
            "confidence": 0.95
        }
    }
    eligible, reason = service.check_valuation_eligible_for_proceeds(tx)
    
    assert eligible == True
    assert reason == "exact_price_match"


def test_valuation_eligible_stablecoin():
    """Test that stablecoin valuations are eligible"""
    db = MockDB()
    service = PriceBackfillService(db)
    
    tx = {
        "total_usd": 1000.0,
        "price_backfill": {
            "valuation_status": "stablecoin",
            "confidence": 1.0
        }
    }
    eligible, reason = service.check_valuation_eligible_for_proceeds(tx)
    
    assert eligible == True
    assert reason == "stablecoin_peg"


def test_valuation_not_eligible_unavailable():
    """Test that unavailable valuations are not eligible"""
    db = MockDB()
    service = PriceBackfillService(db)
    
    tx = {
        "total_usd": None,
        "price_backfill": {
            "valuation_status": "unavailable",
            "confidence": 0.0
        }
    }
    eligible, reason = service.check_valuation_eligible_for_proceeds(tx)
    
    assert eligible == False
    assert reason == "unavailable_valuation"


def test_valuation_not_eligible_low_confidence_approximate():
    """Test that low-confidence approximate valuations are not eligible"""
    db = MockDB()
    service = PriceBackfillService(db)
    
    tx = {
        "total_usd": 5000.0,
        "price_backfill": {
            "valuation_status": "approximate",
            "confidence": 0.5  # Below 0.7 threshold
        }
    }
    eligible, reason = service.check_valuation_eligible_for_proceeds(tx)
    
    assert eligible == False
    assert reason == "approximate_low_confidence"


def test_valuation_eligible_high_confidence_approximate():
    """Test that high-confidence approximate valuations are eligible"""
    db = MockDB()
    service = PriceBackfillService(db)
    
    tx = {
        "total_usd": 5000.0,
        "price_backfill": {
            "valuation_status": "approximate",
            "confidence": 0.8  # Above 0.7 threshold
        }
    }
    eligible, reason = service.check_valuation_eligible_for_proceeds(tx)
    
    assert eligible == True
    assert reason == "approximate_high_confidence"


# === RUN TESTS ===

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
