"""
Constrained Proceeds Acquisition Remediation Service

Implements a strict, auditable flow for creating proceeds acquisitions
from crypto-to-crypto/stablecoin sales. Only creates inventory when 
directly linked to a verified source disposal.

Requirements:
- Only creates proceeds acquisition when linked to known source disposal
- Requires: source_disposal_tx_id, proceeds_asset, exact_amount, timestamp, price_source
- Tags all records as `derived_proceeds_acquisition`
- All records are reversible via rollback
- Excludes: unresolved ownership, missing history, inferred transfers, bridge/DEX ambiguity
- Preview mode shows candidates before applying
- Dry-run summary with fixable/non-fixable counts and reasons
"""

import logging
import uuid
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


class SkipReason(Enum):
    """Reasons why a disposal cannot have proceeds acquisition created"""
    UNRESOLVED_WALLET_OWNERSHIP = "unresolved_wallet_ownership"
    MISSING_ACQUISITION_HISTORY = "missing_acquisition_history"
    INFERRED_INTERNAL_TRANSFER = "inferred_internal_transfer"
    BRIDGE_AMBIGUITY = "bridge_ambiguity"
    DEX_AMBIGUITY = "dex_ambiguity"
    MISSING_PROCEEDS_VALUE = "missing_proceeds_value"
    MISSING_TIMESTAMP = "missing_timestamp"
    STABLECOIN_SOURCE = "stablecoin_source"
    ALREADY_HAS_PROCEEDS = "already_has_proceeds"
    PENDING_REVIEW_QUEUE = "pending_review_queue"
    ZERO_PROCEEDS = "zero_proceeds"
    NEGATIVE_PROCEEDS = "negative_proceeds"
    EXCHANGE_INTERNAL = "exchange_internal"


@dataclass
class CandidateFix:
    """A candidate proceeds acquisition fix"""
    source_disposal_tx_id: str
    source_asset: str
    source_quantity: float
    proceeds_asset: str
    proceeds_amount: float
    disposal_timestamp: str
    exchange: str
    price_source: str
    reason: str  # Why this candidate was identified
    confidence: float  # 0.0 - 1.0
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SkippedDisposal:
    """A disposal that cannot be fixed"""
    tx_id: str
    asset: str
    quantity: float
    skip_reason: SkipReason
    details: str
    
    def to_dict(self) -> Dict:
        return {
            "tx_id": self.tx_id,
            "asset": self.asset,
            "quantity": self.quantity,
            "skip_reason": self.skip_reason.value,
            "details": self.details
        }


@dataclass
class DryRunSummary:
    """Summary of what a fix run would do"""
    fixable_count: int = 0
    fixable_total_value: float = 0.0
    non_fixable_count: int = 0
    non_fixable_by_reason: Dict[str, int] = field(default_factory=dict)
    candidates: List[CandidateFix] = field(default_factory=list)
    skipped: List[SkippedDisposal] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "fixable_count": self.fixable_count,
            "fixable_total_value": round(self.fixable_total_value, 2),
            "non_fixable_count": self.non_fixable_count,
            "non_fixable_by_reason": self.non_fixable_by_reason,
            "candidates": [c.to_dict() for c in self.candidates],
            "skipped": [s.to_dict() for s in self.skipped]
        }


