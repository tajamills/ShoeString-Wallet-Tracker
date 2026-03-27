"""
Unknown Transaction Reduction System

Auto-classifies high-confidence unknown transactions using pattern detection,
machine learning-style scoring, and user feedback loops.

Classification Types:
- internal_transfer: Transfer between user's own wallets
- external_transfer: Transfer to/from external wallets (taxable)
- swap: Token swap/exchange
- bridge: Cross-chain bridge transaction
- deposit: Exchange deposit
- withdrawal: Exchange withdrawal

Confidence Thresholds:
- > 0.95: Auto-classify
- 0.7 - 0.95: Suggest for user confirmation
- < 0.7: Leave unresolved
"""

import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ClassificationType(Enum):
    """Transaction classification types"""
    INTERNAL_TRANSFER = "internal_transfer"
    EXTERNAL_TRANSFER = "external_transfer"
    SWAP = "swap"
    BRIDGE = "bridge"
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    BUY = "buy"
    SELL = "sell"
    REWARD = "reward"
    STAKING = "staking"
    UNKNOWN = "unknown"


class ConfidenceLevel(Enum):
    """Confidence level thresholds"""
    AUTO_APPLY = "auto_apply"      # > 0.95
    SUGGEST = "suggest"            # 0.7 - 0.95
    UNRESOLVED = "unresolved"      # < 0.7


@dataclass
class PatternMatch:
    """A detected pattern match"""
    pattern_id: str
    pattern_type: str  # destination_wallet, source_wallet, timing, amount_range, asset
    pattern_value: str
    match_count: int
    transactions: List[str]  # tx_ids
    suggested_classification: str
    confidence: float
    reasoning: str


@dataclass
class ClassificationSuggestion:
    """Suggestion for classifying a transaction"""
    tx_id: str
    asset: str
    amount: float
    current_type: str
    suggested_type: str
    confidence: float
    confidence_level: ConfidenceLevel
    reasoning: List[str]
    pattern_matches: List[str]  # pattern_ids
    
    def to_dict(self) -> Dict:
        return {
            "tx_id": self.tx_id,
            "asset": self.asset,
            "amount": self.amount,
            "current_type": self.current_type,
            "suggested_type": self.suggested_type,
            "confidence": round(self.confidence, 3),
            "confidence_level": self.confidence_level.value,
            "reasoning": self.reasoning,
            "pattern_matches": self.pattern_matches
        }


@dataclass
class ClassificationMetrics:
    """Metrics for classification system"""
    total_unknown: int = 0
    auto_classified: int = 0
    suggested_count: int = 0
    unresolved_count: int = 0
    user_accepted: int = 0
    user_rejected: int = 0
    accuracy_rate: float = 0.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


