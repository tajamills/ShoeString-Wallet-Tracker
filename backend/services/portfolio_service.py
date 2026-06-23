"""
Portfolio Service - CoinTracker Parity
Core business logic for portfolio tracking, cost basis calculation, and wallet aggregation
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Set
from motor.motor_asyncio import AsyncIOMotorClient

from models.portfolio_models import (
    TransactionType, CostBasisMethod, TaxLot, LinkedWallet,
    PortfolioTransaction, TokenHolding, PortfolioSummary
)

logger = logging.getLogger(__name__)

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'test_database')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]


class PortfolioService:
    """Service for managing portfolio, wallets, and cost basis"""
    
    def __init__(self):
        self.db = db
    
    # ========== WALLET LINKING ==========
    
    async def link_wallet(self, user_id: str, address: str, chain: str, 
                          nickname: Optional[str] = None, wallet_group: Optional[str] = None) -> LinkedWallet:
        """Link a new wallet to user's portfolio"""
        address = address.lower()
        
        # Check if already linked
        existing = await self.db.linked_wallets.find_one({
            "user_id": user_id,
            "address": address,
            "chain": chain
        })
        
        if existing:
            raise ValueError("Wallet already linked to your portfolio")
        
        # Check if this is first wallet (make it primary)
        wallet_count = await self.db.linked_wallets.count_documents({"user_id": user_id})
        is_primary = wallet_count == 0
        
        wallet = LinkedWallet(
            user_id=user_id,
            address=address,
            chain=chain,
            nickname=nickname or f"{chain.upper()} Wallet",
            wallet_group=wallet_group,
            is_primary=is_primary,
            sync_status="pending"
        )
        
        await self.db.linked_wallets.insert_one(wallet.model_dump())
        logger.info(f"Linked wallet {address[:10]}... on {chain} for user {user_id}")
        
        return wallet
    
    async def get_linked_wallets(self, user_id: str) -> List[LinkedWallet]:
        """Get all wallets linked to user"""
        wallets = await self.db.linked_wallets.find(
            {"user_id": user_id},
            {"_id": 0}
        ).to_list(length=100)
        
        return [LinkedWallet(**w) for w in wallets]
    
    async def unlink_wallet(self, user_id: str, wallet_id: str) -> bool:
        """Remove a linked wallet"""
        result = await self.db.linked_wallets.delete_one({
            "user_id": user_id,
            "wallet_id": wallet_id
        })
        return result.deleted_count > 0
    
    async def get_user_wallet_addresses(self, user_id: str) -> Set[str]:
        """Get all wallet addresses for a user (for transfer detection)"""
        wallets = await self.db.linked_wallets.find(
            {"user_id": user_id},
            {"address": 1, "_id": 0}
        ).to_list(length=100)
        
        return {w["address"].lower() for w in wallets}
    
    # ========== TRANSACTION CLASSIFICATION ==========
    
    async def classify_transaction(
        self, 
        user_id: str,
        tx_hash: str,
        chain: str,
        from_address: str,
        to_address: str,
        asset_symbol: str,
        quantity: float,
        timestamp: datetime,
        price_usd: Optional[float] = None,
        fee_usd: Optional[float] = None
    ) -> PortfolioTransaction:
        """Classify a transaction and store it"""
        
        from_address = from_address.lower()
        to_address = to_address.lower()
        
        # Get user's wallet addresses
        user_wallets = await self.get_user_wallet_addresses(user_id)
        
        # Determine transaction type
        from_is_user = from_address in user_wallets
        to_is_user = to_address in user_wallets
        
        if from_is_user and to_is_user:
            # Transfer between own wallets - NOT taxable
            tx_type = TransactionType.TRANSFER_OUT  # Or TRANSFER_IN depending on perspective
            is_internal = True
        elif from_is_user and not to_is_user:
            # Sending out - could be sale, gift, or payment
            tx_type = TransactionType.SELL  # Default to sell, user can reclassify
            is_internal = False
        elif not from_is_user and to_is_user:
            # Receiving - could be buy, income, gift
            tx_type = TransactionType.BUY  # Default to buy, user can reclassify
            is_internal = False
        else:
            tx_type = TransactionType.UNKNOWN
            is_internal = False
        
        # Calculate USD value
        value_usd = (quantity * price_usd) if price_usd else None
        
        # Find wallet IDs
        from_wallet = await self.db.linked_wallets.find_one({
            "user_id": user_id, "address": from_address
        })
        to_wallet = await self.db.linked_wallets.find_one({
            "user_id": user_id, "address": to_address
        })
        
        tx = PortfolioTransaction(
            user_id=user_id,
            tx_hash=tx_hash,
            chain=chain,
            timestamp=timestamp,
            tx_type=tx_type,
            is_internal_transfer=is_internal,
            asset_symbol=asset_symbol,
            quantity=quantity,
            price_usd=price_usd,
            value_usd=value_usd,
            fee_usd=fee_usd,
            from_address=from_address,
            to_address=to_address,
            from_wallet_id=from_wallet["wallet_id"] if from_wallet else None,
            to_wallet_id=to_wallet["wallet_id"] if to_wallet else None
        )
        
        # Upsert transaction
        await self.db.portfolio_transactions.update_one(
            {"user_id": user_id, "tx_hash": tx_hash, "chain": chain},
            {"$set": tx.model_dump()},
            upsert=True
        )
        
        return tx
    
    async def reclassify_transaction(
        self, user_id: str, tx_id: str, new_type: TransactionType, notes: Optional[str] = None
    ) -> bool:
        """Manually reclassify a transaction"""
        result = await self.db.portfolio_transactions.update_one(
            {"user_id": user_id, "tx_id": tx_id},
            {"$set": {
                "user_classification": new_type.value,
                "user_notes": notes,
                "updated_at": datetime.now(timezone.utc)
            }}
        )
        return result.modified_count > 0
    
    async def get_transactions(
        self, user_id: str, 
        chain: Optional[str] = None,
        tx_type: Optional[TransactionType] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[PortfolioTransaction]:
        """Get user's portfolio transactions"""
        query = {"user_id": user_id}
        if chain:
            query["chain"] = chain
        if tx_type:
            query["tx_type"] = tx_type.value
        
        txs = await self.db.portfolio_transactions.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).skip(offset).limit(limit).to_list(length=limit)
        
        return [PortfolioTransaction(**tx) for tx in txs]
    
    # ========== COST BASIS / TAX LOTS ==========
    
    async def create_tax_lot(
        self,
        user_id: str,
        asset_symbol: str,
        chain: str,
        acquisition_date: datetime,
        acquisition_type: TransactionType,
        quantity: float,
        cost_basis_usd: float,
        source_wallet: str,
        tx_hash: Optional[str] = None
    ) -> TaxLot:
        """Create a new tax lot for an acquisition"""
        
        cost_per_unit = cost_basis_usd / quantity if quantity > 0 else 0
        
        lot = TaxLot(
            user_id=user_id,
            asset_symbol=asset_symbol.upper(),
            chain=chain,
            acquisition_date=acquisition_date,
            acquisition_type=acquisition_type,
            acquisition_tx_hash=tx_hash,
            quantity=quantity,
            remaining_quantity=quantity,
            cost_basis_usd=cost_basis_usd,
            cost_per_unit_usd=cost_per_unit,
            source_wallet=source_wallet.lower()
        )
        
        await self.db.tax_lots.insert_one(lot.model_dump())
        logger.info(f"Created tax lot for {quantity} {asset_symbol} at ${cost_per_unit:.2f}/unit")
        
        return lot
    
    async def get_available_lots(
        self, user_id: str, asset_symbol: str, method: CostBasisMethod = CostBasisMethod.FIFO
    ) -> List[TaxLot]:
        """Get available tax lots for an asset, sorted by cost basis method"""
        
        query = {
            "user_id": user_id,
            "asset_symbol": asset_symbol.upper(),
            "is_fully_disposed": False,
            "remaining_quantity": {"$gt": 0}
        }
        
        # Sort based on method
        if method == CostBasisMethod.FIFO:
            sort_key = ("acquisition_date", 1)  # Oldest first
        elif method == CostBasisMethod.LIFO:
            sort_key = ("acquisition_date", -1)  # Newest first
        elif method == CostBasisMethod.HIFO:
            sort_key = ("cost_per_unit_usd", -1)  # Highest cost first
        else:
            sort_key = ("acquisition_date", 1)
        
        lots = await self.db.tax_lots.find(
            query, {"_id": 0}
        ).sort([sort_key]).to_list(length=1000)
        
        return [TaxLot(**lot) for lot in lots]
    
    async def dispose_from_lots(
        self,
        user_id: str,
        asset_symbol: str,
        quantity_to_dispose: float,
        disposal_price_usd: float,
        disposal_date: datetime,
        disposal_tx_hash: str,
        method: CostBasisMethod = CostBasisMethod.FIFO
    ) -> Dict[str, Any]:
        """Dispose quantity from tax lots and calculate gains"""
        
        lots = await self.get_available_lots(user_id, asset_symbol, method)
        
        if not lots:
            logger.warning(f"No tax lots found for {asset_symbol}")
            return {
                "success": False,
                "error": "No cost basis lots found",
                "realized_gain": 0
            }
        
        remaining_to_dispose = quantity_to_dispose
        total_cost_basis = 0.0
        lots_used = []
        
        for lot in lots:
            if remaining_to_dispose <= 0:
                break
            
            # How much to take from this lot
            take_from_lot = min(remaining_to_dispose, lot.remaining_quantity)
            
            # Calculate cost basis for this portion
            portion_cost_basis = take_from_lot * lot.cost_per_unit_usd
            total_cost_basis += portion_cost_basis
            
            # Record disposal on lot
            disposal_record = {
                "date": disposal_date.isoformat(),
                "tx_hash": disposal_tx_hash,
                "quantity": take_from_lot,
                "proceeds_usd": take_from_lot * disposal_price_usd,
                "cost_basis_usd": portion_cost_basis,
                "gain_usd": (take_from_lot * disposal_price_usd) - portion_cost_basis
            }
            
            new_remaining = lot.remaining_quantity - take_from_lot
            is_fully_disposed = new_remaining <= 0.00000001  # Float tolerance
            
            # Update lot in DB
            await self.db.tax_lots.update_one(
                {"lot_id": lot.lot_id},
                {"$set": {
                    "remaining_quantity": max(0, new_remaining),
                    "is_fully_disposed": is_fully_disposed,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$push": {"disposals": disposal_record}}
            )
            
            lots_used.append({
                "lot_id": lot.lot_id,
                "quantity_used": take_from_lot,
                "cost_basis_used": portion_cost_basis
            })
            
            remaining_to_dispose -= take_from_lot
        
        # Calculate realized gain
        proceeds = quantity_to_dispose * disposal_price_usd
        realized_gain = proceeds - total_cost_basis
        
        return {
            "success": True,
            "quantity_disposed": quantity_to_dispose - remaining_to_dispose,
            "remaining_undisposed": remaining_to_dispose,
            "total_cost_basis": total_cost_basis,
            "proceeds": proceeds,
            "realized_gain": realized_gain,
            "lots_used": lots_used,
            "method": method.value
        }
    
    # ========== TOKEN HOLDINGS ==========
    
    async def update_token_holding(
        self,
        user_id: str,
        wallet_id: str,
        wallet_address: str,
        chain: str,
        asset_symbol: str,
        balance: float,
        balance_raw: str,
        contract_address: Optional[str] = None,
        asset_name: Optional[str] = None,
        price_usd: Optional[float] = None
    ) -> TokenHolding:
        """Update or create a token holding"""
        
        value_usd = balance * price_usd if price_usd else None
        
        holding = TokenHolding(
            user_id=user_id,
            wallet_id=wallet_id,
            wallet_address=wallet_address.lower(),
            chain=chain,
            asset_symbol=asset_symbol.upper(),
            asset_name=asset_name,
            contract_address=contract_address.lower() if contract_address else None,
            balance=balance,
            balance_raw=balance_raw,
            price_usd=price_usd,
            value_usd=value_usd,
            last_updated=datetime.now(timezone.utc)
        )
        
        # Upsert
        await self.db.token_holdings.update_one(
            {
                "user_id": user_id,
                "wallet_address": wallet_address.lower(),
                "chain": chain,
                "asset_symbol": asset_symbol.upper()
            },
            {"$set": holding.model_dump()},
            upsert=True
        )
        
        return holding
    
    async def get_holdings(
        self, user_id: str, wallet_id: Optional[str] = None
    ) -> List[TokenHolding]:
        """Get token holdings, optionally filtered by wallet"""
        
        query = {"user_id": user_id}
        if wallet_id:
            query["wallet_id"] = wallet_id
        
        holdings = await self.db.token_holdings.find(
            query, {"_id": 0}
        ).to_list(length=1000)
        
        return [TokenHolding(**h) for h in holdings]
    
    # ========== PORTFOLIO SUMMARY ==========
    
    async def get_portfolio_summary(self, user_id: str) -> PortfolioSummary:
        """Calculate aggregated portfolio summary"""
        
        # Get all holdings
        holdings = await self.get_holdings(user_id)
        
        # Aggregate by asset
        asset_totals: Dict[str, Dict] = {}
        wallet_totals: Dict[str, Dict] = {}
        
        total_value = 0.0
        
        for h in holdings:
            # By asset
            if h.asset_symbol not in asset_totals:
                asset_totals[h.asset_symbol] = {
                    "symbol": h.asset_symbol,
                    "total_balance": 0,
                    "total_value_usd": 0,
                    "price_usd": h.price_usd,
                    "chains": set()
                }
            asset_totals[h.asset_symbol]["total_balance"] += h.balance
            asset_totals[h.asset_symbol]["total_value_usd"] += h.value_usd or 0
            asset_totals[h.asset_symbol]["chains"].add(h.chain)
            
            # By wallet
            if h.wallet_id not in wallet_totals:
                wallet_totals[h.wallet_id] = {
                    "wallet_id": h.wallet_id,
                    "address": h.wallet_address,
                    "chain": h.chain,
                    "total_value_usd": 0,
                    "token_count": 0
                }
            wallet_totals[h.wallet_id]["total_value_usd"] += h.value_usd or 0
            wallet_totals[h.wallet_id]["token_count"] += 1
            
            total_value += h.value_usd or 0
        
        # Convert sets to lists for JSON serialization
        holdings_list = []
        for symbol, data in sorted(asset_totals.items(), key=lambda x: x[1]["total_value_usd"], reverse=True):
            data["chains"] = list(data["chains"])
            holdings_list.append(data)
        
        wallets_list = list(wallet_totals.values())
        
        # Calculate cost basis totals
        lots = await self.db.tax_lots.find(
            {"user_id": user_id, "is_fully_disposed": False},
            {"remaining_quantity": 1, "cost_per_unit_usd": 1, "_id": 0}
        ).to_list(length=10000)
        
        total_cost_basis = sum(lot["remaining_quantity"] * lot["cost_per_unit_usd"] for lot in lots)
        unrealized_gain = total_value - total_cost_basis
        
        # Get realized gains
        realized_pipeline = [
            {"$match": {"user_id": user_id}},
            {"$unwind": "$disposals"},
            {"$group": {"_id": None, "total_gain": {"$sum": "$disposals.gain_usd"}}}
        ]
        realized_result = await self.db.tax_lots.aggregate(realized_pipeline).to_list(length=1)
        total_realized_gain = realized_result[0]["total_gain"] if realized_result else 0
        
        return PortfolioSummary(
            user_id=user_id,
            total_value_usd=total_value,
            total_cost_basis_usd=total_cost_basis,
            total_unrealized_gain_usd=unrealized_gain,
            total_realized_gain_usd=total_realized_gain,
            holdings=holdings_list,
            wallets=wallets_list,
            last_synced_at=datetime.now(timezone.utc)
        )


# Singleton instance
portfolio_service = PortfolioService()
