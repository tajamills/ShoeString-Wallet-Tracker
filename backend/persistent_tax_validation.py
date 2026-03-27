"""
Persistent Tax Validation State

Stores validation state (lots, disposals, audit trail) in MongoDB
for persistence across requests and sessions.

P1 Implementation:
- tax_lots collection: Store lot records
- tax_disposals collection: Store disposal records  
- tax_audit_trail collection: Store audit trail
- Auto-trigger recompute on linkage changes
- Add validation status to API responses
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
import uuid

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class PersistentTaxValidationService:
    """
    Persistent version of TaxValidationService that stores state in MongoDB.
    
    Collections:
    - tax_lots: Lot records with acquisition info
    - tax_disposals: Disposal records with lot matching
    - tax_audit_trail: Audit trail entries
    - tax_validation_state: Per-user validation status
    """
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.lots_collection = db.tax_lots
        self.disposals_collection = db.tax_disposals
        self.audit_collection = db.tax_audit_trail
        self.state_collection = db.tax_validation_state
    
    # ========================================
    # LOT MANAGEMENT
    # ========================================
    
    async def create_lot(
        self,
        user_id: str,
        tx_id: str,
        asset: str,
        acquisition_date: datetime,
        quantity: float,
        cost_basis_per_unit: float,
        source: str,
        classification: str,
        price_source: str = "original"
    ) -> Dict:
        """Create a new tax lot and persist to MongoDB"""
        
        # Validate constraints
        if quantity <= 0:
            raise ValueError(f"Lot quantity must be positive: {quantity}")
        
        if cost_basis_per_unit < 0:
            await self._add_violation(user_id, "NEGATIVE_COST_BASIS", asset, 
                                       f"Negative cost basis: ${cost_basis_per_unit}")
            raise ValueError(f"Cost basis cannot be negative: {cost_basis_per_unit}")
        
        lot = {
            "lot_id": str(uuid.uuid4()),
            "user_id": user_id,
            "tx_id": tx_id,
            "asset": asset.upper(),
            "acquisition_date": acquisition_date,
            "quantity": quantity,
            "remaining_quantity": quantity,
            "cost_basis_per_unit": cost_basis_per_unit,
            "total_cost_basis": quantity * cost_basis_per_unit,
            "source": source,
            "classification": classification,
            "price_source": price_source,
            "is_disposed": False,
            "disposed_quantity": 0.0,
            "created_at": datetime.now(timezone.utc)
        }
        
        await self.lots_collection.insert_one(lot)
        
        # Log audit
        await self._log_audit(user_id, "create_lot", tx_id, {
            "lot_id": lot["lot_id"],
            "asset": asset,
            "quantity": quantity,
            "cost_basis_per_unit": cost_basis_per_unit
        })
        
        # Remove MongoDB _id before returning
        lot.pop("_id", None)
        return lot
    
    async def get_lots(self, user_id: str, asset: str = None) -> List[Dict]:
        """Get all lots for a user, optionally filtered by asset"""
        query = {"user_id": user_id}
        if asset:
            query["asset"] = asset.upper()
        
        lots = await self.lots_collection.find(
            query, {"_id": 0}
        ).sort("acquisition_date", 1).to_list(100000)
        
        return lots
    
    async def dispose_from_lots(
        self,
        user_id: str,
        tx_id: str,
        asset: str,
        disposal_date: datetime,
        quantity: float,
        proceeds: float
    ) -> Dict:
        """Dispose from lots using FIFO and persist to MongoDB"""
        
        asset_upper = asset.upper()
        
        # Get available lots
        lots = await self.lots_collection.find({
            "user_id": user_id,
            "asset": asset_upper,
            "remaining_quantity": {"$gt": 0}
        }).sort("acquisition_date", 1).to_list(100000)
        
        if not lots:
            await self._add_violation(user_id, "NO_ORPHAN_DISPOSAL", asset,
                                       f"Disposal of {quantity} {asset} has no acquisition source")
            raise ValueError(f"No lots available for disposal: {asset}")
        
        # Check total available
        total_available = sum(lot["remaining_quantity"] for lot in lots)
        if quantity > total_available:
            await self._add_violation(user_id, "QUANTITY_EXCEEDED", asset,
                                       f"Disposal {quantity} exceeds available {total_available}")
            raise ValueError(f"Insufficient quantity: trying to dispose {quantity} but only {total_available} available")
        
        # FIFO matching
        remaining_to_dispose = quantity
        total_cost_basis = 0.0
        matched_lots = []
        earliest_acquisition = None
        
        for lot in lots:
            if remaining_to_dispose <= 0:
                break
            
            if lot["remaining_quantity"] <= 0:
                continue
            
            match_qty = min(lot["remaining_quantity"], remaining_to_dispose)
            match_cost = match_qty * lot["cost_basis_per_unit"]
            
            # Update lot in database
            new_remaining = lot["remaining_quantity"] - match_qty
            new_disposed = lot.get("disposed_quantity", 0) + match_qty
            
            await self.lots_collection.update_one(
                {"lot_id": lot["lot_id"]},
                {"$set": {
                    "remaining_quantity": new_remaining,
                    "disposed_quantity": new_disposed,
                    "is_disposed": new_remaining <= 0
                }}
            )
            
            matched_lots.append({
                "lot_id": lot["lot_id"],
                "quantity_matched": match_qty,
                "cost_basis_matched": match_cost,
                "acquisition_date": lot["acquisition_date"].isoformat() if isinstance(lot["acquisition_date"], datetime) else lot["acquisition_date"],
                "cost_basis_per_unit": lot["cost_basis_per_unit"]
            })
            
            total_cost_basis += match_cost
            remaining_to_dispose -= match_qty
            
            if earliest_acquisition is None:
                earliest_acquisition = lot["acquisition_date"]
        
        # Calculate holding period
        if earliest_acquisition:
            if isinstance(earliest_acquisition, str):
                earliest_acquisition = datetime.fromisoformat(earliest_acquisition.replace("Z", "+00:00"))
            
            # Ensure both are timezone-aware
            if earliest_acquisition.tzinfo is None:
                earliest_acquisition = earliest_acquisition.replace(tzinfo=timezone.utc)
            if disposal_date.tzinfo is None:
                disposal_date = disposal_date.replace(tzinfo=timezone.utc)
            
            days_held = (disposal_date - earliest_acquisition).days
            holding_period = "long-term" if days_held > 365 else "short-term"
        else:
            holding_period = "unknown"
        
        # Create disposal record
        disposal = {
            "disposal_id": str(uuid.uuid4()),
            "user_id": user_id,
            "tx_id": tx_id,
            "asset": asset_upper,
            "disposal_date": disposal_date,
            "quantity": quantity,
            "proceeds": proceeds,
            "total_cost_basis": total_cost_basis,
            "gain_loss": proceeds - total_cost_basis,
            "holding_period": holding_period,
            "matched_lots": matched_lots,
            "created_at": datetime.now(timezone.utc)
        }
        
        await self.disposals_collection.insert_one(disposal)
        
        # Log audit
        await self._log_audit(user_id, "dispose_from_lots", tx_id, {
            "disposal_id": disposal["disposal_id"],
            "asset": asset,
            "quantity": quantity,
            "proceeds": proceeds,
            "cost_basis": total_cost_basis,
            "gain_loss": disposal["gain_loss"]
        })
        
        disposal.pop("_id", None)
        return disposal
    
    async def get_disposals(self, user_id: str, tax_year: int = None) -> List[Dict]:
        """Get all disposals for a user"""
        query = {"user_id": user_id}
        
        if tax_year:
            query["disposal_date"] = {
                "$gte": datetime(tax_year, 1, 1, tzinfo=timezone.utc),
                "$lte": datetime(tax_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
            }
        
        disposals = await self.disposals_collection.find(
            query, {"_id": 0}
        ).sort("disposal_date", 1).to_list(100000)
        
        return disposals
    
    # ========================================
    # VALIDATION STATE
    # ========================================
    
    async def get_validation_status(self, user_id: str) -> Dict:
        """Get current validation status for a user"""
        state = await self.state_collection.find_one(
            {"user_id": user_id}, {"_id": 0}
        )
        
        if not state:
            return {
                "user_id": user_id,
                "is_valid": True,
                "can_export": True,
                "last_validated": None,
                "violations": []
            }
        
        return state
    
    async def update_validation_status(
        self,
        user_id: str,
        is_valid: bool,
        can_export: bool,
        violations: List[Dict] = None
    ):
        """Update validation status for a user"""
        await self.state_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "is_valid": is_valid,
                "can_export": can_export,
                "violations": violations or [],
                "last_validated": datetime.now(timezone.utc)
            }},
            upsert=True
        )
    
    async def _add_violation(self, user_id: str, violation_type: str, asset: str, message: str):
        """Add a violation to the user's state"""
        violation = {
            "type": violation_type,
            "asset": asset,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        await self.state_collection.update_one(
            {"user_id": user_id},
            {
                "$set": {"is_valid": False, "can_export": False},
                "$push": {"violations": violation}
            },
            upsert=True
        )
    
    # ========================================
    # RECOMPUTE LOGIC
    # ========================================
    
    async def trigger_full_recompute(self, user_id: str, reason: str) -> Dict:
        """
        Trigger full recomputation of tax data.
        Clears all lots and disposals for the user.
        
        Should be called when:
        - Wallet linkage changes
        - Classification changes
        - Transaction data changes
        """
        # Count what we're deleting
        lots_count = await self.lots_collection.count_documents({"user_id": user_id})
        disposals_count = await self.disposals_collection.count_documents({"user_id": user_id})
        
        # Delete all lots and disposals
        await self.lots_collection.delete_many({"user_id": user_id})
        await self.disposals_collection.delete_many({"user_id": user_id})
        
        # Reset validation state
        await self.state_collection.update_one(
            {"user_id": user_id},
            {"$set": {
                "is_valid": True,
                "can_export": True,
                "violations": [],
                "last_recompute": datetime.now(timezone.utc),
                "recompute_reason": reason
            }},
            upsert=True
        )
        
        # Log audit
        await self._log_audit(user_id, "trigger_full_recompute", None, {
            "reason": reason,
            "cleared_lots": lots_count,
            "cleared_disposals": disposals_count
        })
        
        return {
            "recompute_triggered": True,
            "reason": reason,
            "cleared_lots": lots_count,
            "cleared_disposals": disposals_count,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    # ========================================
    # AUDIT TRAIL
    # ========================================
    
    async def _log_audit(self, user_id: str, action: str, tx_id: Optional[str], details: Dict):
        """Log action to audit trail"""
        entry = {
            "audit_id": str(uuid.uuid4()),
            "user_id": user_id,
            "action": action,
            "tx_id": tx_id,
            "timestamp": datetime.now(timezone.utc),
            "details": details
        }
        
        await self.audit_collection.insert_one(entry)
    
    async def get_audit_trail(self, user_id: str, limit: int = 100) -> List[Dict]:
        """Get recent audit trail entries"""
        entries = await self.audit_collection.find(
            {"user_id": user_id}, {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return entries
    
    # ========================================
    # BALANCE CHECK
    # ========================================
    
    async def get_asset_balance(self, user_id: str, asset: str) -> Dict:
        """Get current balance and cost basis for an asset"""
        lots = await self.get_lots(user_id, asset)
        
        total_quantity = sum(lot["remaining_quantity"] for lot in lots)
        total_cost_basis = sum(
            lot["remaining_quantity"] * lot["cost_basis_per_unit"]
            for lot in lots
        )
        
        return {
            "asset": asset.upper(),
            "quantity": total_quantity,
            "cost_basis": total_cost_basis,
            "lot_count": len(lots),
            "average_cost": total_cost_basis / total_quantity if total_quantity > 0 else 0
        }
    
    async def get_all_balances(self, user_id: str) -> Dict[str, Dict]:
        """Get balances for all assets"""
        # Get unique assets
        assets = await self.lots_collection.distinct("asset", {"user_id": user_id})
        
        balances = {}
        for asset in assets:
            balances[asset] = await self.get_asset_balance(user_id, asset)
        
        return balances


# Integration helper - hooks into existing tax service
async def hook_linkage_change(db, user_id: str, change_type: str):
    """
    Hook to be called when wallet linkage changes.
    Triggers full recompute of tax data.
    """
    service = PersistentTaxValidationService(db)
    return await service.trigger_full_recompute(user_id, f"linkage_change:{change_type}")


async def hook_classification_change(db, user_id: str, tx_id: str):
    """
    Hook to be called when transaction classification changes.
    Triggers full recompute of tax data.
    """
    service = PersistentTaxValidationService(db)
    return await service.trigger_full_recompute(user_id, f"classification_change:{tx_id}")


async def add_validation_status_to_response(db, user_id: str, response: Dict) -> Dict:
    """
    Add validation status to any API response.
    
    Usage:
        response = {"data": ...}
        response = await add_validation_status_to_response(db, user_id, response)
    """
    service = PersistentTaxValidationService(db)
    status = await service.get_validation_status(user_id)
    
    response["validation_status"] = {
        "is_valid": status.get("is_valid", True),
        "can_export": status.get("can_export", True),
        "violations_count": len(status.get("violations", []))
    }
    
    return response
