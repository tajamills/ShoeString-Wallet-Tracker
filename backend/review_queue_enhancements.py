"""
Review Queue Enhancement Service

P2 Implementation:
- Bulk resolution for unknown_wallet review items
- Wallet-link suggestion engine for repeated unknown destinations
- Review queue grouping by source wallet / destination / pattern
"""

import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timezone
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)


class WalletLinkSuggestionEngine:
    """
    Suggests wallet linkages based on patterns in review queue.
    
    Analyzes repeated destinations, similar transaction patterns,
    and known wallet signatures to suggest which wallets belong to the user.
    """
    
    # Confidence thresholds
    HIGH_CONFIDENCE = 0.85
    MEDIUM_CONFIDENCE = 0.6
    LOW_CONFIDENCE = 0.4
    
    def __init__(self, db):
        self.db = db
    
    async def generate_suggestions(self, user_id: str) -> Dict[str, Any]:
        """
        Generate wallet link suggestions based on review queue patterns.
        
        Returns:
            Suggestions grouped by confidence level
        """
        results = {
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "suggestions": [],
            "high_confidence": [],
            "medium_confidence": [],
            "low_confidence": [],
            "statistics": {}
        }
        
        # Get all pending review items
        items = await self.db.review_queue.find({
            "user_id": user_id,
            "review_status": "pending"
        }).to_list(100000)
        
        if not items:
            return results
        
        # Analyze patterns
        destination_analysis = self._analyze_destinations(items)
        source_analysis = self._analyze_sources(items)
        amount_patterns = self._analyze_amount_patterns(items)
        
        # Generate suggestions
        suggestions = []
        
        # 1. Frequent destinations (likely user's wallets)
        for dest, data in destination_analysis.items():
            if data["count"] >= 3:
                confidence = self._calculate_destination_confidence(data)
                suggestion = {
                    "suggestion_id": str(uuid.uuid4()),
                    "type": "frequent_destination",
                    "wallet_address": dest,
                    "confidence": confidence,
                    "evidence": {
                        "transaction_count": data["count"],
                        "total_value": data["total_value"],
                        "assets": list(data["assets"]),
                        "date_range": data["date_range"]
                    },
                    "recommendation": "link_as_mine" if confidence >= self.MEDIUM_CONFIDENCE else "review_manually",
                    "affected_review_ids": data["review_ids"][:10]
                }
                suggestions.append(suggestion)
        
        # 2. Round-trip patterns (send then receive same amount)
        roundtrip_suggestions = await self._find_roundtrip_patterns(user_id, items)
        suggestions.extend(roundtrip_suggestions)
        
        # 3. Known exchange patterns
        exchange_suggestions = self._identify_exchange_patterns(items)
        suggestions.extend(exchange_suggestions)
        
        # Sort and categorize by confidence
        for suggestion in suggestions:
            if suggestion["confidence"] >= self.HIGH_CONFIDENCE:
                results["high_confidence"].append(suggestion)
            elif suggestion["confidence"] >= self.MEDIUM_CONFIDENCE:
                results["medium_confidence"].append(suggestion)
            else:
                results["low_confidence"].append(suggestion)
        
        results["suggestions"] = suggestions
        results["statistics"] = {
            "total_suggestions": len(suggestions),
            "high_confidence_count": len(results["high_confidence"]),
            "medium_confidence_count": len(results["medium_confidence"]),
            "low_confidence_count": len(results["low_confidence"]),
            "unique_destinations_analyzed": len(destination_analysis),
            "unique_sources_analyzed": len(source_analysis)
        }
        
        return results
    
    def _analyze_destinations(self, items: List[Dict]) -> Dict[str, Dict]:
        """Analyze destination wallet patterns"""
        destinations = defaultdict(lambda: {
            "count": 0,
            "total_value": 0,
            "assets": set(),
            "review_ids": [],
            "timestamps": []
        })
        
        for item in items:
            dest = item.get("destination_wallet", "")
            if not dest:
                continue
            
            destinations[dest]["count"] += 1
            destinations[dest]["total_value"] += float(item.get("amount", 0) or 0)
            destinations[dest]["assets"].add(item.get("asset", "UNKNOWN"))
            destinations[dest]["review_ids"].append(item.get("review_id", item.get("tx_id", "")))
            
            ts = item.get("timestamp")
            if ts:
                destinations[dest]["timestamps"].append(str(ts)[:10])
        
        # Calculate date ranges
        for dest, data in destinations.items():
            if data["timestamps"]:
                data["date_range"] = f"{min(data['timestamps'])} to {max(data['timestamps'])}"
            else:
                data["date_range"] = "unknown"
        
        return dict(destinations)
    
    def _analyze_sources(self, items: List[Dict]) -> Dict[str, Dict]:
        """Analyze source wallet patterns"""
        sources = defaultdict(lambda: {
            "count": 0,
            "total_value": 0,
            "assets": set()
        })
        
        for item in items:
            src = item.get("source_wallet", "")
            if not src:
                continue
            
            sources[src]["count"] += 1
            sources[src]["total_value"] += float(item.get("amount", 0) or 0)
            sources[src]["assets"].add(item.get("asset", "UNKNOWN"))
        
        return dict(sources)
    
    def _analyze_amount_patterns(self, items: List[Dict]) -> Dict[float, int]:
        """Find repeated transaction amounts"""
        amounts = defaultdict(int)
        for item in items:
            amount = round(float(item.get("amount", 0) or 0), 6)
            if amount > 0:
                amounts[amount] += 1
        return dict(amounts)
    
    def _calculate_destination_confidence(self, data: Dict) -> float:
        """Calculate confidence that destination is user's wallet"""
        confidence = 0.0
        
        # More transactions = higher confidence
        if data["count"] >= 10:
            confidence += 0.4
        elif data["count"] >= 5:
            confidence += 0.3
        elif data["count"] >= 3:
            confidence += 0.2
        
        # Multiple assets = higher confidence (user moves different coins)
        if len(data["assets"]) >= 3:
            confidence += 0.3
        elif len(data["assets"]) >= 2:
            confidence += 0.2
        elif len(data["assets"]) >= 1:
            confidence += 0.1
        
        # Higher value = more likely to be user's wallet
        if data["total_value"] >= 10000:
            confidence += 0.2
        elif data["total_value"] >= 1000:
            confidence += 0.1
        
        return min(confidence, 0.95)  # Cap at 95%
    
    async def _find_roundtrip_patterns(self, user_id: str, items: List[Dict]) -> List[Dict]:
        """Find send-then-receive patterns suggesting internal transfers"""
        suggestions = []
        
        # Group by asset and amount
        sends_by_amount = defaultdict(list)
        receives_by_amount = defaultdict(list)
        
        for item in items:
            tx_type = item.get("tx_type", "")
            amount = round(float(item.get("amount", 0) or 0), 6)
            asset = item.get("asset", "")
            
            key = f"{asset}:{amount}"
            
            if tx_type == "send":
                sends_by_amount[key].append(item)
            elif tx_type == "receive":
                receives_by_amount[key].append(item)
        
        # Find matching pairs
        for key in sends_by_amount:
            if key in receives_by_amount:
                sends = sends_by_amount[key]
                receives = receives_by_amount[key]
                
                asset, amount = key.split(":")
                
                suggestion = {
                    "suggestion_id": str(uuid.uuid4()),
                    "type": "roundtrip_pattern",
                    "wallet_address": "multiple",
                    "confidence": 0.7,
                    "evidence": {
                        "asset": asset,
                        "amount": float(amount),
                        "send_count": len(sends),
                        "receive_count": len(receives),
                        "pattern": "Matching send/receive amounts suggest internal transfers"
                    },
                    "recommendation": "review_as_group",
                    "affected_review_ids": [s.get("review_id", s.get("tx_id", "")) for s in sends[:5]]
                }
                suggestions.append(suggestion)
        
        return suggestions
    
    def _identify_exchange_patterns(self, items: List[Dict]) -> List[Dict]:
        """Identify known exchange wallet patterns"""
        suggestions = []
        
        # Known exchange prefixes/patterns
        exchange_patterns = {
            "coinbase": ["coinbase", "cb"],
            "binance": ["binance", "bnb"],
            "kraken": ["kraken"],
            "gemini": ["gemini"],
            "ftx": ["ftx"],
        }
        
        for item in items:
            dest = (item.get("destination_wallet") or "").lower()
            source = (item.get("source_wallet") or "").lower()
            
            for exchange, patterns in exchange_patterns.items():
                if any(p in dest or p in source for p in patterns):
                    suggestion = {
                        "suggestion_id": str(uuid.uuid4()),
                        "type": "exchange_detected",
                        "wallet_address": dest or source,
                        "confidence": 0.8,
                        "evidence": {
                            "exchange": exchange,
                            "pattern_match": True
                        },
                        "recommendation": "link_as_mine",
                        "affected_review_ids": [item.get("review_id", item.get("tx_id", ""))]
                    }
                    suggestions.append(suggestion)
                    break
        
        return suggestions


