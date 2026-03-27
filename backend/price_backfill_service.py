"""
Price Backfill Pipeline for Disposals Missing USD Valuation

Fetches historical USD prices for transactions missing valuation data.
Implements strict validation with confidence levels and audit trails.

Valuation Statuses:
- exact: Price from exact transaction timestamp (within 1 hour)
- approximate: Price from nearest available data point (within allowed window)
- unavailable: No price data found within acceptable time range

Only exact or policy-allowed approximate valuations enable downstream
proceeds-acquisition creation.
"""

import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field, asdict

from price_service import price_service

logger = logging.getLogger(__name__)


class ValuationStatus(Enum):
    """Status of price valuation"""
    EXACT = "exact"                    # Price from exact timestamp (within 1 hour)
    APPROXIMATE = "approximate"         # Price from nearest available (within allowed window)
    UNAVAILABLE = "unavailable"         # No price data found
    STABLECOIN = "stablecoin"           # Fixed 1:1 USD peg


class PriceSource(Enum):
    """Source of price data"""
    CRYPTOCOMPARE = "cryptocompare"
    COINGECKO = "coingecko"
    BINANCE = "binance"
    STABLECOIN_PEG = "stablecoin_peg"
    FALLBACK = "fallback"
    UNAVAILABLE = "unavailable"


@dataclass
class PriceBackfillResult:
    """Result of a single price backfill attempt"""
    tx_id: str
    asset: str
    quantity: float
    original_timestamp: str
    
    # Price data
    price_usd: Optional[float] = None
    total_usd: Optional[float] = None
    
    # Valuation metadata
    valuation_status: ValuationStatus = ValuationStatus.UNAVAILABLE
    price_source: PriceSource = PriceSource.UNAVAILABLE
    timestamp_used: Optional[str] = None
    time_delta_hours: Optional[float] = None  # Difference between tx time and price time
    confidence: float = 0.0  # 0.0-1.0
    
    # Processing info
    error: Optional[str] = None
    backfill_attempted: bool = False
    backfill_applied: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "tx_id": self.tx_id,
            "asset": self.asset,
            "quantity": self.quantity,
            "original_timestamp": self.original_timestamp,
            "price_usd": self.price_usd,
            "total_usd": round(self.total_usd, 2) if self.total_usd else None,
            "valuation_status": self.valuation_status.value,
            "price_source": self.price_source.value,
            "timestamp_used": self.timestamp_used,
            "time_delta_hours": round(self.time_delta_hours, 2) if self.time_delta_hours else None,
            "confidence": round(self.confidence, 3),
            "error": self.error,
            "backfill_attempted": self.backfill_attempted,
            "backfill_applied": self.backfill_applied
        }


@dataclass
class BackfillSummary:
    """Summary of backfill operation"""
    total_missing: int = 0
    successfully_backfilled: int = 0
    still_missing: int = 0
    exact_matches: int = 0
    approximate_matches: int = 0
    
    by_status: Dict[str, int] = field(default_factory=dict)
    by_source: Dict[str, int] = field(default_factory=dict)
    by_asset: Dict[str, Dict] = field(default_factory=dict)
    
    results: List[PriceBackfillResult] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "total_missing": self.total_missing,
            "successfully_backfilled": self.successfully_backfilled,
            "still_missing": self.still_missing,
            "exact_matches": self.exact_matches,
            "approximate_matches": self.approximate_matches,
            "by_status": self.by_status,
            "by_source": self.by_source,
            "by_asset": self.by_asset,
            "results": [r.to_dict() for r in self.results]
        }


