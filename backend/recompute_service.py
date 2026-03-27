"""
Recompute Integrity Enforcement Service

Ensures all critical changes trigger full recompute of:
- Tax lots
- Tax disposals
- Validation state

No partial updates allowed - full rebuild on any change to:
- Linkage changes
- Classification changes
- Proceeds application
- Price backfill

Stores recompute timestamp for audit tracking.
"""

import logging
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class RecomputeTrigger(Enum):
    """Types of changes that trigger recompute"""
    LINKAGE_CHANGE = "linkage_change"
    CLASSIFICATION_CHANGE = "classification_change"
    PROCEEDS_APPLICATION = "proceeds_application"
    PRICE_BACKFILL = "price_backfill"
    TRANSACTION_IMPORT = "transaction_import"
    TRANSACTION_DELETE = "transaction_delete"
    MANUAL_REQUEST = "manual_request"
    ROLLBACK = "rollback"


class RecomputeService:
    """
    Service for ensuring recompute integrity.
    
    All critical changes MUST go through this service to ensure
    tax lots, disposals, and validation state are kept in sync.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def full_recompute(
        self,
        user_id: str,
        trigger: RecomputeTrigger = RecomputeTrigger.MANUAL_REQUEST,
        trigger_details: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Perform full recompute of tax state for a user.
        
        Rebuilds:
        1. Tax lots from all acquisitions
        2. Tax disposals by matching lots to sells
        3. Validation state
        
        No partial updates - complete rebuild every time.
        """
        recompute_id = str(uuid.uuid4())
        start_time = datetime.now(timezone.utc)
        
        result = {
            "recompute_id": recompute_id,
            "user_id": user_id,
            "trigger": trigger.value,
            "trigger_details": trigger_details or {},
            "started_at": start_time.isoformat(),
            "status": "in_progress",
            "lots_created": 0,
            "disposals_created": 0,
            "validation_status": None,
            "can_export": None
        }
        
        try:
            # Step 1: Clear existing computed state
            await self._clear_computed_state(user_id)
            
            # Step 2: Rebuild tax lots from acquisitions
            lots_created = await self._rebuild_tax_lots(user_id)
            result["lots_created"] = lots_created
            
            # Step 3: Rebuild disposals by matching lots
            disposals_created = await self._rebuild_disposals(user_id)
            result["disposals_created"] = disposals_created
            
            # Step 4: Rebuild validation state
            validation = await self._rebuild_validation_state(user_id)
            result["validation_status"] = validation.get("validation_status")
            result["can_export"] = validation.get("can_export")
            
            # Step 5: Store recompute timestamp
            await self._store_recompute_timestamp(user_id, recompute_id, result)
            
            result["status"] = "completed"
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
            
        except Exception as e:
            logger.error(f"Recompute failed for user {user_id}: {e}")
            result["status"] = "failed"
            result["error"] = str(e)
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Store recompute result in audit trail
        await self._store_recompute_audit(result)
        
        return result
    
    async def get_last_recompute(self, user_id: str) -> Optional[Dict]:
        """Get the last recompute timestamp and details for a user"""
        record = await self.db.recompute_state.find_one(
            {"user_id": user_id},
            {"_id": 0}
        )
        return record
    
    async def is_recompute_needed(self, user_id: str) -> Dict[str, Any]:
        """
        Check if recompute is needed based on pending changes.
        
        Returns whether recompute is needed and why.
        """
        last_recompute = await self.get_last_recompute(user_id)
        last_ts = last_recompute.get("timestamp") if last_recompute else None
        
        # Check for changes since last recompute
        needs_recompute = False
        reasons = []
        
        # Check for new transactions since last recompute
        if last_ts:
            new_txs = await self.db.exchange_transactions.count_documents({
                "user_id": user_id,
                "created_at": {"$gt": last_ts}
            })
            if new_txs > 0:
                needs_recompute = True
                reasons.append(f"{new_txs} new transactions since last recompute")
        
        # Check for pending linkage changes
        pending_links = await self.db.linkage_edges.count_documents({
            "user_id": user_id,
            "pending_recompute": True
        })
        if pending_links > 0:
            needs_recompute = True
            reasons.append(f"{pending_links} pending linkage changes")
        
        # Check for pending price backfills
        pending_backfills = await self.db.exchange_transactions.count_documents({
            "user_id": user_id,
            "price_backfill.pending_recompute": True
        })
        if pending_backfills > 0:
            needs_recompute = True
            reasons.append(f"{pending_backfills} pending price backfills")
        
        return {
            "needs_recompute": needs_recompute,
            "reasons": reasons,
            "last_recompute": last_ts
        }
    
    async def mark_pending_recompute(
        self,
        user_id: str,
        trigger: RecomputeTrigger,
        details: Optional[Dict] = None
    ):
        """Mark that a recompute is pending for a user"""
        await self.db.recompute_state.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "pending_recompute": True,
                    "pending_trigger": trigger.value,
                    "pending_details": details or {},
                    "pending_since": datetime.now(timezone.utc).isoformat()
                }
            },
            upsert=True
        )
    
    # === PRIVATE METHODS ===
    
    async def _clear_computed_state(self, user_id: str):
        """Clear all computed state (lots, disposals) for rebuild"""
        # Note: We keep derived_proceeds_acquisition records as they are source data
        await self.db.tax_lots.delete_many({"user_id": user_id})
        await self.db.tax_disposals.delete_many({"user_id": user_id})
        
        logger.info(f"Cleared computed state for user {user_id}")
    
    async def _rebuild_tax_lots(self, user_id: str) -> int:
        """Rebuild tax lots from all acquisitions"""
        # Get all acquisition transactions
        acquisition_types = [
            "buy", "receive", "reward", "staking", "airdrop", 
            "mining", "interest", "derived_proceeds_acquisition",
            "proceeds_acquisition"
        ]
        
        acquisitions = await self.db.exchange_transactions.find({
            "user_id": user_id,
            "tx_type": {"$in": acquisition_types}
        }).sort("timestamp", 1).to_list(100000)
        
        lots_created = 0
        
        for acq in acquisitions:
            asset = acq.get("asset", "").upper()
            quantity = float(acq.get("quantity", 0) or acq.get("amount", 0) or 0)
            cost_basis = float(acq.get("total_usd", 0) or 0)
            
            if quantity <= 0:
                continue
            
            lot = {
                "lot_id": str(uuid.uuid4()),
                "user_id": user_id,
                "source_tx_id": acq.get("tx_id"),
                "asset": asset,
                "original_quantity": quantity,
                "remaining_quantity": quantity,
                "cost_basis": cost_basis,
                "cost_per_unit": cost_basis / quantity if quantity > 0 else 0,
                "acquisition_date": acq.get("timestamp"),
                "acquisition_type": acq.get("tx_type"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self.db.tax_lots.insert_one(lot)
            lots_created += 1
        
        logger.info(f"Rebuilt {lots_created} tax lots for user {user_id}")
        return lots_created
    
    async def _rebuild_disposals(self, user_id: str) -> int:
        """Rebuild tax disposals by matching lots to sells (FIFO)"""
        # Get all sell transactions
        sells = await self.db.exchange_transactions.find({
            "user_id": user_id,
            "tx_type": {"$in": ["sell", "send", "transfer"]},
            "chain_status": {"$ne": "linked"}  # Exclude internal transfers
        }).sort("timestamp", 1).to_list(100000)
        
        disposals_created = 0
        
        for sell in sells:
            asset = sell.get("asset", "").upper()
            quantity = float(sell.get("quantity", 0) or sell.get("amount", 0) or 0)
            proceeds = float(sell.get("total_usd", 0) or 0)
            
            if quantity <= 0:
                continue
            
            # Find lots to match (FIFO)
            remaining_to_dispose = quantity
            cost_basis = 0.0
            matched_lots = []
            
            lots = await self.db.tax_lots.find({
                "user_id": user_id,
                "asset": asset,
                "remaining_quantity": {"$gt": 0}
            }).sort("acquisition_date", 1).to_list(10000)
            
            for lot in lots:
                if remaining_to_dispose <= 0:
                    break
                
                available = lot["remaining_quantity"]
                use_qty = min(available, remaining_to_dispose)
                use_cost = use_qty * lot["cost_per_unit"]
                
                # Update lot
                await self.db.tax_lots.update_one(
                    {"lot_id": lot["lot_id"]},
                    {"$inc": {"remaining_quantity": -use_qty}}
                )
                
                matched_lots.append({
                    "lot_id": lot["lot_id"],
                    "quantity": use_qty,
                    "cost_basis": use_cost
                })
                
                cost_basis += use_cost
                remaining_to_dispose -= use_qty
            
            # Create disposal record
            gain_loss = proceeds - cost_basis
            
            # Determine holding period
            earliest_lot = matched_lots[0] if matched_lots else None
            if earliest_lot:
                earliest_lot_data = next(
                    (lot for lot in lots if lot["lot_id"] == earliest_lot["lot_id"]), 
                    None
                )
                if earliest_lot_data:
                    try:
                        acq_date = datetime.fromisoformat(
                            str(earliest_lot_data["acquisition_date"]).replace('Z', '+00:00')
                        )
                        sell_date = datetime.fromisoformat(
                            str(sell.get("timestamp")).replace('Z', '+00:00')
                        )
                        days_held = (sell_date - acq_date).days
                        term = "long" if days_held > 365 else "short"
                    except Exception:
                        term = "short"
                else:
                    term = "short"
            else:
                term = "short"
            
            disposal = {
                "disposal_id": str(uuid.uuid4()),
                "user_id": user_id,
                "source_tx_id": sell.get("tx_id"),
                "asset": asset,
                "quantity": quantity,
                "proceeds": proceeds,
                "cost_basis": cost_basis,
                "gain_loss": gain_loss,
                "term": term,
                "disposal_date": sell.get("timestamp"),
                "matched_lots": matched_lots,
                "orphan_quantity": remaining_to_dispose if remaining_to_dispose > 0 else 0,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await self.db.tax_disposals.insert_one(disposal)
            disposals_created += 1
        
        logger.info(f"Rebuilt {disposals_created} disposals for user {user_id}")
        return disposals_created
    
    async def _rebuild_validation_state(self, user_id: str) -> Dict:
        """Rebuild validation state"""
        try:
            from beta_validation_harness import BetaValidationHarness
            harness = BetaValidationHarness(self.db)
            report = await harness.validate_user_account(user_id)
            return {
                "validation_status": report.get("validation_status", "unknown"),
                "can_export": report.get("can_export", False)
            }
        except Exception as e:
            logger.warning(f"Could not rebuild validation state: {e}")
            return {"validation_status": "unknown", "can_export": False}
    
    async def _store_recompute_timestamp(
        self,
        user_id: str,
        recompute_id: str,
        result: Dict
    ):
        """Store recompute timestamp and clear pending flag"""
        await self.db.recompute_state.update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "user_id": user_id,
                    "last_recompute_id": recompute_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "lots_created": result.get("lots_created", 0),
                    "disposals_created": result.get("disposals_created", 0),
                    "validation_status": result.get("validation_status"),
                    "can_export": result.get("can_export"),
                    "pending_recompute": False
                },
                "$unset": {
                    "pending_trigger": "",
                    "pending_details": "",
                    "pending_since": ""
                }
            },
            upsert=True
        )
    
    async def _store_recompute_audit(self, result: Dict):
        """Store recompute result in audit trail"""
        audit_entry = {
            "entry_id": str(uuid.uuid4()),
            "user_id": result["user_id"],
            "action": "full_recompute",
            "timestamp": result.get("completed_at") or datetime.now(timezone.utc).isoformat(),
            "details": result
        }
        await self.db.tax_audit_trail.insert_one(audit_entry)
