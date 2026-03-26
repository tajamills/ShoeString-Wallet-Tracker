"""
Linkage Engine Service - Layer 2 of Chain of Custody System

Handles wallet linkage, cluster formation, and chain break detection.
Implements the identity layer that maps addresses to owned wallet clusters.

Architecture:
- Layer 1: Canonical Ledger (immutable transaction data)
- Layer 2: Linkage Engine (this service - identity/ownership)
- Layer 3: Chain of Custody (user-facing custody trails)
"""

import os
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum
import hashlib
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

logger = logging.getLogger(__name__)


class LinkType(str, Enum):
    """Types of linkage between addresses"""
    USER_CONFIRMED = "user_confirmed"        # User explicitly linked
    SELF_TRANSFER = "self_transfer"          # Direct transfer between owned wallets
    BRIDGE_TRANSFER = "bridge_transfer"      # Cross-chain bridge
    CEX_WITHDRAWAL = "cex_withdrawal"        # Exchange withdrawal
    CEX_DEPOSIT = "cex_deposit"              # Exchange deposit
    CONTRACT_MEDIATED = "contract_mediated"  # Transfer via smart contract
    WALLET_SWEEP = "wallet_sweep"            # Consolidation/sweep
    INFERRED = "inferred"                    # Heuristic match


class ChainStatus(str, Enum):
    """Status of chain of custody for a transaction"""
    LINKED = "linked"              # Part of owned custody chain
    UNLINKED = "unlinked"          # Chain break detected, pending review
    EXTERNAL = "external"          # Confirmed external transfer
    PENDING_REVIEW = "pending_review"  # Awaiting user decision


class ReviewStatus(str, Enum):
    """Status of items in review queue"""
    PENDING = "pending"
    RESOLVED_YES = "resolved_yes"      # User confirmed ownership
    RESOLVED_NO = "resolved_no"        # User confirmed external
    RESOLVED_IGNORE = "resolved_ignore"  # User chose to ignore
    AUTO_RESOLVED = "auto_resolved"    # System auto-resolved


class ConfidenceLevel:
    """Confidence thresholds for auto-linking"""
    USER_CONFIRMED = 1.0
    DETERMINISTIC = 0.95  # Bridge, exact self-transfer
    STRONG_MATCH = 0.8    # High confidence inference
    HEURISTIC = 0.5       # Pattern-based only
    LOW = 0.3             # Weak signal
    
    # Auto-link threshold
    AUTO_LINK_THRESHOLD = 0.95
    # Prompt user threshold
    PROMPT_THRESHOLD = 0.5


# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'crypto_tracker')
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


