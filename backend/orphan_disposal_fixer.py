"""
Orphan Disposal Fixer and Review Queue Analyzer

Fixes for P0 issues:
1. Root-cause and fix orphan disposals
2. Categorize unresolved review queue items by cause and frequency
"""

import asyncio
import logging
from typing import Dict, List, Tuple, Any
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)


class OrphanDisposalAnalyzer:
    """Analyzes and fixes orphan disposal issues"""
    
    def __init__(self, db):
        self.db = db
    
    async def analyze_orphan_disposals(self, user_id: str) -> Dict[str, Any]:
        """
        Analyze all assets for orphan disposal issues.
        
        Returns:
            Detailed analysis of orphan disposals with root causes
        """
        results = {
            "user_id": user_id,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "assets_analyzed": 0,
            "orphan_assets": [],
            "root_causes": [],
            "recommended_fixes": []
        }
        
        # Get all transactions
        txs = await self.db.exchange_transactions.find(
            {"user_id": user_id}
        ).to_list(100000)
        
        # Group by asset
        by_asset = defaultdict(list)
        for tx in txs:
            asset = tx.get("asset", "UNKNOWN")
            by_asset[asset].append(tx)
        
        results["assets_analyzed"] = len(by_asset)
        
        for asset, asset_txs in by_asset.items():
            analysis = self._analyze_asset(asset, asset_txs)
            
            if analysis["is_orphan"]:
                results["orphan_assets"].append(analysis)
                results["root_causes"].extend(analysis["root_causes"])
                results["recommended_fixes"].extend(analysis["recommended_fixes"])
        
        # Deduplicate and prioritize fixes
        results["root_causes"] = list(set(results["root_causes"]))
        results["recommended_fixes"] = self._prioritize_fixes(results["recommended_fixes"])
        
        return results
    
    def _analyze_asset(self, asset: str, txs: List[Dict]) -> Dict[str, Any]:
        """Analyze a single asset for orphan disposal"""
        analysis = {
            "asset": asset,
            "total_transactions": len(txs),
            "is_orphan": False,
            "acquired": Decimal("0"),
            "disposed": Decimal("0"),
            "gap": Decimal("0"),
            "breakdown": {},
            "root_causes": [],
            "recommended_fixes": [],
            "problematic_transactions": []
        }
        
        # Categorize transactions
        categories = defaultdict(lambda: {"count": 0, "quantity": Decimal("0"), "missing_price": 0})
        
        for tx in txs:
            tx_type = tx.get("tx_type", "unknown")
            chain_status = tx.get("chain_status", "none")
            qty = Decimal(str(tx.get("quantity", 0) or tx.get("amount", 0) or 0))
            price_usd = tx.get("price_usd")
            total_usd = tx.get("total_usd")
            
            key = f"{tx_type}|{chain_status}"
            categories[key]["count"] += 1
            categories[key]["quantity"] += qty
            
            if price_usd is None or total_usd is None:
                categories[key]["missing_price"] += 1
                analysis["problematic_transactions"].append({
                    "tx_id": tx.get("tx_id"),
                    "tx_type": tx_type,
                    "issue": "missing_price_data",
                    "quantity": float(qty)
                })
            
            # Classify as acquisition or disposal
            if tx_type in ["buy", "trade", "reward", "staking", "airdrop", "mining", "interest", "convert"]:
                analysis["acquired"] += qty
            elif tx_type == "receive" and chain_status != "linked":
                # Non-linked receives could be acquisitions
                analysis["acquired"] += qty
            elif tx_type == "sell":
                analysis["disposed"] += qty
            elif tx_type == "send" and chain_status == "external":
                analysis["disposed"] += qty
        
        analysis["breakdown"] = {k: {"count": v["count"], "quantity": float(v["quantity"]), "missing_price": v["missing_price"]} 
                                  for k, v in categories.items()}
        
        analysis["gap"] = analysis["acquired"] - analysis["disposed"]
        analysis["is_orphan"] = analysis["gap"] < 0
        
        # Identify root causes
        if analysis["is_orphan"]:
            # Check for missing price data
            missing_price_sells = sum(
                v["missing_price"] for k, v in categories.items() 
                if k.startswith("sell")
            )
            if missing_price_sells > 0:
                analysis["root_causes"].append(f"MISSING_PRICE_DATA: {missing_price_sells} sells without USD value for {asset}")
                analysis["recommended_fixes"].append({
                    "asset": asset,
                    "fix_type": "fetch_historical_prices",
                    "priority": "high",
                    "description": f"Fetch historical prices for {missing_price_sells} {asset} sell transactions"
                })
            
            # Check for sells that might be conversions
            sell_count = categories.get("sell|pending", {}).get("count", 0) + categories.get("sell|none", {}).get("count", 0)
            if sell_count > 0 and asset in ["USDC", "USD", "USDT"]:
                analysis["root_causes"].append(f"STABLECOIN_OFFRAMP: {asset} sells are likely fiat conversions, may need matching acquisition from other crypto sells")
                analysis["recommended_fixes"].append({
                    "asset": asset,
                    "fix_type": "create_implicit_acquisitions",
                    "priority": "high",
                    "description": f"Create {asset} acquisition records for proceeds from selling other crypto"
                })
            
            # Check for unresolved transfers
            unresolved_sends = categories.get("send|pending", {}).get("count", 0) + categories.get("send|none", {}).get("count", 0)
            if unresolved_sends > 0:
                analysis["root_causes"].append(f"UNRESOLVED_TRANSFERS: {unresolved_sends} sends without chain resolution for {asset}")
                analysis["recommended_fixes"].append({
                    "asset": asset,
                    "fix_type": "resolve_chain_breaks",
                    "priority": "medium",
                    "description": f"Resolve {unresolved_sends} unresolved send transactions"
                })
        
        return analysis
    
    def _prioritize_fixes(self, fixes: List[Dict]) -> List[Dict]:
        """Prioritize and deduplicate fixes"""
        # Group by fix type and asset
        grouped = {}
        for fix in fixes:
            key = f"{fix['fix_type']}|{fix['asset']}"
            if key not in grouped:
                grouped[key] = fix
        
        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_fixes = sorted(
            grouped.values(),
            key=lambda x: priority_order.get(x.get("priority", "low"), 99)
        )
        
        return sorted_fixes
    
    async def create_implicit_acquisitions(self, user_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        Create implicit acquisition records for stablecoins.
        
        When crypto is sold, the proceeds (in USDC/USD) should create an acquisition record.
        This fixes the USDC orphan issue.
        """
        results = {
            "user_id": user_id,
            "dry_run": dry_run,
            "acquisitions_to_create": [],
            "total_value": 0
        }
        
        # Find all sells of non-stablecoin assets that have USD value
        sells = await self.db.exchange_transactions.find({
            "user_id": user_id,
            "tx_type": "sell",
            "asset": {"$nin": ["USDC", "USD", "USDT", "DAI", "BUSD"]}
        }).to_list(100000)
        
        for sell in sells:
            total_usd = sell.get("total_usd")
            if total_usd and float(total_usd) > 0:
                # This sell generated USD proceeds - create USDC acquisition
                acquisition = {
                    "user_id": user_id,
                    "tx_id": f"implicit_usdc_{sell.get('tx_id', 'unknown')}",
                    "exchange": sell.get("exchange", "unknown"),
                    "tx_type": "implicit_acquisition",
                    "asset": "USDC",
                    "quantity": float(total_usd),
                    "amount": float(total_usd),
                    "price_usd": 1.0,
                    "total_usd": float(total_usd),
                    "timestamp": sell.get("timestamp"),
                    "chain_status": "linked",
                    "source_tx_id": sell.get("tx_id"),
                    "source_asset": sell.get("asset"),
                    "notes": f"Implicit USDC acquisition from selling {sell.get('asset')}"
                }
                
                results["acquisitions_to_create"].append(acquisition)
                results["total_value"] += float(total_usd)
        
        if not dry_run and results["acquisitions_to_create"]:
            # Actually create the records
            await self.db.exchange_transactions.insert_many(results["acquisitions_to_create"])
            results["created"] = len(results["acquisitions_to_create"])
        
        return results


class ReviewQueueAnalyzer:
    """Analyzes and categorizes review queue items"""
    
    # Known cause categories
    CAUSE_CATEGORIES = {
        "bridge_transfer": "Bridge/Cross-chain Transfer",
        "dex_swap": "DEX/Swap Transaction",
        "exchange_withdrawal": "Exchange Withdrawal",
        "exchange_deposit": "Exchange Deposit",
        "unknown_wallet": "Unknown Wallet Interaction",
        "contract_interaction": "Smart Contract Interaction",
        "dust_amount": "Dust/Small Amount Transfer",
        "missing_counterparty": "Missing Counterparty Transaction"
    }
    
    def __init__(self, db):
        self.db = db
    
    async def categorize_review_queue(self, user_id: str) -> Dict[str, Any]:
        """
        Categorize all review queue items by cause and frequency.
        
        Returns:
            Breakdown of review items by category
        """
        results = {
            "user_id": user_id,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "total_items": 0,
            "by_category": {},
            "by_asset": {},
            "by_status": {},
            "top_patterns": [],
            "recommendations": []
        }
        
        # Get all review queue items
        items = await self.db.review_queue.find(
            {"user_id": user_id}
        ).to_list(100000)
        
        results["total_items"] = len(items)
        
        if not items:
            return results
        
        # Categorize each item
        categorized = defaultdict(list)
        by_asset = defaultdict(lambda: {"count": 0, "total_amount": 0})
        by_status = defaultdict(int)
        
        for item in items:
            category = self._determine_category(item)
            categorized[category].append(item)
            
            asset = item.get("asset", "UNKNOWN")
            amount = float(item.get("amount", 0) or item.get("quantity", 0) or 0)
            by_asset[asset]["count"] += 1
            by_asset[asset]["total_amount"] += amount
            
            status = item.get("review_status", "pending")
            by_status[status] += 1
        
        # Build summary
        for category, items_list in categorized.items():
            results["by_category"][category] = {
                "count": len(items_list),
                "percentage": round(len(items_list) / len(items) * 100, 1),
                "sample_tx_ids": [i.get("tx_id") for i in items_list[:3]]
            }
        
        results["by_asset"] = dict(by_asset)
        results["by_status"] = dict(by_status)
        
        # Find patterns
        results["top_patterns"] = self._find_patterns(items)
        
        # Generate recommendations
        results["recommendations"] = self._generate_recommendations(categorized, by_asset)
        
        return results
    
    def _determine_category(self, item: Dict) -> str:
        """Determine the category of a review queue item"""
        source_wallet = (item.get("source_wallet") or "").lower()
        dest_wallet = (item.get("destination_wallet") or "").lower()
        tx_type = item.get("tx_type", "")
        amount = float(item.get("amount", 0) or 0)
        notes = (item.get("notes") or "").lower()
        
        # Check for dust amounts (< $1 value)
        if amount < 0.01:
            return "dust_amount"
        
        # Check for bridge transfers
        bridge_keywords = ["bridge", "wormhole", "multichain", "synapse", "hop", "across", "stargate", "layerzero"]
        if any(kw in source_wallet or kw in dest_wallet or kw in notes for kw in bridge_keywords):
            return "bridge_transfer"
        
        # Check for DEX swaps
        dex_keywords = ["uniswap", "sushiswap", "pancake", "curve", "1inch", "0x", "paraswap", "dex"]
        if any(kw in source_wallet or kw in dest_wallet or kw in notes for kw in dex_keywords):
            return "dex_swap"
        
        # Check for exchange interactions
        exchange_keywords = ["coinbase", "binance", "kraken", "gemini", "ftx", "exchange"]
        if any(kw in source_wallet or kw in dest_wallet for kw in exchange_keywords):
            if tx_type == "send":
                return "exchange_deposit"
            else:
                return "exchange_withdrawal"
        
        # Check for smart contract (0x addresses with lots of transactions)
        if source_wallet.startswith("0x") or dest_wallet.startswith("0x"):
            return "contract_interaction"
        
        # Default
        return "unknown_wallet"
    
    def _find_patterns(self, items: List[Dict]) -> List[Dict]:
        """Find common patterns in review queue items"""
        patterns = []
        
        # Pattern 1: Same source/destination appearing multiple times
        source_counts = defaultdict(int)
        dest_counts = defaultdict(int)
        
        for item in items:
            source = item.get("source_wallet", "")
            dest = item.get("destination_wallet", "")
            if source:
                source_counts[source] += 1
            if dest:
                dest_counts[dest] += 1
        
        # Find frequently appearing wallets
        for wallet, count in sorted(source_counts.items(), key=lambda x: -x[1])[:5]:
            if count >= 3:
                patterns.append({
                    "pattern": "frequent_source",
                    "wallet": wallet[:20] + "...",
                    "count": count,
                    "suggestion": "This wallet appears frequently - likely your own wallet or known service"
                })
        
        for wallet, count in sorted(dest_counts.items(), key=lambda x: -x[1])[:5]:
            if count >= 3:
                patterns.append({
                    "pattern": "frequent_destination",
                    "wallet": wallet[:20] + "...",
                    "count": count,
                    "suggestion": "This destination appears frequently - likely your own wallet or known service"
                })
        
        # Pattern 2: Same amount transfers
        amount_counts = defaultdict(int)
        for item in items:
            amount = round(float(item.get("amount", 0) or 0), 4)
            if amount > 0:
                amount_counts[amount] += 1
        
        for amount, count in sorted(amount_counts.items(), key=lambda x: -x[1])[:3]:
            if count >= 3:
                patterns.append({
                    "pattern": "repeated_amount",
                    "amount": amount,
                    "count": count,
                    "suggestion": "Repeated transfer amount - could be automated transfers or internal moves"
                })
        
        return patterns
    
    def _generate_recommendations(self, categorized: Dict, by_asset: Dict) -> List[Dict]:
        """Generate recommendations for resolving review queue"""
        recommendations = []
        
        # If many dust amounts, suggest bulk ignore
        dust_count = len(categorized.get("dust_amount", []))
        if dust_count > 10:
            recommendations.append({
                "priority": "low",
                "action": "bulk_ignore_dust",
                "count": dust_count,
                "description": f"Ignore {dust_count} dust transactions (amounts < $0.01)"
            })
        
        # If many bridge transfers, suggest reviewing chain links
        bridge_count = len(categorized.get("bridge_transfer", []))
        if bridge_count > 5:
            recommendations.append({
                "priority": "high",
                "action": "review_bridge_transfers",
                "count": bridge_count,
                "description": f"Review {bridge_count} bridge transfers - likely internal moves that should be linked"
            })
        
        # Asset-specific recommendations
        for asset, data in sorted(by_asset.items(), key=lambda x: -x[1]["count"]):
            if data["count"] > 10:
                recommendations.append({
                    "priority": "medium",
                    "action": f"review_{asset.lower()}_transfers",
                    "count": data["count"],
                    "description": f"Review {data['count']} {asset} transfers totaling {data['total_amount']:.4f} {asset}"
                })
        
        return recommendations


async def run_p0_analysis(db, user_id: str) -> Dict[str, Any]:
    """Run complete P0 analysis"""
    orphan_analyzer = OrphanDisposalAnalyzer(db)
    review_analyzer = ReviewQueueAnalyzer(db)
    
    # Analyze orphans
    orphan_results = await orphan_analyzer.analyze_orphan_disposals(user_id)
    
    # Categorize review queue
    review_results = await review_analyzer.categorize_review_queue(user_id)
    
    return {
        "orphan_analysis": orphan_results,
        "review_queue_analysis": review_results,
        "summary": {
            "orphan_assets": len(orphan_results["orphan_assets"]),
            "root_causes": len(orphan_results["root_causes"]),
            "review_items": review_results["total_items"],
            "review_categories": len(review_results["by_category"]),
            "total_fixes_needed": len(orphan_results["recommended_fixes"]) + len(review_results["recommendations"])
        }
    }