class BulkResolutionService:
    """
    Service for bulk resolving review queue items.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def bulk_resolve(
        self,
        user_id: str,
        review_ids: List[str] = None,
        category: str = None,
        destination_wallet: str = None,
        decision: str = "mine",
        reason: str = "bulk_resolution"
    ) -> Dict[str, Any]:
        """
        Bulk resolve multiple review items at once.
        
        Args:
            user_id: User ID
            review_ids: Specific review IDs to resolve (optional)
            category: Resolve all items of this category (optional)
            destination_wallet: Resolve all items to this destination (optional)
            decision: "mine" or "external"
            reason: Reason for bulk resolution
        
        Returns:
            Results of bulk resolution
        """
        results = {
            "user_id": user_id,
            "decision": decision,
            "reason": reason,
            "resolved_count": 0,
            "failed_count": 0,
            "resolved_ids": [],
            "failed_ids": [],
            "linkages_created": 0,
            "tax_events_created": 0
        }
        
        # Build query
        query = {"user_id": user_id, "review_status": "pending"}
        
        if review_ids:
            query["$or"] = [
                {"review_id": {"$in": review_ids}},
                {"tx_id": {"$in": review_ids}}
            ]
        
        if destination_wallet:
            query["destination_wallet"] = destination_wallet
        
        # Get items to resolve
        items = await self.db.review_queue.find(query).to_list(10000)
        
        if not items:
            results["message"] = "No matching items found"
            return results
        
        # Process each item
        for item in items:
            try:
                item_id = item.get("review_id") or item.get("tx_id")
                
                if decision == "mine":
                    # Create linkage edge
                    linkage = {
                        "linkage_id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "from_address": item.get("source_wallet"),
                        "to_address": item.get("destination_wallet"),
                        "confidence": 1.0,
                        "reason": reason,
                        "created_at": datetime.now(timezone.utc)
                    }
                    await self.db.linkage_edges.insert_one(linkage)
                    results["linkages_created"] += 1
                    
                elif decision == "external":
                    # Create tax event
                    tax_event = {
                        "event_id": str(uuid.uuid4()),
                        "user_id": user_id,
                        "tx_id": item.get("tx_id"),
                        "event_type": "disposal",
                        "asset": item.get("asset"),
                        "quantity": item.get("amount"),
                        "date_disposed": item.get("timestamp"),
                        "is_active": True,
                        "created_at": datetime.now(timezone.utc),
                        "source": "bulk_resolution"
                    }
                    await self.db.tax_events.insert_one(tax_event)
                    results["tax_events_created"] += 1
                
                # Update review status
                await self.db.review_queue.update_one(
                    {"_id": item["_id"]},
                    {"$set": {
                        "review_status": "resolved",
                        "resolution": decision,
                        "resolved_at": datetime.now(timezone.utc),
                        "resolution_reason": reason
                    }}
                )
                
                results["resolved_count"] += 1
                results["resolved_ids"].append(item_id)
                
            except Exception as e:
                logger.error(f"Failed to resolve {item_id}: {e}")
                results["failed_count"] += 1
                results["failed_ids"].append(item_id)
        
        return results
    
    async def bulk_resolve_by_category(
        self,
        user_id: str,
        category: str,
        decision: str,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Resolve all items of a specific category.
        
        Categories: unknown_wallet, bridge_transfer, dust_amount, etc.
        """
        # Get items by analyzing category
        all_items = await self.db.review_queue.find({
            "user_id": user_id,
            "review_status": "pending"
        }).to_list(100000)
        
        # Filter by category (using ReviewQueueAnalyzer logic)
        matching_ids = []
        for item in all_items:
            item_category = self._determine_category(item)
            if item_category == category:
                matching_ids.append(item.get("review_id") or item.get("tx_id"))
                if len(matching_ids) >= limit:
                    break
        
        if not matching_ids:
            return {
                "user_id": user_id,
                "category": category,
                "message": f"No pending items found in category '{category}'",
                "resolved_count": 0
            }
        
        return await self.bulk_resolve(
            user_id=user_id,
            review_ids=matching_ids,
            decision=decision,
            reason=f"bulk_category_{category}"
        )
    
    def _determine_category(self, item: Dict) -> str:
        """Determine category of a review item"""
        source = (item.get("source_wallet") or "").lower()
        dest = (item.get("destination_wallet") or "").lower()
        amount = float(item.get("amount", 0) or 0)
        
        if amount < 0.01:
            return "dust_amount"
        
        bridge_keywords = ["bridge", "wormhole", "multichain", "synapse"]
        if any(k in source or k in dest for k in bridge_keywords):
            return "bridge_transfer"
        
        return "unknown_wallet"


