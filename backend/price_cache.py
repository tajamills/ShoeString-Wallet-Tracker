"""
MongoDB-backed price cache for persistent historical price storage.
Eliminates redundant API calls across requests.
"""
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone
import os
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

MONGO_URL = os.environ.get('MONGO_URL', '')
DB_NAME = os.environ.get('DB_NAME', 'crypto_bag_tracker')

_client = None
_db = None


def _get_db():
    global _client, _db
    if _db is None and MONGO_URL:
        _client = AsyncIOMotorClient(MONGO_URL)
        _db = _client[DB_NAME]
    return _db


async def get_cached_price(symbol: str, date_str: str) -> Optional[float]:
    """Get cached historical price from MongoDB."""
    db = _get_db()
    if not db:
        return None
    try:
        doc = await db.price_cache.find_one(
            {"symbol": symbol.upper(), "date": date_str},
            {"_id": 0, "price": 1}
        )
        if doc:
            return doc.get("price")
    except Exception as e:
        logger.debug(f"Price cache read error: {e}")
    return None


async def set_cached_price(symbol: str, date_str: str, price: float):
    """Store historical price in MongoDB cache."""
    db = _get_db()
    if not db:
        return
    try:
        await db.price_cache.update_one(
            {"symbol": symbol.upper(), "date": date_str},
            {"$set": {"symbol": symbol.upper(), "date": date_str, "price": price, "cached_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
    except Exception as e:
        logger.debug(f"Price cache write error: {e}")


async def batch_get_cached_prices(keys: List[Dict]) -> Dict[str, float]:
    """
    Batch fetch cached prices.
    keys: [{"symbol": "ETH", "date": "15-01-2024"}, ...]
    Returns: {"ETH_15-01-2024": 2300.0, ...}
    """
    db = _get_db()
    if not db or not keys:
        return {}

    try:
        conditions = [{"symbol": k["symbol"].upper(), "date": k["date"]} for k in keys]
        cursor = db.price_cache.find(
            {"$or": conditions},
            {"_id": 0, "symbol": 1, "date": 1, "price": 1}
        )
        results = {}
        async for doc in cursor:
            cache_key = f"{doc['symbol']}_{doc['date']}"
            results[cache_key] = doc["price"]
        return results
    except Exception as e:
        logger.debug(f"Batch price cache read error: {e}")
        return {}


async def batch_set_cached_prices(prices: Dict[str, float]):
    """
    Batch store prices. Keys format: "SYMBOL_DD-MM-YYYY"
    """
    db = _get_db()
    if not db or not prices:
        return
    try:
        from pymongo import UpdateOne
        ops = []
        for cache_key, price in prices.items():
            parts = cache_key.split("_", 1)
            if len(parts) != 2:
                continue
            symbol, date_str = parts
            ops.append(UpdateOne(
                {"symbol": symbol, "date": date_str},
                {"$set": {"symbol": symbol, "date": date_str, "price": price, "cached_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True
            ))
        if ops:
            await db.price_cache.bulk_write(ops, ordered=False)
    except Exception as e:
        logger.debug(f"Batch price cache write error: {e}")


async def ensure_indexes():
    """Create indexes for price cache collection."""
    db = _get_db()
    if not db:
        return
    try:
        await db.price_cache.create_index([("symbol", 1), ("date", 1)], unique=True)
    except Exception:
        pass
