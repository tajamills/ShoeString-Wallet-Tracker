"""
Tests for Constrained Proceeds Acquisition Remediation Service

Ensures the service NEVER creates inventory without a linked disposal.
Tests all exclusion cases and validates audit trail.
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from constrained_proceeds_service import (
    ConstrainedProceedsService,
    SkipReason,
    CandidateFix,
    SkippedDisposal,
    DryRunSummary
)


class MockCollection:
    """Mock MongoDB collection for testing"""
    
    def __init__(self, data=None):
        self.data = data or []
        self.inserted = []
        self.deleted = []
        self._aggregation_results = []
    
    def find(self, query, projection=None):
        # Filter data based on query
        filtered = []
        for item in self.data:
            match = True
            for key, value in query.items():
                if key == "$and":
                    continue
                if isinstance(value, dict):
                    if "$in" in value:
                        if item.get(key) not in value["$in"]:
                            match = False
                    elif "$nin" in value:
                        if item.get(key) in value["$nin"]:
                            match = False
                    elif "$exists" in value:
                        if value["$exists"] and key not in item:
                            match = False
                        elif not value["$exists"] and key in item:
                            match = False
                else:
                    if item.get(key) != value:
                        match = False
            if match:
                filtered.append(item)
        self._filtered = filtered
        return self
    
    async def to_list(self, limit):
        # Return aggregation results if available
        if hasattr(self, '_aggregation_results') and self._aggregation_results:
            results = self._aggregation_results
            self._aggregation_results = []  # Clear after use
            return results
        if hasattr(self, '_filtered'):
            return self._filtered
        return self.data
    
    def aggregate(self, pipeline):
        # Simple aggregation mock - return pre-set results or build from data
        results = []
        
        # Check if it's the acquisition history aggregation
        for stage in pipeline:
            if "$group" in stage and stage["$group"].get("_id") == "$asset":
                # Group by asset for acquisition history
                from collections import defaultdict
                grouped = defaultdict(lambda: {"count": 0, "total": 0, "earliest": None})
                
                # Filter for acquisition types
                match_stage = next((s.get("$match", {}) for s in pipeline if "$match" in s), {})
                tx_types = match_stage.get("tx_type", {}).get("$in", [])
                
                for item in self.data:
                    if item.get("tx_type") in tx_types:
                        asset = item.get("asset", "UNKNOWN")
                        grouped[asset]["count"] += 1
                        qty = item.get("quantity", 0) or item.get("amount", 0) or 0
                        grouped[asset]["total"] += float(qty)
                
                results = [
                    {
                        "_id": asset,
                        "count": data["count"],
                        "total_quantity": data["total"],
                        "earliest": "2023-01-01T00:00:00Z"
                    }
                    for asset, data in grouped.items()
                ]
                break
            elif "$group" in stage and stage["$group"].get("_id") == "$rollback_batch_id":
                # Handle rollback batch listing
                from collections import defaultdict
                grouped = defaultdict(lambda: {"count": 0, "total": 0, "assets": set(), "created_at": None})
                
                for item in self.data:
                    if item.get("derived_record") and item.get("rollback_batch_id"):
                        bid = item["rollback_batch_id"]
                        grouped[bid]["count"] += 1
                        grouped[bid]["total"] += float(item.get("quantity", 0))
                        grouped[bid]["assets"].add(item.get("asset", "UNKNOWN"))
                        grouped[bid]["created_at"] = item.get("created_at")
                
                results = [
                    {
                        "_id": bid,
                        "count": data["count"],
                        "total_value": data["total"],
                        "assets": list(data["assets"]),
                        "created_at": data["created_at"]
                    }
                    for bid, data in grouped.items()
                ]
                break
        
        self._aggregation_results = results
        return self
    
    async def insert_many(self, records):
        self.inserted.extend(records)
        return MagicMock(inserted_ids=[f"id_{i}" for i in range(len(records))])
    
    async def insert_one(self, record):
        self.inserted.append(record)
        return MagicMock(inserted_id="inserted_id")
    
    async def delete_many(self, query):
        self.deleted.append(query)
        count = len([d for d in self.data if d.get("rollback_batch_id") == query.get("rollback_batch_id")])
        return MagicMock(deleted_count=count)


class MockDB:
    """Mock database for testing"""
    
    def __init__(self):
        self.exchange_transactions = MockCollection()
        self.review_queue = MockCollection()
        self.tax_audit_trail = MockCollection()


# === TESTS FOR EXCLUSION CASES ===

@pytest.mark.asyncio
async def test_excludes_stablecoin_disposals():
    """Test that stablecoin disposals are NOT given proceeds acquisitions"""
    db = MockDB()
    
    # USDC sell should be skipped
    db.exchange_transactions.data = [
        {
            "tx_id": "usdc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "USDC",
            "quantity": 1000,
            "total_usd": 1000,
            "timestamp": "2024-01-01T00:00:00Z"
        }
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 0
    assert summary.non_fixable_count == 1
    assert SkipReason.STABLECOIN_SOURCE.value in summary.non_fixable_by_reason


@pytest.mark.asyncio
async def test_excludes_already_has_proceeds():
    """Test that disposals with existing proceeds records are skipped"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        # The original sell
        {
            "tx_id": "btc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "BTC",
            "quantity": 0.5,
            "total_usd": 25000,
            "timestamp": "2024-01-01T00:00:00Z"
        },
        # Existing proceeds record
        {
            "tx_id": "derived_proceeds_btc_sell_1",
            "user_id": "test_user",
            "tx_type": "derived_proceeds_acquisition",
            "asset": "USDC",
            "quantity": 25000
        },
        # Need at least one acquisition for history check
        {
            "tx_id": "btc_buy_1",
            "user_id": "test_user",
            "tx_type": "buy",
            "asset": "BTC",
            "quantity": 1.0,
            "timestamp": "2023-01-01T00:00:00Z"
        }
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 0
    assert SkipReason.ALREADY_HAS_PROCEEDS.value in summary.non_fixable_by_reason