class PriceBackfillService:
    """
    Service for backfilling missing USD prices on disposals.
    
    Configuration:
    - EXACT_MATCH_WINDOW: 1 hour - price from within this window is "exact"
    - APPROXIMATE_WINDOW: 24 hours - price from within this window is "approximate"
    - Policy allows proceeds-acquisition for: exact, stablecoin, and (optionally) approximate
    """
    
    # Configuration
    EXACT_MATCH_WINDOW_HOURS = 1
    APPROXIMATE_WINDOW_HOURS = 24
    POLICY_ALLOWED_APPROXIMATE = True  # Set to False to require exact matches only
    
    # Stablecoins always valued at $1
    STABLECOINS = {"USDC", "USDT", "USD", "DAI", "BUSD", "TUSD", "USDP", "GUSD", "FRAX"}
    
    def __init__(self, db):
        self.db = db
        self.price_service = price_service
    
    async def get_disposals_missing_price(self, user_id: str) -> List[Dict]:
        """Get all sell transactions missing USD value"""
        return await self.db.exchange_transactions.find({
            "user_id": user_id,
            "tx_type": "sell",
            "$or": [
                {"total_usd": None},
                {"total_usd": {"$exists": False}},
                {"total_usd": 0},
                {"price_usd": None},
                {"price_usd": {"$exists": False}},
                {"price_usd": 0}
            ]
        }).to_list(100000)
    
    async def preview_backfill(self, user_id: str) -> BackfillSummary:
        """
        Preview what backfilling would do (dry-run).
        
        Returns summary of:
        - Total disposals missing price
        - How many can be backfilled (and with what confidence)
        - How many will remain missing
        - Source breakdown
        """
        summary = BackfillSummary()
        
        # Get disposals missing price
        disposals = await self.get_disposals_missing_price(user_id)
        summary.total_missing = len(disposals)
        
        if not disposals:
            return summary
        
        # Pre-fetch bulk historical prices for common assets
        assets = set(d.get("asset", "").upper() for d in disposals)
        bulk_prices = {}
        for asset in assets:
            if asset and asset not in self.STABLECOINS:
                prices = self.price_service.get_bulk_historical_prices(asset, days=2000)
                if prices:
                    bulk_prices[asset] = prices
        
        # Process each disposal
        for disposal in disposals:
            result = self._evaluate_backfill(disposal, bulk_prices)
            summary.results.append(result)
            
            # Update counts
            status_key = result.valuation_status.value
            summary.by_status[status_key] = summary.by_status.get(status_key, 0) + 1
            
            source_key = result.price_source.value
            summary.by_source[source_key] = summary.by_source.get(source_key, 0) + 1
            
            asset = result.asset
            if asset not in summary.by_asset:
                summary.by_asset[asset] = {"total": 0, "backfillable": 0, "missing": 0}
            summary.by_asset[asset]["total"] += 1
            
            if result.valuation_status in [ValuationStatus.EXACT, ValuationStatus.STABLECOIN]:
                summary.successfully_backfilled += 1
                summary.exact_matches += 1
                summary.by_asset[asset]["backfillable"] += 1
            elif result.valuation_status == ValuationStatus.APPROXIMATE:
                if self.POLICY_ALLOWED_APPROXIMATE:
                    summary.successfully_backfilled += 1
                    summary.by_asset[asset]["backfillable"] += 1
                else:
                    summary.still_missing += 1
                    summary.by_asset[asset]["missing"] += 1
                summary.approximate_matches += 1
            else:
                summary.still_missing += 1
                summary.by_asset[asset]["missing"] += 1
        
        return summary
    
    async def apply_backfill(
        self, 
        user_id: str, 
        tx_ids: Optional[List[str]] = None,
        dry_run: bool = True,
        allow_approximate: bool = True
    ) -> Dict[str, Any]:
        """
        Apply price backfill to disposals.
        
        Args:
            user_id: User ID
            tx_ids: Specific tx_ids to backfill (None = all eligible)
            dry_run: If True, preview only
            allow_approximate: If True, apply approximate matches too
        
        Returns:
            Results with applied records and audit trail
        """
        # Get preview first
        summary = await self.preview_backfill(user_id)
        
        # Filter to requested tx_ids
        if tx_ids:
            results = [r for r in summary.results if r.tx_id in tx_ids]
        else:
            results = summary.results
        
        # Filter to backfillable results
        backfillable = []
        for result in results:
            if result.valuation_status == ValuationStatus.EXACT:
                backfillable.append(result)
            elif result.valuation_status == ValuationStatus.STABLECOIN:
                backfillable.append(result)
            elif result.valuation_status == ValuationStatus.APPROXIMATE and allow_approximate:
                backfillable.append(result)
        
        response = {
            "user_id": user_id,
            "dry_run": dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_processed": len(results),
            "backfillable_count": len(backfillable),
            "applied_count": 0,
            "still_missing": len(results) - len(backfillable),
            "allow_approximate": allow_approximate,
            "backfill_batch_id": str(uuid.uuid4()) if not dry_run else None,
            "applied_records": [],
            "audit_entries": [],
            "preview": [r.to_dict() for r in backfillable] if dry_run else []
        }
        
        if dry_run or not backfillable:
            return response
        
        # Apply backfills
        batch_id = response["backfill_batch_id"]
        applied = []
        audit_entries = []
        
        for result in backfillable:
            # Update the transaction
            update_result = await self.db.exchange_transactions.update_one(
                {"tx_id": result.tx_id, "user_id": user_id},
                {"$set": {
                    "price_usd": result.price_usd,
                    "total_usd": result.total_usd,
                    "price_backfill": {
                        "valuation_status": result.valuation_status.value,
                        "price_source": result.price_source.value,
                        "timestamp_used": result.timestamp_used,
                        "time_delta_hours": result.time_delta_hours,
                        "confidence": result.confidence,
                        "backfill_batch_id": batch_id,
                        "backfilled_at": datetime.now(timezone.utc).isoformat()
                    }
                }}
            )
            
            if update_result.modified_count > 0:
                result.backfill_applied = True
                applied.append(result.to_dict())
                
                # Create audit entry
                audit_entry = {
                    "entry_id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "action": "price_backfill",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "backfill_batch_id": batch_id,
                    "details": {
                        "tx_id": result.tx_id,
                        "asset": result.asset,
                        "quantity": result.quantity,
                        "price_usd": result.price_usd,
                        "total_usd": result.total_usd,
                        "valuation_status": result.valuation_status.value,
                        "price_source": result.price_source.value,
                        "timestamp_used": result.timestamp_used,
                        "time_delta_hours": result.time_delta_hours,
                        "confidence": result.confidence
                    }
                }
                audit_entries.append(audit_entry)
        
        # Insert audit entries
        if audit_entries:
            await self.db.tax_audit_trail.insert_many(audit_entries)
        
        response["applied_count"] = len(applied)
        response["applied_records"] = applied
        response["audit_entries"] = [e["entry_id"] for e in audit_entries]
        
        return response
    
    async def rollback_backfill(self, user_id: str, batch_id: str) -> Dict[str, Any]:
        """
        Rollback a batch of price backfills.
        
        Removes price data that was backfilled in the specified batch.
        """
        # Find all transactions with this batch ID
        transactions = await self.db.exchange_transactions.find({
            "user_id": user_id,
            "price_backfill.backfill_batch_id": batch_id
        }).to_list(100000)
        
        if not transactions:
            return {
                "success": False,
                "message": f"No backfilled records found for batch {batch_id}",
                "reverted_count": 0
            }
        
        # Revert the price data
        result = await self.db.exchange_transactions.update_many(
            {
                "user_id": user_id,
                "price_backfill.backfill_batch_id": batch_id
            },
            {
                "$set": {
                    "price_usd": None,
                    "total_usd": None
                },
                "$unset": {
                    "price_backfill": ""
                }
            }
        )
        
        # Add rollback audit entry
        rollback_audit = {
            "entry_id": str(uuid.uuid4()),
            "user_id": user_id,
            "action": "rollback_price_backfill",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "backfill_batch_id": batch_id,
                "records_reverted": result.modified_count,
                "reverted_tx_ids": [t["tx_id"] for t in transactions]
            }
        }
        await self.db.tax_audit_trail.insert_one(rollback_audit)
        
        return {
            "success": True,
            "batch_id": batch_id,
            "reverted_count": result.modified_count,
            "reverted_tx_ids": [t["tx_id"] for t in transactions],
            "audit_entry_id": rollback_audit["entry_id"]
        }
    
    async def list_backfill_batches(self, user_id: str) -> List[Dict]:
        """List all backfill batches for a user"""
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "price_backfill.backfill_batch_id": {"$exists": True}
            }},
            {"$group": {
                "_id": "$price_backfill.backfill_batch_id",
                "count": {"$sum": 1},
                "total_value": {"$sum": "$total_usd"},
                "backfilled_at": {"$first": "$price_backfill.backfilled_at"},
                "assets": {"$addToSet": "$asset"}
            }},
            {"$sort": {"backfilled_at": -1}}
        ]
        
        batches = await self.db.exchange_transactions.aggregate(pipeline).to_list(100)
        
        return [
            {
                "batch_id": b["_id"],
                "record_count": b["count"],
                "total_value": round(b["total_value"], 2) if b["total_value"] else 0,
                "backfilled_at": b["backfilled_at"],
                "assets": b["assets"]
            }
            for b in batches
        ]
    
    def check_valuation_eligible_for_proceeds(self, tx: Dict) -> Tuple[bool, str]:
        """
        Check if a transaction's valuation is eligible for proceeds acquisition.
        
        Returns (eligible, reason)
        """
        backfill_info = tx.get("price_backfill", {})
        valuation_status = backfill_info.get("valuation_status")
        
        # No backfill info - check if it has original price data
        if not backfill_info:
            if tx.get("total_usd") and float(tx.get("total_usd", 0)) > 0:
                return True, "original_price_data"
            return False, "no_price_data"
        
        # Check valuation status
        if valuation_status == ValuationStatus.EXACT.value:
            return True, "exact_price_match"
        
        if valuation_status == ValuationStatus.STABLECOIN.value:
            return True, "stablecoin_peg"
        
        if valuation_status == ValuationStatus.APPROXIMATE.value:
            if self.POLICY_ALLOWED_APPROXIMATE:
                confidence = backfill_info.get("confidence", 0)
                if confidence >= 0.7:  # Require 70%+ confidence for approximate
                    return True, "approximate_high_confidence"
                return False, "approximate_low_confidence"
            return False, "approximate_not_allowed_by_policy"
        
        return False, "unavailable_valuation"
    
    # ========== PRIVATE METHODS ==========
    
    def _evaluate_backfill(
        self, 
        disposal: Dict,
        bulk_prices: Dict[str, Dict[str, float]]
    ) -> PriceBackfillResult:
        """Evaluate a single disposal for backfilling"""
        tx_id = disposal.get("tx_id", "unknown")
        asset = (disposal.get("asset") or "").upper()
        quantity = float(disposal.get("quantity", 0) or disposal.get("amount", 0) or 0)
        timestamp_str = disposal.get("timestamp")
        
        result = PriceBackfillResult(
            tx_id=tx_id,
            asset=asset,
            quantity=quantity,
            original_timestamp=str(timestamp_str) if timestamp_str else None,
            backfill_attempted=True
        )
        
        # Handle missing timestamp
        if not timestamp_str:
            result.error = "Missing transaction timestamp"
            result.valuation_status = ValuationStatus.UNAVAILABLE
            return result
        
        # Parse timestamp
        try:
            if isinstance(timestamp_str, str):
                # Try various formats
                for fmt in ["%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", 
                           "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        tx_dt = datetime.strptime(timestamp_str, fmt)
                        if tx_dt.tzinfo is None:
                            tx_dt = tx_dt.replace(tzinfo=timezone.utc)
                        break
                    except ValueError:
                        continue
                else:
                    # Try ISO format as last resort
                    tx_dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            elif isinstance(timestamp_str, datetime):
                tx_dt = timestamp_str
                if tx_dt.tzinfo is None:
                    tx_dt = tx_dt.replace(tzinfo=timezone.utc)
            else:
                result.error = f"Unsupported timestamp format: {type(timestamp_str)}"
                result.valuation_status = ValuationStatus.UNAVAILABLE
                return result
        except Exception as e:
            result.error = f"Cannot parse timestamp: {str(e)}"
            result.valuation_status = ValuationStatus.UNAVAILABLE
            return result
        
        result.timestamp_used = tx_dt.isoformat()
        
        # Handle stablecoins
        if asset in self.STABLECOINS:
            result.price_usd = 1.0
            result.total_usd = quantity * 1.0
            result.valuation_status = ValuationStatus.STABLECOIN
            result.price_source = PriceSource.STABLECOIN_PEG
            result.confidence = 1.0
            result.time_delta_hours = 0.0
            return result
        
        # Try bulk prices first (faster)
        date_str = tx_dt.strftime('%d-%m-%Y')
        if asset in bulk_prices and date_str in bulk_prices[asset]:
            price = bulk_prices[asset][date_str]
            result.price_usd = price
            result.total_usd = quantity * price
            result.price_source = PriceSource.CRYPTOCOMPARE
            result.time_delta_hours = 0.0  # Daily close price
            
            # Daily close is approximate but high confidence
            result.valuation_status = ValuationStatus.EXACT
            result.confidence = 0.95
            return result
        
        # Try individual historical price lookup
        price = self.price_service.get_historical_price(asset, date_str)
        if price:
            result.price_usd = price
            result.total_usd = quantity * price
            result.valuation_status = ValuationStatus.EXACT
            result.price_source = PriceSource.CRYPTOCOMPARE
            result.time_delta_hours = 0.0
            result.confidence = 0.95
            return result
        
        # Try CoinGecko as fallback
        coin_id = self.price_service.coin_ids.get(asset)
        if coin_id:
            price = self.price_service._get_historical_price_coingecko(asset, date_str)
            if price:
                result.price_usd = price
                result.total_usd = quantity * price
                result.valuation_status = ValuationStatus.EXACT
                result.price_source = PriceSource.COINGECKO
                result.time_delta_hours = 0.0
                result.confidence = 0.90
                return result
        
        # Try nearest date (approximate match)
        nearest_result = self._find_nearest_price(asset, tx_dt, bulk_prices.get(asset, {}))
        if nearest_result:
            price, delta_hours, source = nearest_result
            result.price_usd = price
            result.total_usd = quantity * price
            result.time_delta_hours = delta_hours
            result.price_source = source
            
            # Determine confidence based on time delta
            if delta_hours <= self.EXACT_MATCH_WINDOW_HOURS:
                result.valuation_status = ValuationStatus.EXACT
                result.confidence = 0.95 - (delta_hours * 0.05)
            elif delta_hours <= self.APPROXIMATE_WINDOW_HOURS:
                result.valuation_status = ValuationStatus.APPROXIMATE
                result.confidence = 0.85 - (delta_hours * 0.02)
            else:
                result.valuation_status = ValuationStatus.APPROXIMATE
                result.confidence = max(0.5, 0.85 - (delta_hours * 0.01))
            
            return result
        
        # No price found
        result.error = f"No historical price data found for {asset}"
        result.valuation_status = ValuationStatus.UNAVAILABLE
        result.price_source = PriceSource.UNAVAILABLE
        result.confidence = 0.0
        return result
    
    def _find_nearest_price(
        self, 
        asset: str, 
        target_dt: datetime,
        bulk_prices: Dict[str, float]
    ) -> Optional[Tuple[float, float, PriceSource]]:
        """Find nearest available price within the approximate window"""
        if not bulk_prices:
            return None
        
        target_date = target_dt.date()
        best_price = None
        best_delta_days = float('inf')
        
        for date_str, price in bulk_prices.items():
            try:
                price_date = datetime.strptime(date_str, '%d-%m-%Y').date()
                delta_days = abs((target_date - price_date).days)
                
                if delta_days < best_delta_days:
                    best_delta_days = delta_days
                    best_price = price
            except ValueError:
                continue
        
        if best_price and best_delta_days <= (self.APPROXIMATE_WINDOW_HOURS / 24):
            return (best_price, best_delta_days * 24, PriceSource.CRYPTOCOMPARE)
        
        return None