class ReviewQueueGroupingService:
    """
    Groups review queue items by source wallet, destination, or pattern.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def group_review_queue(self, user_id: str) -> Dict[str, Any]:
        """
        Group review queue items for easier bulk processing.
        """
        items = await self.db.review_queue.find({
            "user_id": user_id,
            "review_status": "pending"
        }).to_list(100000)
        
        results = {
            "user_id": user_id,
            "total_items": len(items),
            "by_destination": {},
            "by_source": {},
            "by_asset": {},
            "by_amount_range": {},
            "actionable_groups": []
        }
        
        if not items:
            return results
        
        # Group by destination
        by_dest = defaultdict(list)
        for item in items:
            dest = item.get("destination_wallet", "unknown")
            by_dest[dest].append(item)
        
        for dest, group_items in sorted(by_dest.items(), key=lambda x: -len(x[1])):
            if len(group_items) >= 2:  # Only show groups with 2+ items
                results["by_destination"][dest[:20] + "..."] = {
                    "count": len(group_items),
                    "total_value": sum(float(i.get("amount", 0) or 0) for i in group_items),
                    "assets": list(set(i.get("asset", "?") for i in group_items)),
                    "review_ids": [i.get("review_id") or i.get("tx_id") for i in group_items[:10]]
                }
        
        # Group by source
        by_src = defaultdict(list)
        for item in items:
            src = item.get("source_wallet", "unknown")
            by_src[src].append(item)
        
        for src, group_items in sorted(by_src.items(), key=lambda x: -len(x[1])):
            if len(group_items) >= 2:
                results["by_source"][src[:20] + "..."] = {
                    "count": len(group_items),
                    "total_value": sum(float(i.get("amount", 0) or 0) for i in group_items),
                    "assets": list(set(i.get("asset", "?") for i in group_items))
                }
        
        # Group by asset
        by_asset = defaultdict(list)
        for item in items:
            asset = item.get("asset", "UNKNOWN")
            by_asset[asset].append(item)
        
        for asset, group_items in sorted(by_asset.items(), key=lambda x: -len(x[1])):
            results["by_asset"][asset] = {
                "count": len(group_items),
                "total_value": sum(float(i.get("amount", 0) or 0) for i in group_items)
            }
        
        # Group by amount range
        ranges = [
            ("dust", 0, 1),
            ("small", 1, 100),
            ("medium", 100, 1000),
            ("large", 1000, 10000),
            ("very_large", 10000, float("inf"))
        ]
        
        for range_name, low, high in ranges:
            matching = [i for i in items if low <= float(i.get("amount", 0) or 0) < high]
            if matching:
                results["by_amount_range"][range_name] = {
                    "count": len(matching),
                    "range": f"${low} - ${high if high != float('inf') else '∞'}"
                }
        
        # Create actionable groups (recommendations)
        for dest, data in results["by_destination"].items():
            if data["count"] >= 5:
                results["actionable_groups"].append({
                    "group_type": "frequent_destination",
                    "identifier": dest,
                    "count": data["count"],
                    "suggestion": "Consider bulk linking as 'mine' if this is your wallet",
                    "action_endpoint": f"/api/custody/bulk-resolve?destination={dest}&decision=mine"
                })
        
        return results