class LinkageEngineService:
    """
    Core linkage engine for wallet identity management.
    
    Responsibilities:
    - Create and manage linkage edges between addresses
    - Form wallet clusters from high-confidence edges
    - Detect chain breaks in custody trail
    - Generate review prompts for user decisions
    - Track tax events from custody resolutions
    """
    
    def __init__(self):
        # Matching configuration
        self.config = {
            'time_window_hours': 24,           # Max time between matched transfers
            'amount_tolerance_percent': 2.0,    # Fee/slippage tolerance
            'bridge_time_window_hours': 72,    # Bridges can be slower
            'cex_time_window_hours': 48,       # CEX withdrawals can have delays
        }
        
        # Token equivalencies across chains (bridged assets)
        self.token_equivalencies = {
            'ETH': ['ETH', 'WETH', 'stETH', 'rETH'],
            'BTC': ['BTC', 'WBTC', 'renBTC', 'tBTC'],
            'USDC': ['USDC', 'USDC.e', 'USDbC'],
            'USDT': ['USDT'],
            'DAI': ['DAI', 'xDAI'],
        }
    
    # ========================================
    # LINKAGE EDGE MANAGEMENT
    # ========================================
    
    async def create_linkage_edge(
        self,
        user_id: str,
        from_address: str,
        to_address: str,
        link_type: LinkType,
        confidence: float,
        reason: str,
        evidence_id: Optional[str] = None,
        chain: str = "ethereum",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        Create a new linkage edge between two addresses.
        
        Args:
            user_id: User who owns these addresses
            from_address: Source address
            to_address: Destination address
            link_type: Type of linkage
            confidence: Confidence score (0.0 - 1.0)
            reason: Machine-readable reason code
            evidence_id: Optional transaction ID as evidence
            chain: Blockchain network
            metadata: Additional context
        
        Returns:
            Created edge document
        """
        edge_id = str(uuid.uuid4())
        
        edge = {
            "id": edge_id,
            "user_id": user_id,
            "from_address": from_address.lower(),
            "to_address": to_address.lower(),
            "link_type": link_type.value if isinstance(link_type, LinkType) else link_type,
            "confidence": confidence,
            "reason": reason,
            "reason_human": self._get_human_readable_reason(reason, link_type),
            "evidence_id": evidence_id,
            "chain": chain,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc),
            "is_active": True,
            "revoked_at": None,
            "revoked_reason": None
        }
        
        # Check for existing edge
        existing = await db.linkage_edges.find_one({
            "user_id": user_id,
            "from_address": edge["from_address"],
            "to_address": edge["to_address"],
            "is_active": True
        })
        
        if existing:
            # Update if new confidence is higher
            if confidence > existing.get("confidence", 0):
                await db.linkage_edges.update_one(
                    {"id": existing["id"]},
                    {"$set": {
                        "confidence": confidence,
                        "reason": reason,
                        "reason_human": edge["reason_human"],
                        "link_type": edge["link_type"],
                        "updated_at": datetime.now(timezone.utc)
                    }}
                )
                logger.info(f"Updated linkage edge {existing['id']} with higher confidence {confidence}")
            return existing
        
        await db.linkage_edges.insert_one(edge)
        logger.info(f"Created linkage edge: {from_address[:8]}...→{to_address[:8]}... ({link_type}, conf={confidence})")
        
        # Auto-update clusters if confidence is high enough
        if confidence >= ConfidenceLevel.AUTO_LINK_THRESHOLD:
            await self._update_clusters_for_edge(user_id, edge)
        
        return edge
    
    async def revoke_linkage_edge(
        self,
        edge_id: str,
        user_id: str,
        reason: str
    ) -> bool:
        """Revoke a linkage edge (soft delete with reason)"""
        result = await db.linkage_edges.update_one(
            {"id": edge_id, "user_id": user_id},
            {"$set": {
                "is_active": False,
                "revoked_at": datetime.now(timezone.utc),
                "revoked_reason": reason
            }}
        )
        
        if result.modified_count > 0:
            # Recompute clusters
            await self.recompute_clusters(user_id)
            return True
        return False
    
    async def get_edges_for_user(self, user_id: str, active_only: bool = True) -> List[Dict]:
        """Get all linkage edges for a user"""
        query = {"user_id": user_id}
        if active_only:
            query["is_active"] = True
        
        edges = await db.linkage_edges.find(query, {"_id": 0}).to_list(10000)
        return edges
    
    # ========================================
    # WALLET CLUSTER MANAGEMENT
    # ========================================
    
    async def _update_clusters_for_edge(self, user_id: str, edge: Dict):
        """Update clusters when a new high-confidence edge is added"""
        from_addr = edge["from_address"]
        to_addr = edge["to_address"]
        
        # Find existing clusters for both addresses
        from_cluster = await db.cluster_members.find_one({
            "user_id": user_id,
            "address": from_addr,
            "is_active": True
        })
        
        to_cluster = await db.cluster_members.find_one({
            "user_id": user_id,
            "address": to_addr,
            "is_active": True
        })
        
        if from_cluster and to_cluster:
            # Both in clusters - merge if different
            if from_cluster["cluster_id"] != to_cluster["cluster_id"]:
                await self._merge_clusters(user_id, from_cluster["cluster_id"], to_cluster["cluster_id"])
        elif from_cluster:
            # Add to_addr to from's cluster
            await self._add_to_cluster(user_id, from_cluster["cluster_id"], to_addr)
        elif to_cluster:
            # Add from_addr to to's cluster
            await self._add_to_cluster(user_id, to_cluster["cluster_id"], from_addr)
        else:
            # Create new cluster with both addresses
            await self._create_cluster(user_id, [from_addr, to_addr])
    
    async def _create_cluster(self, user_id: str, addresses: List[str]) -> str:
        """Create a new wallet cluster"""
        cluster_id = str(uuid.uuid4())
        
        cluster = {
            "id": cluster_id,
            "user_id": user_id,
            "name": f"Wallet Group {cluster_id[:8]}",
            "created_at": datetime.now(timezone.utc),
            "is_active": True,
            "address_count": len(addresses)
        }
        
        await db.wallet_clusters.insert_one(cluster)
        
        # Add members
        for addr in addresses:
            await db.cluster_members.insert_one({
                "cluster_id": cluster_id,
                "user_id": user_id,
                "address": addr.lower(),
                "added_at": datetime.now(timezone.utc),
                "is_active": True
            })
        
        logger.info(f"Created cluster {cluster_id} with {len(addresses)} addresses")
        return cluster_id
    
    async def _add_to_cluster(self, user_id: str, cluster_id: str, address: str):
        """Add an address to an existing cluster"""
        await db.cluster_members.update_one(
            {"user_id": user_id, "address": address.lower()},
            {"$set": {
                "cluster_id": cluster_id,
                "user_id": user_id,
                "address": address.lower(),
                "added_at": datetime.now(timezone.utc),
                "is_active": True
            }},
            upsert=True
        )
        
        # Update cluster count
        count = await db.cluster_members.count_documents({
            "cluster_id": cluster_id,
            "is_active": True
        })
        await db.wallet_clusters.update_one(
            {"id": cluster_id},
            {"$set": {"address_count": count}}
        )
    
    async def _merge_clusters(self, user_id: str, keep_cluster_id: str, merge_cluster_id: str):
        """Merge two clusters into one"""
        # Move all members from merge_cluster to keep_cluster
        await db.cluster_members.update_many(
            {"cluster_id": merge_cluster_id, "user_id": user_id},
            {"$set": {"cluster_id": keep_cluster_id}}
        )
        
        # Deactivate the merged cluster
        await db.wallet_clusters.update_one(
            {"id": merge_cluster_id},
            {"$set": {"is_active": False, "merged_into": keep_cluster_id}}
        )
        
        # Update count
        count = await db.cluster_members.count_documents({
            "cluster_id": keep_cluster_id,
            "is_active": True
        })
        await db.wallet_clusters.update_one(
            {"id": keep_cluster_id},
            {"$set": {"address_count": count}}
        )
        
        logger.info(f"Merged cluster {merge_cluster_id} into {keep_cluster_id}")
    
    async def recompute_clusters(self, user_id: str):
        """
        Recompute all clusters for a user from scratch.
        Uses Union-Find algorithm on active high-confidence edges.
        """
        # Get all active high-confidence edges
        edges = await db.linkage_edges.find({
            "user_id": user_id,
            "is_active": True,
            "confidence": {"$gte": ConfidenceLevel.AUTO_LINK_THRESHOLD}
        }).to_list(10000)
        
        if not edges:
            return
        
        # Union-Find implementation
        parent = {}
        
        def find(x):
            if x not in parent:
                parent[x] = x
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]
        
        def union(x, y):
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py
        
        # Build clusters from edges
        for edge in edges:
            union(edge["from_address"], edge["to_address"])
        
        # Group addresses by cluster root
        clusters = {}
        for addr in parent:
            root = find(addr)
            if root not in clusters:
                clusters[root] = []
            clusters[root].append(addr)
        
        # Deactivate old clusters
        await db.wallet_clusters.update_many(
            {"user_id": user_id},
            {"$set": {"is_active": False}}
        )
        await db.cluster_members.update_many(
            {"user_id": user_id},
            {"$set": {"is_active": False}}
        )
        
        # Create new clusters
        for addresses in clusters.values():
            if len(addresses) > 1:  # Only create cluster if multiple addresses
                await self._create_cluster(user_id, addresses)
        
        logger.info(f"Recomputed clusters for user {user_id}: {len(clusters)} clusters")
    
    async def get_cluster_for_address(self, user_id: str, address: str) -> Optional[Dict]:
        """Get the cluster containing a specific address"""
        member = await db.cluster_members.find_one({
            "user_id": user_id,
            "address": address.lower(),
            "is_active": True
        })
        
        if not member:
            return None
        
        cluster = await db.wallet_clusters.find_one({
            "id": member["cluster_id"],
            "is_active": True
        }, {"_id": 0})
        
        if cluster:
            # Add member addresses
            members = await db.cluster_members.find({
                "cluster_id": cluster["id"],
                "is_active": True
            }, {"_id": 0}).to_list(1000)
            cluster["addresses"] = [m["address"] for m in members]
        
        return cluster
    
    async def get_all_owned_addresses(self, user_id: str) -> Set[str]:
        """Get all addresses owned by a user (from clusters and saved wallets)"""
        owned = set()
        
        # From clusters
        members = await db.cluster_members.find({
            "user_id": user_id,
            "is_active": True
        }).to_list(10000)
        owned.update(m["address"].lower() for m in members)
        
        # From saved wallets
        wallets = await db.saved_wallets.find({
            "user_id": user_id
        }).to_list(1000)
        owned.update(w.get("address", "").lower() for w in wallets if w.get("address"))
        
        return owned
    
    # ========================================
    # CHAIN BREAK DETECTION
    # ========================================
    
    async def detect_chain_breaks(
        self,
        user_id: str,
        transactions: List[Dict],
        owned_addresses: Optional[Set[str]] = None
    ) -> List[Dict]:
        """
        Detect chain breaks in a list of transactions.
        
        A chain break occurs when:
        - Asset leaves an owned wallet
        - Destination is not in owned clusters
        - No matching inbound found in owned wallets
        
        Returns:
            List of chain break events with prompts
        """
        if owned_addresses is None:
            owned_addresses = await self.get_all_owned_addresses(user_id)
        
        chain_breaks = []
        
        for tx in transactions:
            tx_type = tx.get("tx_type", "").lower()
            from_addr = tx.get("from_address", "").lower()
            to_addr = tx.get("to_address", "").lower()
            
            # Check for outbound transfers from owned wallets
            if tx_type in ["send", "transfer", "withdrawal"] and from_addr in owned_addresses:
                if to_addr and to_addr not in owned_addresses:
                    # Potential chain break - check for matching inbound
                    match = await self._find_matching_inbound(
                        user_id, tx, owned_addresses
                    )
                    
                    if not match:
                        # Chain break detected
                        break_event = {
                            "tx_id": tx.get("tx_id") or tx.get("hash"),
                            "user_id": user_id,
                            "source_address": from_addr,
                            "destination_address": to_addr,
                            "asset": tx.get("asset"),
                            "amount": tx.get("amount"),
                            "timestamp": tx.get("timestamp"),
                            "chain": tx.get("chain", "ethereum"),
                            "chain_status": ChainStatus.UNLINKED.value,
                            "detected_reason": "outbound_unmatched",
                            "confidence": 0.0,  # No match found
                            "detected_at": datetime.now(timezone.utc)
                        }
                        chain_breaks.append(break_event)
        
        return chain_breaks
    
    async def _find_matching_inbound(
        self,
        user_id: str,
        outbound_tx: Dict,
        owned_addresses: Set[str]
    ) -> Optional[Dict]:
        """
        Find a matching inbound transaction in owned wallets.
        
        Checks for:
        - Direct transfers (same asset, similar amount, within time window)
        - Bridge transfers (equivalent tokens, adjusted amount, longer window)
        - CEX flows (deposit/withdrawal patterns)
        """
        asset = outbound_tx.get("asset", "").upper()
        amount = float(outbound_tx.get("amount", 0))
        tx_time = outbound_tx.get("timestamp")
        
        if not tx_time:
            return None
        
        if isinstance(tx_time, str):
            tx_time = datetime.fromisoformat(tx_time.replace("Z", "+00:00"))
        
        # Define time windows
        time_window = timedelta(hours=self.config["time_window_hours"])
        bridge_window = timedelta(hours=self.config["bridge_time_window_hours"])
        
        # Amount tolerance
        tolerance = self.config["amount_tolerance_percent"] / 100
        min_amount = amount * (1 - tolerance)
        max_amount = amount * (1 + tolerance)
        
        # Get equivalent tokens for bridge matching
        equivalent_tokens = self.token_equivalencies.get(asset, [asset])
        
        # Search for matching inbound in owned addresses
        for owned_addr in owned_addresses:
            # Query for inbound transactions to this owned address
            query = {
                "user_id": user_id,
                "to_address": owned_addr,
                "tx_type": {"$in": ["receive", "deposit", "transfer"]},
                "asset": {"$in": equivalent_tokens},
                "amount": {"$gte": min_amount, "$lte": max_amount},
                "timestamp": {
                    "$gte": tx_time - bridge_window,
                    "$lte": tx_time + bridge_window
                }
            }
            
            match = await db.exchange_transactions.find_one(query)
            if match:
                return match
        
        return None
    
    # ========================================
    # REVIEW QUEUE MANAGEMENT
    # ========================================
    
    async def add_to_review_queue(
        self,
        user_id: str,
        tx_id: str,
        source_address: str,
        destination_address: str,
        asset: str,
        amount: float,
        detected_reason: str,
        confidence: float,
        chain: str = "ethereum",
        metadata: Optional[Dict] = None
    ) -> Dict:
        """Add a chain break to the review queue for user decision"""
        review_id = str(uuid.uuid4())
        
        review_item = {
            "id": review_id,
            "user_id": user_id,
            "tx_id": tx_id,
            "source_address": source_address.lower(),
            "destination_address": destination_address.lower(),
            "asset": asset,
            "amount": amount,
            "chain": chain,
            "detected_reason": detected_reason,
            "confidence": confidence,
            "review_status": ReviewStatus.PENDING.value,
            "user_decision": None,
            "override_reason": None,
            "prompt_text": self._generate_prompt_text(destination_address, asset, amount),
            "created_at": datetime.now(timezone.utc),
            "resolved_at": None,
            "metadata": metadata or {}
        }
        
        # Check for duplicate
        existing = await db.review_queue.find_one({
            "user_id": user_id,
            "tx_id": tx_id,
            "review_status": ReviewStatus.PENDING.value
        })
        
        if existing:
            return existing
        
        await db.review_queue.insert_one(review_item)
        logger.info(f"Added to review queue: {tx_id} ({asset} to {destination_address[:8]}...)")
        
        return review_item
    
    async def resolve_review(
        self,
        review_id: str,
        user_id: str,
        decision: str,  # "yes", "no", "ignore"
        override_reason: Optional[str] = None
    ) -> Dict:
        """
        Resolve a review queue item based on user decision.
        
        Args:
            review_id: ID of review item
            user_id: User making the decision
            decision: "yes" (own wallet), "no" (external), "ignore"
            override_reason: Optional reason for the decision
        
        Returns:
            Updated review item and any created tax events
        """
        review = await db.review_queue.find_one({
            "id": review_id,
            "user_id": user_id
        })
        
        if not review:
            raise ValueError(f"Review item {review_id} not found")
        
        result = {"review": None, "tax_event": None, "linkage_edge": None}
        
        decision_lower = decision.lower()
        
        if decision_lower == "yes":
            # User confirms ownership - create linkage edge
            edge = await self.create_linkage_edge(
                user_id=user_id,
                from_address=review["source_address"],
                to_address=review["destination_address"],
                link_type=LinkType.USER_CONFIRMED,
                confidence=ConfidenceLevel.USER_CONFIRMED,
                reason="user_confirmed_ownership",
                evidence_id=review["tx_id"],
                chain=review.get("chain", "ethereum")
            )
            result["linkage_edge"] = edge
            
            # Update transaction chain status
            await db.exchange_transactions.update_one(
                {"tx_id": review["tx_id"], "user_id": user_id},
                {"$set": {"chain_status": ChainStatus.LINKED.value}}
            )
            
            review_status = ReviewStatus.RESOLVED_YES.value
            
        elif decision_lower == "no":
            # External transfer - create tax event
            tax_event = await self._create_tax_event_from_chain_break(user_id, review)
            result["tax_event"] = tax_event
            
            # Update transaction chain status
            await db.exchange_transactions.update_one(
                {"tx_id": review["tx_id"], "user_id": user_id},
                {"$set": {"chain_status": ChainStatus.EXTERNAL.value}}
            )
            
            review_status = ReviewStatus.RESOLVED_NO.value
            
        else:  # ignore
            review_status = ReviewStatus.RESOLVED_IGNORE.value
        
        # Update review item
        await db.review_queue.update_one(
            {"id": review_id},
            {"$set": {
                "review_status": review_status,
                "user_decision": decision_lower,
                "override_reason": override_reason,
                "resolved_at": datetime.now(timezone.utc)
            }}
        )
        
        review["review_status"] = review_status
        review["user_decision"] = decision_lower
        result["review"] = review
        
        logger.info(f"Resolved review {review_id}: {decision_lower}")
        
        return result
    
    async def get_pending_reviews(self, user_id: str) -> List[Dict]:
        """Get all pending review items for a user"""
        # Use fresh connection to avoid stale data issues
        from motor.motor_asyncio import AsyncIOMotorClient
        client = AsyncIOMotorClient(MONGO_URL)
        fresh_db = client[DB_NAME]
        
        reviews = await fresh_db.review_queue.find({
            "user_id": user_id,
            "review_status": ReviewStatus.PENDING.value
        }, {"_id": 0}).sort("created_at", -1).to_list(1000)
        
        client.close()
        return reviews
    
    # ========================================
    # TAX EVENT GENERATION
    # ========================================
    
    async def _create_tax_event_from_chain_break(
        self,
        user_id: str,
        review: Dict
    ) -> Dict:
        """
        Create a tax event when a chain break is resolved as external transfer.
        
        Per IRS guidelines, transferring crypto out of your control is a disposal event.
        """
        from price_service import price_service
        
        tx_id = review["tx_id"]
        asset = review["asset"]
        amount = review["amount"]
        timestamp = review.get("timestamp") or review.get("created_at")
        
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        
        # Get FMV at time of transfer
        date_str = timestamp.strftime("%d-%m-%Y") if timestamp else None
        fmv_price = price_service.get_historical_price(asset, date_str) if date_str else None
        proceeds = (amount * fmv_price) if fmv_price else 0
        
        # Look up cost basis from FIFO lots
        cost_basis = await self._get_cost_basis_fifo(user_id, asset, amount, timestamp)
        
        tax_event = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "tx_id": tx_id,
            "event_type": "disposal",
            "source": "chain_break_resolution",
            "asset": asset,
            "quantity": amount,
            "date_acquired": cost_basis.get("date_acquired"),
            "date_disposed": timestamp.isoformat() if timestamp else None,
            "proceeds": proceeds,
            "cost_basis": cost_basis.get("cost_basis", 0),
            "gain_loss": proceeds - cost_basis.get("cost_basis", 0),
            "holding_period": self._calculate_holding_period(
                cost_basis.get("date_acquired"),
                timestamp
            ),
            "form_8949_data": {
                "description": f"{amount:.8f} {asset}",
                "date_acquired": cost_basis.get("date_acquired"),
                "date_sold": timestamp.isoformat() if timestamp else None,
                "proceeds": proceeds,
                "cost_basis": cost_basis.get("cost_basis", 0),
                "adjustment_code": "",
                "adjustment_amount": 0,
                "gain_or_loss": proceeds - cost_basis.get("cost_basis", 0)
            },
            "created_at": datetime.now(timezone.utc),
            "is_active": True
        }
        
        await db.tax_events.insert_one(tax_event)
        logger.info(f"Created tax event for {amount} {asset}: gain/loss = ${tax_event['gain_loss']:.2f}")
        
        return tax_event
    
    async def _get_cost_basis_fifo(
        self,
        user_id: str,
        asset: str,
        amount: float,
        disposal_date: datetime
    ) -> Dict:
        """Get cost basis using FIFO method"""
        # Get all acquisition lots for this asset, sorted by date
        lots = await db.exchange_transactions.find({
            "user_id": user_id,
            "asset": asset,
            "tx_type": {"$in": ["buy", "receive", "reward", "staking"]},
            "timestamp": {"$lt": disposal_date}
        }).sort("timestamp", 1).to_list(10000)
        
        total_cost = 0
        remaining = amount
        earliest_date = None
        
        for lot in lots:
            lot_amount = lot.get("amount", 0)
            lot_cost = lot.get("total_usd", 0) or (lot_amount * (lot.get("price_usd") or 0))
            
            if remaining <= 0:
                break
            
            if earliest_date is None:
                earliest_date = lot.get("timestamp")
            
            if lot_amount <= remaining:
                total_cost += lot_cost
                remaining -= lot_amount
            else:
                # Partial lot
                portion = remaining / lot_amount
                total_cost += lot_cost * portion
                remaining = 0
        
        return {
            "cost_basis": total_cost,
            "date_acquired": earliest_date.isoformat() if earliest_date else None
        }
    
    def _calculate_holding_period(
        self,
        date_acquired: Optional[str],
        date_disposed: Optional[datetime]
    ) -> str:
        """Calculate if holding period is short-term or long-term"""
        if not date_acquired or not date_disposed:
            return "unknown"
        
        try:
            if isinstance(date_acquired, str):
                acquired = datetime.fromisoformat(date_acquired.replace("Z", "+00:00"))
            else:
                acquired = date_acquired
            
            if isinstance(date_disposed, str):
                disposed = datetime.fromisoformat(date_disposed.replace("Z", "+00:00"))
            else:
                disposed = date_disposed
            
            days_held = (disposed - acquired).days
            return "long-term" if days_held > 365 else "short-term"
        except:
            return "unknown"
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    def _get_human_readable_reason(self, reason: str, link_type) -> str:
        """Convert machine reason to human-readable explanation"""
        reasons = {
            "user_confirmed_ownership": "You confirmed this is your wallet",
            "self_transfer_detected": "Automatic detection: direct transfer between your wallets",
            "bridge_transfer_matched": "Automatic detection: cross-chain bridge transfer matched",
            "cex_withdrawal_matched": "Automatic detection: exchange withdrawal matched to deposit",
            "contract_mediated_detected": "Automatic detection: smart contract transfer matched",
            "wallet_sweep_detected": "Automatic detection: wallet consolidation detected",
            "heuristic_match": "Pattern-based detection (lower confidence)"
        }
        return reasons.get(reason, reason)
    
    def _generate_prompt_text(self, address: str, asset: str, amount: float) -> str:
        """Generate the user prompt text for chain breaks"""
        return f"You sent {amount:.8f} {asset} to {address}. Is this another wallet you own?"
    
    # ========================================
    # MATCHING LOGIC
    # ========================================
    
    async def match_direct_transfer(
        self,
        user_id: str,
        outbound_tx: Dict,
        owned_addresses: Set[str]
    ) -> Tuple[Optional[Dict], float]:
        """
        Match direct wallet-to-wallet transfers.
        
        Returns:
            Tuple of (matched_tx, confidence)
        """
        asset = outbound_tx.get("asset", "").upper()
        amount = float(outbound_tx.get("amount", 0))
        to_addr = outbound_tx.get("to_address", "").lower()
        tx_time = outbound_tx.get("timestamp")
        
        if to_addr in owned_addresses:
            return (outbound_tx, ConfidenceLevel.DETERMINISTIC)
        
        # Check for matching inbound to any owned address
        time_window = timedelta(hours=self.config["time_window_hours"])
        tolerance = self.config["amount_tolerance_percent"] / 100
        
        if isinstance(tx_time, str):
            tx_time = datetime.fromisoformat(tx_time.replace("Z", "+00:00"))
        
        for owned_addr in owned_addresses:
            match = await db.exchange_transactions.find_one({
                "user_id": user_id,
                "to_address": owned_addr,
                "asset": asset,
                "amount": {"$gte": amount * (1 - tolerance), "$lte": amount * (1 + tolerance)},
                "timestamp": {"$gte": tx_time - time_window, "$lte": tx_time + time_window}
            })
            
            if match:
                return (match, ConfidenceLevel.STRONG_MATCH)
        
        return (None, 0.0)
    
    async def match_bridge_transfer(
        self,
        user_id: str,
        outbound_tx: Dict,
        owned_addresses: Set[str]
    ) -> Tuple[Optional[Dict], float]:
        """
        Match cross-chain bridge transfers.
        
        Bridge transfers may have:
        - Different chain
        - Equivalent token (ETH → WETH)
        - Slightly different amount (fees)
        - Longer time window
        """
        asset = outbound_tx.get("asset", "").upper()
        amount = float(outbound_tx.get("amount", 0))
        tx_time = outbound_tx.get("timestamp")
        source_chain = outbound_tx.get("chain", "ethereum")
        
        equivalent_tokens = self.token_equivalencies.get(asset, [asset])
        time_window = timedelta(hours=self.config["bridge_time_window_hours"])
        tolerance = 0.05  # 5% tolerance for bridge fees
        
        if isinstance(tx_time, str):
            tx_time = datetime.fromisoformat(tx_time.replace("Z", "+00:00"))
        
        for owned_addr in owned_addresses:
            match = await db.exchange_transactions.find_one({
                "user_id": user_id,
                "to_address": owned_addr,
                "asset": {"$in": equivalent_tokens},
                "chain": {"$ne": source_chain},  # Different chain
                "amount": {"$gte": amount * (1 - tolerance), "$lte": amount * (1 + tolerance)},
                "timestamp": {"$gte": tx_time, "$lte": tx_time + time_window}
            })
            
            if match:
                return (match, ConfidenceLevel.DETERMINISTIC)
        
        return (None, 0.0)


# Singleton instance
linkage_engine = LinkageEngineService()