class UnknownTransactionClassifier:
    """
    System for reducing unknown transactions through pattern detection
    and auto-classification.
    """
    
    # Confidence thresholds
    AUTO_APPLY_THRESHOLD = 0.95
    SUGGEST_THRESHOLD = 0.70
    
    # Known exchange addresses (partial list for pattern matching)
    EXCHANGE_KEYWORDS = [
        "coinbase", "binance", "kraken", "gemini", "kucoin", "okx",
        "crypto.com", "ftx", "huobi", "bitstamp", "bitfinex"
    ]
    
    # Bridge keywords
    BRIDGE_KEYWORDS = [
        "bridge", "wormhole", "multichain", "synapse", "hop", "across",
        "stargate", "layerzero", "portal", "celer", "polygon"
    ]
    
    # DEX/swap keywords
    SWAP_KEYWORDS = [
        "uniswap", "sushiswap", "pancake", "curve", "1inch", "0x",
        "paraswap", "dex", "swap", "router", "aggregator"
    ]
    
    def __init__(self, db):
        self.db = db
    
    async def analyze_unknown_transactions(
        self,
        user_id: str,
        limit: int = 10000
    ) -> Dict[str, Any]:
        """
        Analyze all unknown transactions and generate classification suggestions.
        
        Returns analysis with pattern detection and suggestions.
        """
        # Get unknown transactions
        unknown_txs = await self._get_unknown_transactions(user_id, limit)
        
        if not unknown_txs:
            return {
                "success": True,
                "unknown_count": 0,
                "patterns": [],
                "by_confidence": {
                    "auto_apply": [],
                    "suggest": [],
                    "unresolved": []
                },
                "suggestions": [],
                "metrics": ClassificationMetrics().to_dict()
            }
        
        # Get user's known wallets and linkages
        known_wallets = await self._get_user_wallets(user_id)
        linkages = await self._get_user_linkages(user_id)
        
        # Get historical classifications for learning
        historical = await self._get_historical_classifications(user_id)
        
        # Detect patterns
        patterns = await self._detect_patterns(unknown_txs, known_wallets, linkages, historical)
        
        # Generate suggestions for each unknown transaction
        suggestions = []
        auto_apply = []
        suggest_confirm = []
        unresolved = []
        
        for tx in unknown_txs:
            suggestion = self._generate_suggestion(
                tx, patterns, known_wallets, linkages, historical
            )
            suggestions.append(suggestion)
            
            if suggestion.confidence_level == ConfidenceLevel.AUTO_APPLY:
                auto_apply.append(suggestion)
            elif suggestion.confidence_level == ConfidenceLevel.SUGGEST:
                suggest_confirm.append(suggestion)
            else:
                unresolved.append(suggestion)
        
        # Calculate metrics
        metrics = ClassificationMetrics(
            total_unknown=len(unknown_txs),
            auto_classified=len(auto_apply),
            suggested_count=len(suggest_confirm),
            unresolved_count=len(unresolved)
        )
        
        # Calculate accuracy from historical feedback
        feedback_stats = await self._get_feedback_stats(user_id)
        if feedback_stats["total"] > 0:
            metrics.user_accepted = feedback_stats["accepted"]
            metrics.user_rejected = feedback_stats["rejected"]
            metrics.accuracy_rate = feedback_stats["accepted"] / feedback_stats["total"]
        
        return {
            "success": True,
            "unknown_count": len(unknown_txs),
            "patterns": [p.__dict__ for p in patterns[:50]],  # Limit patterns in response
            "by_confidence": {
                "auto_apply": [s.to_dict() for s in auto_apply[:100]],
                "suggest": [s.to_dict() for s in suggest_confirm[:100]],
                "unresolved": [s.to_dict() for s in unresolved[:100]]
            },
            "metrics": metrics.to_dict()
        }
    
    async def auto_classify_high_confidence(
        self,
        user_id: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Auto-classify transactions with confidence > 0.95.
        
        Only applies classifications that meet the auto-apply threshold.
        """
        # Get analysis
        analysis = await self.analyze_unknown_transactions(user_id)
        auto_apply = analysis.get("by_confidence", {}).get("auto_apply", [])
        
        if not auto_apply:
            return {
                "success": True,
                "dry_run": dry_run,
                "classified_count": 0,
                "message": "No transactions meet auto-apply threshold (>0.95)"
            }
        
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "classified_count": len(auto_apply),
                "would_classify": auto_apply
            }
        
        # Apply classifications
        batch_id = str(uuid.uuid4())
        classified = []
        
        for suggestion in auto_apply:
            result = await self._apply_classification(
                user_id=user_id,
                tx_id=suggestion["tx_id"],
                new_type=suggestion["suggested_type"],
                confidence=suggestion["confidence"],
                reasoning=suggestion["reasoning"],
                batch_id=batch_id,
                auto_applied=True
            )
            if result["success"]:
                classified.append(result)
        
        # Store batch for potential rollback
        await self._store_classification_batch(user_id, batch_id, classified)
        
        return {
            "success": True,
            "dry_run": False,
            "batch_id": batch_id,
            "classified_count": len(classified),
            "classified": classified
        }
    
    async def bulk_classify_by_pattern(
        self,
        user_id: str,
        pattern_id: str,
        classification: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Bulk classify all transactions matching a specific pattern.
        """
        # Find the pattern
        patterns_doc = await self.db.classification_patterns.find_one({
            "user_id": user_id,
            "pattern_id": pattern_id
        })
        
        if not patterns_doc:
            # Try to regenerate patterns
            analysis = await self.analyze_unknown_transactions(user_id)
            pattern = next(
                (p for p in analysis["patterns"] if p.get("pattern_id") == pattern_id),
                None
            )
            if not pattern:
                return {
                    "success": False,
                    "error": f"Pattern {pattern_id} not found"
                }
            tx_ids = pattern.get("transactions", [])
        else:
            tx_ids = patterns_doc.get("transactions", [])
        
        if not tx_ids:
            return {
                "success": False,
                "error": "No transactions in pattern"
            }
        
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "pattern_id": pattern_id,
                "would_classify": len(tx_ids),
                "classification": classification,
                "tx_ids": tx_ids[:50]  # Limit response
            }
        
        # Apply classifications
        batch_id = str(uuid.uuid4())
        classified = []
        
        for tx_id in tx_ids:
            result = await self._apply_classification(
                user_id=user_id,
                tx_id=tx_id,
                new_type=classification,
                confidence=0.85,  # Pattern-based confidence
                reasoning=[f"Bulk classified via pattern {pattern_id}"],
                batch_id=batch_id,
                auto_applied=False
            )
            if result["success"]:
                classified.append(result)
        
        await self._store_classification_batch(user_id, batch_id, classified)
        
        return {
            "success": True,
            "dry_run": False,
            "batch_id": batch_id,
            "pattern_id": pattern_id,
            "classified_count": len(classified)
        }
    
    async def bulk_classify_by_destination(
        self,
        user_id: str,
        destination_wallet: str,
        classification: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Bulk classify all unknown transactions to a specific destination wallet.
        """
        # Find matching transactions
        txs = await self.db.exchange_transactions.find({
            "user_id": user_id,
            "tx_type": "unknown",
            "$or": [
                {"destination_address": destination_wallet},
                {"destination_wallet": destination_wallet},
                {"to_address": destination_wallet}
            ]
        }).to_list(10000)
        
        if not txs:
            return {
                "success": True,
                "classified_count": 0,
                "message": f"No unknown transactions to {destination_wallet}"
            }
        
        tx_ids = [tx["tx_id"] for tx in txs]
        
        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "destination_wallet": destination_wallet,
                "would_classify": len(tx_ids),
                "classification": classification
            }
        
        # Apply classifications
        batch_id = str(uuid.uuid4())
        classified = []
        
        for tx_id in tx_ids:
            result = await self._apply_classification(
                user_id=user_id,
                tx_id=tx_id,
                new_type=classification,
                confidence=0.90,  # Destination-based confidence
                reasoning=[f"Bulk classified: same destination {destination_wallet[:16]}..."],
                batch_id=batch_id,
                auto_applied=False
            )
            if result["success"]:
                classified.append(result)
        
        await self._store_classification_batch(user_id, batch_id, classified)
        
        return {
            "success": True,
            "dry_run": False,
            "batch_id": batch_id,
            "destination_wallet": destination_wallet,
            "classified_count": len(classified)
        }
    
    async def apply_single_suggestion(
        self,
        user_id: str,
        tx_id: str,
        accept: bool,
        override_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Apply or reject a single classification suggestion.
        
        This is the feedback loop - user decisions improve future suggestions.
        """
        # Get the original suggestion
        tx = await self.db.exchange_transactions.find_one({
            "tx_id": tx_id,
            "user_id": user_id
        })
        
        if not tx:
            return {"success": False, "error": "Transaction not found"}
        
        # Get suggestion from analysis cache if available
        suggestion_cache = await self.db.classification_suggestions.find_one({
            "tx_id": tx_id,
            "user_id": user_id
        })
        
        suggested_type = suggestion_cache.get("suggested_type") if suggestion_cache else "unknown"
        
        # Determine final classification
        if accept:
            final_type = override_type or suggested_type
        else:
            # User rejected - keep as unknown or apply override
            final_type = override_type or "unknown"
        
        # Apply classification
        result = await self._apply_classification(
            user_id=user_id,
            tx_id=tx_id,
            new_type=final_type,
            confidence=1.0 if accept else 0.0,  # User decision = full confidence
            reasoning=["User classification" if not accept else "User accepted suggestion"],
            batch_id=None,
            auto_applied=False
        )
        
        # Record feedback for learning
        await self._record_feedback(
            user_id=user_id,
            tx_id=tx_id,
            suggested_type=suggested_type,
            user_decision=final_type,
            accepted=accept
        )
        
        return result
    
    async def get_classification_metrics(
        self,
        user_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get classification metrics over time.
        """
        since = datetime.now(timezone.utc) - timedelta(days=days)
        
        # Get current unknown count
        current_unknown = await self.db.exchange_transactions.count_documents({
            "user_id": user_id,
            "tx_type": "unknown"
        })
        
        # Get historical unknown counts
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "action": {"$in": ["auto_classification", "user_classification"]},
                "timestamp": {"$gte": since.isoformat()}
            }},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": {"$toDate": "$timestamp"}}},
                "auto_classified": {
                    "$sum": {"$cond": [{"$eq": ["$action", "auto_classification"]}, 1, 0]}
                },
                "user_classified": {
                    "$sum": {"$cond": [{"$eq": ["$action", "user_classification"]}, 1, 0]}
                }
            }},
            {"$sort": {"_id": 1}}
        ]
        
        daily_stats = await self.db.classification_audit.aggregate(pipeline).to_list(100)
        
        # Get accuracy stats
        feedback_stats = await self._get_feedback_stats(user_id)
        
        return {
            "success": True,
            "current_unknown": current_unknown,
            "period_days": days,
            "auto_classification_rate": feedback_stats.get("auto_rate", 0),
            "suggestion_accuracy": feedback_stats.get("accuracy", 0),
            "total_feedback": feedback_stats.get("total", 0),
            "accepted": feedback_stats.get("accepted", 0),
            "rejected": feedback_stats.get("rejected", 0),
            "daily_stats": daily_stats
        }
    
    async def rollback_classification_batch(
        self,
        user_id: str,
        batch_id: str
    ) -> Dict[str, Any]:
        """
        Rollback a batch of classifications.
        """
        batch = await self.db.classification_batches.find_one({
            "user_id": user_id,
            "batch_id": batch_id
        })
        
        if not batch:
            return {"success": False, "error": f"Batch {batch_id} not found"}
        
        reverted = 0
        for record in batch.get("classified", []):
            tx_id = record.get("tx_id")
            original_type = record.get("original_type", "unknown")
            
            await self.db.exchange_transactions.update_one(
                {"tx_id": tx_id, "user_id": user_id},
                {
                    "$set": {"tx_type": original_type},
                    "$unset": {"classification_info": ""}
                }
            )
            reverted += 1
        
        # Mark batch as rolled back
        await self.db.classification_batches.update_one(
            {"batch_id": batch_id},
            {"$set": {"rolled_back": True, "rolled_back_at": datetime.now(timezone.utc).isoformat()}}
        )
        
        return {
            "success": True,
            "batch_id": batch_id,
            "reverted_count": reverted
        }
    
    # === PRIVATE METHODS ===
    
    async def _get_unknown_transactions(self, user_id: str, limit: int) -> List[Dict]:
        """Get unknown transactions"""
        return await self.db.exchange_transactions.find({
            "user_id": user_id,
            "tx_type": "unknown"
        }).limit(limit).to_list(limit)
    
    async def _get_user_wallets(self, user_id: str) -> set:
        """Get user's known wallet addresses"""
        # From linkages
        linkages = await self.db.linkage_edges.find(
            {"user_id": user_id},
            {"from_address": 1, "to_address": 1}
        ).to_list(10000)
        
        wallets = set()
        for link in linkages:
            if link.get("from_address"):
                wallets.add(link["from_address"].lower())
            if link.get("to_address"):
                wallets.add(link["to_address"].lower())
        
        # From transactions with known classifications
        txs = await self.db.exchange_transactions.find(
            {
                "user_id": user_id,
                "tx_type": {"$in": ["buy", "sell", "receive", "send"]},
                "$or": [
                    {"source_wallet": {"$exists": True}},
                    {"wallet_address": {"$exists": True}}
                ]
            },
            {"source_wallet": 1, "wallet_address": 1, "from_address": 1, "to_address": 1}
        ).to_list(10000)
        
        for tx in txs:
            for field_name in ["source_wallet", "wallet_address", "from_address", "to_address"]:
                if tx.get(field_name):
                    wallets.add(str(tx[field_name]).lower())
        
        return wallets
    
    async def _get_user_linkages(self, user_id: str) -> Dict[str, str]:
        """Get mapping of linked addresses"""
        linkages = await self.db.linkage_edges.find(
            {"user_id": user_id}
        ).to_list(10000)
        
        link_map = {}
        for link in linkages:
            if link.get("from_address") and link.get("to_address"):
                link_map[link["from_address"].lower()] = link["to_address"].lower()
                link_map[link["to_address"].lower()] = link["from_address"].lower()
        
        return link_map
    
    async def _get_historical_classifications(self, user_id: str) -> Dict[str, Any]:
        """Get historical classification patterns from user decisions"""
        # Get user feedback
        feedback = await self.db.classification_feedback.find(
            {"user_id": user_id, "accepted": True}
        ).to_list(10000)
        
        # Build pattern map
        patterns = defaultdict(list)
        for fb in feedback:
            if fb.get("destination_address"):
                patterns[f"dest:{fb['destination_address']}"].append(fb["user_decision"])
            if fb.get("source_address"):
                patterns[f"src:{fb['source_address']}"].append(fb["user_decision"])
            if fb.get("asset"):
                patterns[f"asset:{fb['asset']}"].append(fb["user_decision"])
        
        # Calculate most common classification per pattern
        learned = {}
        for pattern_key, decisions in patterns.items():
            if decisions:
                most_common = max(set(decisions), key=decisions.count)
                confidence = decisions.count(most_common) / len(decisions)
                learned[pattern_key] = {
                    "classification": most_common,
                    "confidence": confidence,
                    "count": len(decisions)
                }
        
        return learned
    
    async def _detect_patterns(
        self,
        transactions: List[Dict],
        known_wallets: set,
        linkages: Dict,
        historical: Dict
    ) -> List[PatternMatch]:
        """Detect patterns in unknown transactions"""
        patterns = []
        
        # Group by destination
        by_destination = defaultdict(list)
        for tx in transactions:
            dest = (tx.get("destination_address") or tx.get("to_address") or "").lower()
            if dest:
                by_destination[dest].append(tx)
        
        for dest, txs in by_destination.items():
            if len(txs) >= 2:  # At least 2 transactions to same destination
                # Determine suggested classification
                if dest in known_wallets or dest in linkages:
                    suggested = "internal_transfer"
                    confidence = 0.95
                elif any(kw in dest for kw in self.EXCHANGE_KEYWORDS):
                    suggested = "deposit"
                    confidence = 0.90
                elif any(kw in dest for kw in self.BRIDGE_KEYWORDS):
                    suggested = "bridge"
                    confidence = 0.85
                else:
                    suggested = "external_transfer"
                    confidence = 0.75
                
                patterns.append(PatternMatch(
                    pattern_id=f"dest_{dest[:16]}_{len(txs)}",
                    pattern_type="destination_wallet",
                    pattern_value=dest,
                    match_count=len(txs),
                    transactions=[tx["tx_id"] for tx in txs],
                    suggested_classification=suggested,
                    confidence=confidence,
                    reasoning=f"{len(txs)} transactions to same destination"
                ))
        
        # Group by source
        by_source = defaultdict(list)
        for tx in transactions:
            src = (tx.get("source_address") or tx.get("from_address") or "").lower()
            if src:
                by_source[src].append(tx)
        
        for src, txs in by_source.items():
            if len(txs) >= 3:  # At least 3 transactions from same source
                if src in known_wallets or src in linkages:
                    suggested = "internal_transfer"
                    confidence = 0.90
                elif any(kw in src for kw in self.EXCHANGE_KEYWORDS):
                    suggested = "withdrawal"
                    confidence = 0.90
                else:
                    suggested = "receive"
                    confidence = 0.70
                
                patterns.append(PatternMatch(
                    pattern_id=f"src_{src[:16]}_{len(txs)}",
                    pattern_type="source_wallet",
                    pattern_value=src,
                    match_count=len(txs),
                    transactions=[tx["tx_id"] for tx in txs],
                    suggested_classification=suggested,
                    confidence=confidence,
                    reasoning=f"{len(txs)} transactions from same source"
                ))
        
        # Group by asset
        by_asset = defaultdict(list)
        for tx in transactions:
            asset = (tx.get("asset") or "").upper()
            if asset:
                by_asset[asset].append(tx)
        
        for asset, txs in by_asset.items():
            if len(txs) >= 5:  # Significant number of same asset
                # Check historical for this asset
                hist_key = f"asset:{asset}"
                if hist_key in historical and historical[hist_key]["confidence"] > 0.8:
                    suggested = historical[hist_key]["classification"]
                    confidence = historical[hist_key]["confidence"] * 0.9  # Slight discount
                else:
                    suggested = "unknown"
                    confidence = 0.50
                
                if suggested != "unknown":
                    patterns.append(PatternMatch(
                        pattern_id=f"asset_{asset}_{len(txs)}",
                        pattern_type="asset",
                        pattern_value=asset,
                        match_count=len(txs),
                        transactions=[tx["tx_id"] for tx in txs],
                        suggested_classification=suggested,
                        confidence=confidence,
                        reasoning=f"Historical pattern for {asset}"
                    ))
        
        # Store patterns for later use
        for pattern in patterns:
            await self.db.classification_patterns.update_one(
                {"pattern_id": pattern.pattern_id, "user_id": transactions[0].get("user_id")},
                {"$set": {
                    "user_id": transactions[0].get("user_id"),
                    **pattern.__dict__,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }},
                upsert=True
            )
        
        return sorted(patterns, key=lambda p: -p.confidence)
    
    def _generate_suggestion(
        self,
        tx: Dict,
        patterns: List[PatternMatch],
        known_wallets: set,
        linkages: Dict,
        historical: Dict
    ) -> ClassificationSuggestion:
        """Generate classification suggestion for a single transaction"""
        tx_id = tx.get("tx_id", "unknown")
        asset = (tx.get("asset") or "").upper()
        amount = float(tx.get("quantity", 0) or tx.get("amount", 0) or 0)
        
        reasoning = []
        pattern_matches = []
        confidence_scores = []
        
        dest = (tx.get("destination_address") or tx.get("to_address") or "").lower()
        src = (tx.get("source_address") or tx.get("from_address") or "").lower()
        notes = (tx.get("notes") or "").lower()
        
        # Check destination against known wallets
        if dest and dest in known_wallets:
            reasoning.append("Destination is user's known wallet")
            confidence_scores.append(0.95)
            suggested_type = "internal_transfer"
        elif dest and dest in linkages:
            reasoning.append("Destination is linked to user's wallet")
            confidence_scores.append(0.92)
            suggested_type = "internal_transfer"
        elif src and src in known_wallets:
            reasoning.append("Source is user's known wallet")
            confidence_scores.append(0.90)
            suggested_type = "send"
        else:
            suggested_type = "unknown"
        
        # Check against exchange keywords
        if suggested_type == "unknown":
            if any(kw in (dest + src + notes) for kw in self.EXCHANGE_KEYWORDS):
                reasoning.append("Matches exchange address pattern")
                confidence_scores.append(0.85)
                suggested_type = "deposit" if dest else "withdrawal"
        
        # Check against bridge keywords
        if suggested_type == "unknown":
            if any(kw in (dest + src + notes) for kw in self.BRIDGE_KEYWORDS):
                reasoning.append("Matches bridge transaction pattern")
                confidence_scores.append(0.80)
                suggested_type = "bridge"
        
        # Check against swap keywords
        if suggested_type == "unknown":
            if any(kw in (dest + src + notes) for kw in self.SWAP_KEYWORDS):
                reasoning.append("Matches swap/DEX pattern")
                confidence_scores.append(0.75)
                suggested_type = "swap"
        
        # Check patterns
        for pattern in patterns:
            if tx_id in pattern.transactions:
                pattern_matches.append(pattern.pattern_id)
                if suggested_type == "unknown" or pattern.confidence > max(confidence_scores, default=0):
                    suggested_type = pattern.suggested_classification
                    confidence_scores.append(pattern.confidence)
                    reasoning.append(pattern.reasoning)
        
        # Check historical learning
        hist_key = f"dest:{dest}" if dest else f"src:{src}"
        if hist_key in historical and historical[hist_key]["confidence"] > 0.7:
            learned = historical[hist_key]
            if suggested_type == "unknown" or learned["confidence"] > max(confidence_scores, default=0):
                suggested_type = learned["classification"]
                confidence_scores.append(learned["confidence"])
                reasoning.append(f"Learned from {learned['count']} previous decisions")
        
        # Calculate final confidence
        if confidence_scores:
            # Weighted average with bias toward highest
            confidence = (max(confidence_scores) * 0.6 + 
                         sum(confidence_scores) / len(confidence_scores) * 0.4)
        else:
            confidence = 0.30
            suggested_type = "unknown"
            reasoning.append("No matching patterns found")
        
        # Determine confidence level
        if confidence > self.AUTO_APPLY_THRESHOLD:
            confidence_level = ConfidenceLevel.AUTO_APPLY
        elif confidence > self.SUGGEST_THRESHOLD:
            confidence_level = ConfidenceLevel.SUGGEST
        else:
            confidence_level = ConfidenceLevel.UNRESOLVED
        
        return ClassificationSuggestion(
            tx_id=tx_id,
            asset=asset,
            amount=amount,
            current_type=tx.get("tx_type", "unknown"),
            suggested_type=suggested_type,
            confidence=confidence,
            confidence_level=confidence_level,
            reasoning=reasoning,
            pattern_matches=pattern_matches
        )
    
    async def _apply_classification(
        self,
        user_id: str,
        tx_id: str,
        new_type: str,
        confidence: float,
        reasoning: List[str],
        batch_id: Optional[str],
        auto_applied: bool
    ) -> Dict[str, Any]:
        """Apply classification to a transaction"""
        # Get current state
        tx = await self.db.exchange_transactions.find_one({
            "tx_id": tx_id,
            "user_id": user_id
        })
        
        if not tx:
            return {"success": False, "tx_id": tx_id, "error": "Transaction not found"}
        
        original_type = tx.get("tx_type", "unknown")
        
        # Update transaction
        await self.db.exchange_transactions.update_one(
            {"tx_id": tx_id, "user_id": user_id},
            {"$set": {
                "tx_type": new_type,
                "classification_info": {
                    "classified_at": datetime.now(timezone.utc).isoformat(),
                    "confidence": confidence,
                    "reasoning": reasoning,
                    "batch_id": batch_id,
                    "auto_applied": auto_applied,
                    "original_type": original_type
                }
            }}
        )
        
        # Record in audit
        await self.db.classification_audit.insert_one({
            "entry_id": str(uuid.uuid4()),
            "user_id": user_id,
            "tx_id": tx_id,
            "action": "auto_classification" if auto_applied else "user_classification",
            "original_type": original_type,
            "new_type": new_type,
            "confidence": confidence,
            "reasoning": reasoning,
            "batch_id": batch_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {
            "success": True,
            "tx_id": tx_id,
            "original_type": original_type,
            "new_type": new_type,
            "confidence": confidence
        }
    
    async def _store_classification_batch(
        self,
        user_id: str,
        batch_id: str,
        classified: List[Dict]
    ):
        """Store batch for potential rollback"""
        await self.db.classification_batches.insert_one({
            "user_id": user_id,
            "batch_id": batch_id,
            "classified": classified,
            "count": len(classified),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "rolled_back": False
        })
    
    async def _record_feedback(
        self,
        user_id: str,
        tx_id: str,
        suggested_type: str,
        user_decision: str,
        accepted: bool
    ):
        """Record user feedback for learning"""
        # Get transaction details for pattern learning
        tx = await self.db.exchange_transactions.find_one({
            "tx_id": tx_id,
            "user_id": user_id
        })
        
        await self.db.classification_feedback.insert_one({
            "feedback_id": str(uuid.uuid4()),
            "user_id": user_id,
            "tx_id": tx_id,
            "suggested_type": suggested_type,
            "user_decision": user_decision,
            "accepted": accepted,
            "asset": tx.get("asset") if tx else None,
            "destination_address": (tx.get("destination_address") or tx.get("to_address")) if tx else None,
            "source_address": (tx.get("source_address") or tx.get("from_address")) if tx else None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def _get_feedback_stats(self, user_id: str) -> Dict[str, Any]:
        """Get feedback statistics"""
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": None,
                "total": {"$sum": 1},
                "accepted": {"$sum": {"$cond": ["$accepted", 1, 0]}},
                "rejected": {"$sum": {"$cond": ["$accepted", 0, 1]}}
            }}
        ]
        
        result = await self.db.classification_feedback.aggregate(pipeline).to_list(1)
        
        if not result:
            return {"total": 0, "accepted": 0, "rejected": 0, "accuracy": 0, "auto_rate": 0}
        
        stats = result[0]
        total = stats.get("total", 0)
        accepted = stats.get("accepted", 0)
        
        return {
            "total": total,
            "accepted": accepted,
            "rejected": stats.get("rejected", 0),
            "accuracy": accepted / total if total > 0 else 0,
            "auto_rate": accepted / total if total > 0 else 0
        }