@pytest.mark.asyncio
async def test_excludes_missing_proceeds_value():
    """Test that disposals without USD value are skipped"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "eth_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "ETH",
            "quantity": 1.0,
            "total_usd": None,  # Missing!
            "timestamp": "2024-01-01T00:00:00Z"
        }
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 0
    assert SkipReason.MISSING_PROCEEDS_VALUE.value in summary.non_fixable_by_reason


@pytest.mark.asyncio
async def test_excludes_missing_timestamp():
    """Test that disposals without timestamp are skipped"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "eth_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "ETH",
            "quantity": 1.0,
            "total_usd": 3000,
            "timestamp": None  # Missing!
        }
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 0
    assert SkipReason.MISSING_TIMESTAMP.value in summary.non_fixable_by_reason


@pytest.mark.asyncio
async def test_excludes_unresolved_wallet_ownership():
    """Test that disposals with pending review queue items are skipped"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "eth_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "ETH",
            "quantity": 1.0,
            "total_usd": 3000,
            "timestamp": "2024-01-01T00:00:00Z"
        }
    ]
    
    # This disposal is in the review queue
    db.review_queue.data = [
        {
            "tx_id": "eth_sell_1",
            "user_id": "test_user",
            "review_status": "pending"
        }
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 0
    assert SkipReason.UNRESOLVED_WALLET_OWNERSHIP.value in summary.non_fixable_by_reason


@pytest.mark.asyncio
async def test_excludes_missing_acquisition_history():
    """Test that disposals without prior acquisitions are skipped"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "sol_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "SOL",
            "quantity": 10.0,
            "total_usd": 2000,
            "timestamp": "2024-01-01T00:00:00Z"
        }
        # No SOL buys/acquisitions!
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 0
    assert SkipReason.MISSING_ACQUISITION_HISTORY.value in summary.non_fixable_by_reason


@pytest.mark.asyncio
async def test_excludes_inferred_internal_transfer():
    """Test that linked/internal transfers are skipped"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "eth_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "ETH",
            "quantity": 1.0,
            "total_usd": 3000,
            "timestamp": "2024-01-01T00:00:00Z",
            "chain_status": "linked"  # Internal transfer!
        },
        # Required acquisition history
        {
            "tx_id": "eth_buy_1",
            "user_id": "test_user",
            "tx_type": "buy",
            "asset": "ETH",
            "quantity": 2.0,
            "timestamp": "2023-01-01T00:00:00Z"
        }
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 0
    assert SkipReason.INFERRED_INTERNAL_TRANSFER.value in summary.non_fixable_by_reason


@pytest.mark.asyncio
async def test_excludes_bridge_ambiguity():
    """Test that bridge transactions without explicit proceeds are skipped"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "eth_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "ETH",
            "quantity": 1.0,
            "total_usd": 3000,
            "timestamp": "2024-01-01T00:00:00Z",
            "notes": "Wormhole bridge transaction"
        },
        # Need acquisition history
        {
            "tx_id": "eth_buy_1",
            "user_id": "test_user",
            "tx_type": "buy",
            "asset": "ETH",
            "quantity": 2.0
        }
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 0
    assert SkipReason.BRIDGE_AMBIGUITY.value in summary.non_fixable_by_reason