class ConstrainedProceedsService:
    """
    Service for creating constrained, auditable proceeds acquisitions.
    
    NEVER creates inventory without a linked, verified disposal.
    """
    
    # Assets that are considered "stablecoins" (proceeds assets)
    STABLECOIN_ASSETS = {"USDC", "USDT", "USD", "DAI", "BUSD", "TUSD", "USDP", "GUSD", "FRAX"}
    
    # Keywords indicating bridge transactions
    BRIDGE_KEYWORDS = ["bridge", "wormhole", "multichain", "synapse", "hop", "across", 
                       "stargate", "layerzero", "portal", "celer"]
    
    # Keywords indicating DEX transactions
    DEX_KEYWORDS = ["uniswap", "sushiswap", "pancake", "curve", "1inch", "0x", 
                    "paraswap", "dex", "swap", "router", "aggregator"]
    
    # Transaction types that indicate acquisition (for missing history check)
    ACQUISITION_TYPES = {"buy", "receive", "trade", "reward", "staking", "airdrop", 
                         "mining", "interest", "convert", "proceeds_acquisition"}
    
    def __init__(self, db):
        self.db = db
    
    async def preview_candidates(self, user_id: str) -> DryRunSummary:
        """
        Preview all candidate fixes before applying.
        
        Returns a DryRunSummary with:
        - All fixable disposals with their proposed proceeds acquisitions
        - All non-fixable disposals with reasons they were skipped
        """
        summary = DryRunSummary()
        
        # Get all relevant disposals
        disposals = await self._get_all_disposals(user_id)
        
        # Get existing proceeds acquisitions to avoid duplicates
        existing_proceeds = await self._get_existing_proceeds_tx_ids(user_id)
        
        # Get pending review items (unresolved ownership)
        pending_reviews = await self._get_pending_review_tx_ids(user_id)
        
        # Get acquisition history for each asset
        acquisition_history = await self._get_acquisition_history(user_id)
        
        for disposal in disposals:
            tx_id = disposal.get("tx_id", "unknown")
            asset = disposal.get("asset", "UNKNOWN")
            quantity = float(disposal.get("quantity", 0) or disposal.get("amount", 0) or 0)
            total_usd = disposal.get("total_usd")
            timestamp = disposal.get("timestamp")
            exchange = disposal.get("exchange", "unknown")
            notes = (disposal.get("notes") or "").lower()
            chain_status = disposal.get("chain_status", "none")
            
            # === EXCLUSION CHECKS ===
            
            # 1. Skip stablecoin sources (USDC sells don't generate USDC proceeds)
            if asset.upper() in self.STABLECOIN_ASSETS:
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.STABLECOIN_SOURCE,
                    details=f"Stablecoin {asset} disposal does not generate crypto proceeds"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.STABLECOIN_SOURCE.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.STABLECOIN_SOURCE.value, 0) + 1
                continue
            
            # 2. Skip if already has proceeds record
            proceeds_tx_id = f"derived_proceeds_{tx_id}"
            if proceeds_tx_id in existing_proceeds or f"proceeds_{tx_id}" in existing_proceeds:
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.ALREADY_HAS_PROCEEDS,
                    details="Proceeds acquisition already exists for this disposal"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.ALREADY_HAS_PROCEEDS.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.ALREADY_HAS_PROCEEDS.value, 0) + 1
                continue
            
            # 3. Skip if missing proceeds value
            if total_usd is None:
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.MISSING_PROCEEDS_VALUE,
                    details="No USD value recorded for this disposal"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.MISSING_PROCEEDS_VALUE.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.MISSING_PROCEEDS_VALUE.value, 0) + 1
                continue
            
            proceeds_value = float(total_usd)
            
            # 4. Skip if zero or negative proceeds
            if proceeds_value <= 0:
                reason = SkipReason.ZERO_PROCEEDS if proceeds_value == 0 else SkipReason.NEGATIVE_PROCEEDS
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=reason,
                    details=f"Proceeds value is {proceeds_value}"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[reason.value] = \
                    summary.non_fixable_by_reason.get(reason.value, 0) + 1
                continue
            
            # 5. Skip if missing timestamp
            if not timestamp:
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.MISSING_TIMESTAMP,
                    details="No timestamp recorded for this disposal"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.MISSING_TIMESTAMP.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.MISSING_TIMESTAMP.value, 0) + 1
                continue
            
            # 6. Skip if unresolved wallet ownership (in review queue)
            if tx_id in pending_reviews:
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.UNRESOLVED_WALLET_OWNERSHIP,
                    details="This transaction has pending wallet ownership review"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.UNRESOLVED_WALLET_OWNERSHIP.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.UNRESOLVED_WALLET_OWNERSHIP.value, 0) + 1
                continue
            
            # 7. Skip if missing acquisition history for this asset
            if asset not in acquisition_history or acquisition_history[asset]["count"] == 0:
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.MISSING_ACQUISITION_HISTORY,
                    details=f"No acquisition history found for {asset}"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.MISSING_ACQUISITION_HISTORY.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.MISSING_ACQUISITION_HISTORY.value, 0) + 1
                continue
            
            # 8. Skip inferred internal transfers (chain_status indicates linked transfer)
            if chain_status == "internal_transfer" or chain_status == "linked":
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.INFERRED_INTERNAL_TRANSFER,
                    details=f"Chain status '{chain_status}' indicates internal transfer"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.INFERRED_INTERNAL_TRANSFER.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.INFERRED_INTERNAL_TRANSFER.value, 0) + 1
                continue
            
            # 9. Skip bridge ambiguity without explicit proceeds leg
            if self._has_bridge_ambiguity(disposal, notes):
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.BRIDGE_AMBIGUITY,
                    details="Bridge/cross-chain transaction without explicit proceeds leg"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.BRIDGE_AMBIGUITY.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.BRIDGE_AMBIGUITY.value, 0) + 1
                continue
            
            # 10. Skip DEX ambiguity without explicit proceeds leg
            if self._has_dex_ambiguity(disposal, notes):
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.DEX_AMBIGUITY,
                    details="DEX/swap transaction without explicit proceeds leg"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.DEX_AMBIGUITY.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.DEX_AMBIGUITY.value, 0) + 1
                continue
            
            # 11. Skip exchange internal transfers (e.g., moving to earn/staking)
            if self._is_exchange_internal(disposal):
                summary.skipped.append(SkippedDisposal(
                    tx_id=tx_id,
                    asset=asset,
                    quantity=quantity,
                    skip_reason=SkipReason.EXCHANGE_INTERNAL,
                    details="Exchange-internal transfer (earn, staking, etc.)"
                ))
                summary.non_fixable_count += 1
                summary.non_fixable_by_reason[SkipReason.EXCHANGE_INTERNAL.value] = \
                    summary.non_fixable_by_reason.get(SkipReason.EXCHANGE_INTERNAL.value, 0) + 1
                continue
            
            # === PASSED ALL EXCLUSION CHECKS - CREATE CANDIDATE ===
            
            # Determine proceeds asset (default USDC for most exchanges)
            proceeds_asset = self._determine_proceeds_asset(disposal)
            
            candidate = CandidateFix(
                source_disposal_tx_id=tx_id,
                source_asset=asset,
                source_quantity=quantity,
                proceeds_asset=proceeds_asset,
                proceeds_amount=proceeds_value,
                disposal_timestamp=str(timestamp),
                exchange=exchange,
                price_source=f"proceeds_from_{asset}_sell",
                reason=f"Verified {asset} sell on {exchange} with {proceeds_value:.2f} {proceeds_asset} proceeds",
                confidence=self._calculate_confidence(disposal, acquisition_history.get(asset, {}))
            )
            
            summary.candidates.append(candidate)
            summary.fixable_count += 1
            summary.fixable_total_value += proceeds_value
        
        return summary
    
    async def apply_fixes(
        self, 
        user_id: str, 
        candidate_tx_ids: Optional[List[str]] = None,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Apply proceeds acquisition fixes.
        
        Args:
            user_id: User ID
            candidate_tx_ids: Specific disposal tx_ids to fix (None = all candidates)
            dry_run: If True, show what would be created without creating
        
        Returns:
            Results with created records and audit trail
        """
        # First get preview to get candidates
        summary = await self.preview_candidates(user_id)
        
        # Filter to requested candidates if specified
        if candidate_tx_ids:
            candidates = [c for c in summary.candidates if c.source_disposal_tx_id in candidate_tx_ids]
        else:
            candidates = summary.candidates
        
        results = {
            "user_id": user_id,
            "dry_run": dry_run,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "candidates_count": len(candidates),
            "created_count": 0,
            "total_value": sum(c.proceeds_amount for c in candidates),
            "created_records": [],
            "audit_entries": [],
            "rollback_batch_id": str(uuid.uuid4()) if not dry_run else None
        }
        
        if dry_run:
            # Just return what would be created
            results["preview"] = [c.to_dict() for c in candidates]
            return results
        
        # Actually create the records
        batch_id = results["rollback_batch_id"]
        created_records = []
        audit_entries = []
        
        for candidate in candidates:
            # Create the derived proceeds acquisition record
            record = {
                "user_id": user_id,
                "tx_id": f"derived_proceeds_{candidate.source_disposal_tx_id}",
                "exchange": candidate.exchange,
                "tx_type": "derived_proceeds_acquisition",  # Tagged as derived
                "asset": candidate.proceeds_asset,
                "quantity": candidate.proceeds_amount,
                "amount": candidate.proceeds_amount,
                "price_usd": 1.0,  # Stablecoin
                "total_usd": candidate.proceeds_amount,
                "timestamp": candidate.disposal_timestamp,
                "chain_status": "verified_proceeds",
                
                # Required linkage fields
                "source_disposal": {
                    "tx_id": candidate.source_disposal_tx_id,
                    "asset": candidate.source_asset,
                    "quantity": candidate.source_quantity,
                    "proceeds": candidate.proceeds_amount
                },
                "price_source": candidate.price_source,
                
                # Reversibility metadata
                "derived_record": True,
                "rollback_batch_id": batch_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": "constrained_proceeds_service",
                
                "notes": f"Derived proceeds: {candidate.proceeds_amount:.2f} {candidate.proceeds_asset} from selling {candidate.source_quantity} {candidate.source_asset}"
            }
            
            created_records.append(record)
            
            # Create audit entry
            audit_entry = {
                "entry_id": str(uuid.uuid4()),
                "user_id": user_id,
                "action": "create_derived_proceeds_acquisition",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "rollback_batch_id": batch_id,
                "details": {
                    "derived_tx_id": record["tx_id"],
                    "source_disposal_tx_id": candidate.source_disposal_tx_id,
                    "source_asset": candidate.source_asset,
                    "source_quantity": candidate.source_quantity,
                    "proceeds_asset": candidate.proceeds_asset,
                    "proceeds_amount": candidate.proceeds_amount,
                    "confidence": candidate.confidence,
                    "linkage_verified": True
                }
            }
            audit_entries.append(audit_entry)
        
        # Insert records
        if created_records:
            await self.db.exchange_transactions.insert_many(created_records)
            results["created_count"] = len(created_records)
            results["created_records"] = [
                {
                    "tx_id": r["tx_id"],
                    "asset": r["asset"],
                    "amount": r["quantity"],
                    "source_disposal": r["source_disposal"]["tx_id"]
                } for r in created_records
            ]
        
        # Insert audit entries
        if audit_entries:
            await self.db.tax_audit_trail.insert_many(audit_entries)
            results["audit_entries"] = [e["entry_id"] for e in audit_entries]
        
        return results
    
    async def rollback_batch(self, user_id: str, batch_id: str) -> Dict[str, Any]:
        """
        Rollback a batch of created proceeds acquisitions.
        
        Args:
            user_id: User ID
            batch_id: The rollback_batch_id from apply_fixes
        
        Returns:
            Rollback results
        """
        # Find all records with this batch ID
        records = await self.db.exchange_transactions.find({
            "user_id": user_id,
            "rollback_batch_id": batch_id,
            "derived_record": True
        }).to_list(100000)
        
        if not records:
            return {
                "success": False,
                "message": f"No records found for batch {batch_id}",
                "deleted_count": 0
            }
        
        # Delete the records
        result = await self.db.exchange_transactions.delete_many({
            "user_id": user_id,
            "rollback_batch_id": batch_id,
            "derived_record": True
        })
        
        # Add rollback audit entry
        rollback_audit = {
            "entry_id": str(uuid.uuid4()),
            "user_id": user_id,
            "action": "rollback_derived_proceeds_batch",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": {
                "rollback_batch_id": batch_id,
                "records_deleted": result.deleted_count,
                "deleted_tx_ids": [r["tx_id"] for r in records]
            }
        }
        await self.db.tax_audit_trail.insert_one(rollback_audit)
        
        return {
            "success": True,
            "batch_id": batch_id,
            "deleted_count": result.deleted_count,
            "deleted_tx_ids": [r["tx_id"] for r in records],
            "audit_entry_id": rollback_audit["entry_id"]
        }
    
    async def list_rollback_batches(self, user_id: str) -> List[Dict]:
        """List all rollback batches for a user"""
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "derived_record": True,
                "rollback_batch_id": {"$exists": True}
            }},
            {"$group": {
                "_id": "$rollback_batch_id",
                "count": {"$sum": 1},
                "total_value": {"$sum": "$quantity"},
                "created_at": {"$first": "$created_at"},
                "assets": {"$addToSet": "$asset"}
            }},
            {"$sort": {"created_at": -1}}
        ]
        
        batches = await self.db.exchange_transactions.aggregate(pipeline).to_list(100)
        
        return [
            {
                "batch_id": b["_id"],
                "record_count": b["count"],
                "total_value": round(b["total_value"], 2),
                "created_at": b["created_at"],
                "assets": b["assets"]
            }
            for b in batches
        ]
    
    # === HELPER METHODS ===
    
    async def _get_all_disposals(self, user_id: str) -> List[Dict]:
        """Get all sell transactions for the user"""
        return await self.db.exchange_transactions.find({
            "user_id": user_id,
            "tx_type": "sell"
        }).to_list(100000)
    
    async def _get_existing_proceeds_tx_ids(self, user_id: str) -> set:
        """Get tx_ids of existing proceeds acquisitions"""
        records = await self.db.exchange_transactions.find(
            {
                "user_id": user_id,
                "tx_type": {"$in": ["proceeds_acquisition", "derived_proceeds_acquisition"]}
            },
            {"tx_id": 1}
        ).to_list(100000)
        return {r["tx_id"] for r in records}
    
    async def _get_pending_review_tx_ids(self, user_id: str) -> set:
        """Get tx_ids that are pending wallet ownership review"""
        reviews = await self.db.review_queue.find(
            {"user_id": user_id, "review_status": "pending"},
            {"tx_id": 1}
        ).to_list(100000)
        return {r["tx_id"] for r in reviews}
    
    async def _get_acquisition_history(self, user_id: str) -> Dict[str, Dict]:
        """Get acquisition history by asset"""
        pipeline = [
            {"$match": {
                "user_id": user_id,
                "tx_type": {"$in": list(self.ACQUISITION_TYPES)}
            }},
            {"$group": {
                "_id": "$asset",
                "count": {"$sum": 1},
                "total_quantity": {"$sum": {"$ifNull": ["$quantity", "$amount"]}},
                "earliest": {"$min": "$timestamp"}
            }}
        ]
        
        results = await self.db.exchange_transactions.aggregate(pipeline).to_list(1000)
        
        return {
            r["_id"]: {
                "count": r["count"],
                "total_quantity": r["total_quantity"],
                "earliest": r["earliest"]
            }
            for r in results
        }
    
    def _has_bridge_ambiguity(self, disposal: Dict, notes: str) -> bool:
        """Check if disposal has bridge ambiguity"""
        # Check notes for bridge keywords
        if any(kw in notes for kw in self.BRIDGE_KEYWORDS):
            return True
        
        # Check if tx_type indicates bridge
        tx_type = disposal.get("tx_type", "")
        if "bridge" in tx_type.lower():
            return True
        
        # Check destination for bridge keywords
        dest = (disposal.get("destination_address") or "").lower()
        if any(kw in dest for kw in self.BRIDGE_KEYWORDS):
            return True
        
        return False
    
    def _has_dex_ambiguity(self, disposal: Dict, notes: str) -> bool:
        """Check if disposal has DEX ambiguity without explicit proceeds"""
        # Check notes for DEX keywords
        if any(kw in notes for kw in self.DEX_KEYWORDS):
            # Only ambiguous if no explicit received_asset
            if not disposal.get("received_asset") and not disposal.get("output_asset"):
                return True
        
        # Check if tx_type indicates swap without proceeds
        tx_type = disposal.get("tx_type", "")
        if "swap" in tx_type.lower() or "dex" in tx_type.lower():
            if not disposal.get("received_asset") and not disposal.get("output_asset"):
                return True
        
        return False
    
    def _is_exchange_internal(self, disposal: Dict) -> bool:
        """Check if this is an exchange-internal transfer (earn, staking)"""
        tx_type = disposal.get("tx_type", "").lower()
        notes = (disposal.get("notes") or "").lower()
        
        internal_keywords = ["earn", "staking", "savings", "vault", "lending", 
                           "margin", "futures", "convert_internal"]
        
        return any(kw in tx_type or kw in notes for kw in internal_keywords)
    
    def _determine_proceeds_asset(self, disposal: Dict) -> str:
        """Determine the proceeds asset for a disposal"""
        # Check if explicit proceeds asset is set
        if disposal.get("proceeds_asset"):
            return disposal["proceeds_asset"]
        
        if disposal.get("received_asset"):
            return disposal["received_asset"]
        
        # Default to USDC for most exchanges
        return "USDC"
    
    def _calculate_confidence(self, disposal: Dict, acquisition_history: Dict) -> float:
        """Calculate confidence score for a candidate fix"""
        confidence = 0.5  # Base confidence
        
        # Higher confidence if we have acquisition history
        if acquisition_history.get("count", 0) > 0:
            confidence += 0.2
        
        # Higher confidence if disposal has clear timestamp
        if disposal.get("timestamp"):
            confidence += 0.1
        
        # Higher confidence if from known exchange
        exchange = (disposal.get("exchange") or "").lower()
        known_exchanges = ["coinbase", "binance", "kraken", "gemini", "kucoin", "okx"]
        if any(ex in exchange for ex in known_exchanges):
            confidence += 0.15
        
        # Higher confidence if USD value is present
        if disposal.get("total_usd") and float(disposal.get("total_usd", 0)) > 0:
            confidence += 0.05
        
        return min(confidence, 1.0)