@pytest.mark.asyncio
async def test_excludes_dex_ambiguity():
    """Test that DEX swaps without explicit proceeds are skipped"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "eth_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "ETH",
            "quantity": 1.0,
            "total_usd": 3000,
            "timestamp": "2024-01-01T00:00:00Z",
            "notes": "Uniswap swap"
            # No received_asset or output_asset
        },
        {
            "tx_id": "eth_buy_1",
            "user_id": "test_user",
            "tx_type": "buy",
            "asset": "ETH",
            "quantity": 2.0
        }
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 0
    assert SkipReason.DEX_AMBIGUITY.value in summary.non_fixable_by_reason


# === TESTS FOR VALID CANDIDATES ===

@pytest.mark.asyncio
async def test_creates_candidate_for_valid_disposal():
    """Test that valid disposals get proceeds acquisition candidates"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        # Valid sell
        {
            "tx_id": "btc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "BTC",
            "quantity": 0.5,
            "total_usd": 50000,
            "timestamp": "2024-01-15T10:30:00Z",
            "exchange": "coinbase"
        },
        # Required acquisition history
        {
            "tx_id": "btc_buy_1",
            "user_id": "test_user",
            "tx_type": "buy",
            "asset": "BTC",
            "quantity": 1.0,
            "timestamp": "2023-01-01T00:00:00Z"
        }
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    assert summary.fixable_count == 1
    assert summary.fixable_total_value == 50000
    assert len(summary.candidates) == 1
    
    candidate = summary.candidates[0]
    assert candidate.source_disposal_tx_id == "btc_sell_1"
    assert candidate.source_asset == "BTC"
    assert candidate.proceeds_amount == 50000
    assert candidate.proceeds_asset == "USDC"
    assert candidate.price_source == "proceeds_from_BTC_sell"


# === TESTS FOR AUDIT TRAIL AND REVERSIBILITY ===

@pytest.mark.asyncio
async def test_apply_creates_audit_entries():
    """Test that applying fixes creates audit trail entries"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "btc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "BTC",
            "quantity": 0.5,
            "total_usd": 50000,
            "timestamp": "2024-01-15T10:30:00Z",
            "exchange": "coinbase"
        },
        {
            "tx_id": "btc_buy_1",
            "user_id": "test_user",
            "tx_type": "buy",
            "asset": "BTC",
            "quantity": 1.0
        }
    ]
    
    service = ConstrainedProceedsService(db)
    results = await service.apply_fixes("test_user", dry_run=False)
    
    assert results["created_count"] == 1
    assert results["rollback_batch_id"] is not None
    assert len(db.tax_audit_trail.inserted) == 1
    
    audit_entry = db.tax_audit_trail.inserted[0]
    assert audit_entry["action"] == "create_derived_proceeds_acquisition"
    assert audit_entry["details"]["linkage_verified"] == True


@pytest.mark.asyncio
async def test_created_records_have_rollback_id():
    """Test that created records have rollback_batch_id for reversibility"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "btc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "BTC",
            "quantity": 0.5,
            "total_usd": 50000,
            "timestamp": "2024-01-15T10:30:00Z",
            "exchange": "coinbase"
        },
        {
            "tx_id": "btc_buy_1",
            "user_id": "test_user",
            "tx_type": "buy",
            "asset": "BTC",
            "quantity": 1.0
        }
    ]
    
    service = ConstrainedProceedsService(db)
    results = await service.apply_fixes("test_user", dry_run=False)
    
    assert len(db.exchange_transactions.inserted) == 1
    created_record = db.exchange_transactions.inserted[0]
    
    assert created_record["rollback_batch_id"] == results["rollback_batch_id"]
    assert created_record["derived_record"] == True
    assert created_record["tx_type"] == "derived_proceeds_acquisition"


@pytest.mark.asyncio
async def test_created_records_have_source_disposal_linkage():
    """Test that created records are linked to source disposal"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {
            "tx_id": "btc_sell_1",
            "user_id": "test_user",
            "tx_type": "sell",
            "asset": "BTC",
            "quantity": 0.5,
            "total_usd": 50000,
            "timestamp": "2024-01-15T10:30:00Z",
            "exchange": "coinbase"
        },
        {
            "tx_id": "btc_buy_1",
            "user_id": "test_user",
            "tx_type": "buy",
            "asset": "BTC",
            "quantity": 1.0
        }
    ]
    
    service = ConstrainedProceedsService(db)
    await service.apply_fixes("test_user", dry_run=False)
    
    created_record = db.exchange_transactions.inserted[0]
    
    # Verify source disposal linkage
    assert "source_disposal" in created_record
    assert created_record["source_disposal"]["tx_id"] == "btc_sell_1"
    assert created_record["source_disposal"]["asset"] == "BTC"
    assert created_record["source_disposal"]["quantity"] == 0.5
    assert created_record["source_disposal"]["proceeds"] == 50000


# === TESTS FOR NEVER CREATING INVENTORY WITHOUT LINKED DISPOSAL ===

@pytest.mark.asyncio
async def test_never_creates_orphan_inventory():
    """
    CRITICAL TEST: Verify that EVERY created record has a linked source disposal.
    This test ensures we NEVER create inventory without a disposal.
    """
    db = MockDB()
    
    # Add multiple sells and buys
    db.exchange_transactions.data = [
        # Valid sells
        {"tx_id": "btc_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "BTC", "quantity": 0.5, "total_usd": 50000, "timestamp": "2024-01-01T00:00:00Z"},
        {"tx_id": "eth_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "ETH", "quantity": 2.0, "total_usd": 6000, "timestamp": "2024-01-02T00:00:00Z"},
        # Required acquisition history
        {"tx_id": "btc_buy_1", "user_id": "test_user", "tx_type": "buy", "asset": "BTC", "quantity": 1.0},
        {"tx_id": "eth_buy_1", "user_id": "test_user", "tx_type": "buy", "asset": "ETH", "quantity": 5.0},
    ]
    
    service = ConstrainedProceedsService(db)
    results = await service.apply_fixes("test_user", dry_run=False)
    
    # Verify each created record
    for record in db.exchange_transactions.inserted:
        # MUST have source_disposal
        assert "source_disposal" in record, f"Record {record['tx_id']} missing source_disposal!"
        assert record["source_disposal"]["tx_id"], f"Record {record['tx_id']} has empty source disposal tx_id!"
        
        # MUST have proper tx_type
        assert record["tx_type"] == "derived_proceeds_acquisition", f"Record {record['tx_id']} has wrong tx_type!"
        
        # MUST have rollback capability
        assert record["rollback_batch_id"], f"Record {record['tx_id']} missing rollback_batch_id!"
        assert record["derived_record"] == True, f"Record {record['tx_id']} not marked as derived!"


@pytest.mark.asyncio
async def test_dry_run_does_not_create_records():
    """Test that dry_run mode does not create any records"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        {"tx_id": "btc_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "BTC", "quantity": 0.5, "total_usd": 50000, "timestamp": "2024-01-01T00:00:00Z"},
        {"tx_id": "btc_buy_1", "user_id": "test_user", "tx_type": "buy", "asset": "BTC", "quantity": 1.0},
    ]
    
    service = ConstrainedProceedsService(db)
    results = await service.apply_fixes("test_user", dry_run=True)
    
    assert results["dry_run"] == True
    assert results["rollback_batch_id"] is None
    assert len(db.exchange_transactions.inserted) == 0
    assert len(db.tax_audit_trail.inserted) == 0


@pytest.mark.asyncio
async def test_preview_shows_all_candidates_and_skipped():
    """Test that preview mode shows complete information"""
    db = MockDB()
    
    db.exchange_transactions.data = [
        # Valid - should be candidate
        {"tx_id": "btc_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "BTC", "quantity": 0.5, "total_usd": 50000, "timestamp": "2024-01-01T00:00:00Z"},
        # Invalid - missing USD value
        {"tx_id": "eth_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "ETH", "quantity": 1.0, "total_usd": None, "timestamp": "2024-01-01T00:00:00Z"},
        # Invalid - stablecoin
        {"tx_id": "usdc_sell_1", "user_id": "test_user", "tx_type": "sell", "asset": "USDC", "quantity": 1000, "total_usd": 1000, "timestamp": "2024-01-01T00:00:00Z"},
        # Required acquisition history
        {"tx_id": "btc_buy_1", "user_id": "test_user", "tx_type": "buy", "asset": "BTC", "quantity": 1.0},
        {"tx_id": "eth_buy_1", "user_id": "test_user", "tx_type": "buy", "asset": "ETH", "quantity": 2.0},
    ]
    
    service = ConstrainedProceedsService(db)
    summary = await service.preview_candidates("test_user")
    
    # Verify counts
    assert summary.fixable_count == 1
    assert summary.non_fixable_count == 2
    
    # Verify candidate has all required fields
    assert len(summary.candidates) == 1
    candidate = summary.candidates[0]
    assert candidate.source_disposal_tx_id
    assert candidate.source_asset
    assert candidate.proceeds_amount > 0
    assert candidate.price_source
    
    # Verify skipped items have reasons
    assert len(summary.skipped) == 2
    skip_reasons = [s.skip_reason for s in summary.skipped]
    assert SkipReason.MISSING_PROCEEDS_VALUE in skip_reasons
    assert SkipReason.STABLECOIN_SOURCE in skip_reasons


# === RUN TESTS ===

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
