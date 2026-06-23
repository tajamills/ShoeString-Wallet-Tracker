"""
Portfolio Routes - CoinTracker Parity API
Endpoints for wallet linking, cost basis tracking, and portfolio management
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone

from routes.dependencies import get_current_user
from services.portfolio_service import portfolio_service
from models.portfolio_models import (
    TransactionType, CostBasisMethod, LinkWalletRequest,
    ClassifyTransactionRequest, PortfolioSettingsUpdate
)

router = APIRouter()


# ========== WALLET MANAGEMENT ==========

@router.post("/wallets/link")
async def link_wallet(
    request: LinkWalletRequest,
    user: dict = Depends(get_current_user)
):
    """Link a new wallet to your portfolio"""
    try:
        wallet = await portfolio_service.link_wallet(
            user_id=user["id"],
            address=request.address,
            chain=request.chain,
            nickname=request.nickname,
            wallet_group=request.wallet_group
        )
        return {
            "success": True,
            "message": f"Wallet linked successfully",
            "wallet": {
                "wallet_id": wallet.wallet_id,
                "address": wallet.address,
                "chain": wallet.chain,
                "nickname": wallet.nickname
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to link wallet: {str(e)}")


@router.get("/wallets")
async def get_linked_wallets(user: dict = Depends(get_current_user)):
    """Get all linked wallets"""
    try:
        wallets = await portfolio_service.get_linked_wallets(user["id"])
        return {
            "wallets": [
                {
                    "wallet_id": w.wallet_id,
                    "address": w.address,
                    "chain": w.chain,
                    "nickname": w.nickname,
                    "wallet_group": w.wallet_group,
                    "is_primary": w.is_primary,
                    "sync_status": w.sync_status,
                    "last_synced_at": w.last_synced_at.isoformat() if w.last_synced_at else None
                }
                for w in wallets
            ],
            "count": len(wallets)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get wallets: {str(e)}")


@router.delete("/wallets/{wallet_id}")
async def unlink_wallet(wallet_id: str, user: dict = Depends(get_current_user)):
    """Unlink a wallet from your portfolio"""
    try:
        success = await portfolio_service.unlink_wallet(user["id"], wallet_id)
        if not success:
            raise HTTPException(status_code=404, detail="Wallet not found")
        return {"success": True, "message": "Wallet unlinked"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to unlink wallet: {str(e)}")


# ========== TRANSACTIONS ==========

@router.get("/transactions")
async def get_transactions(
    chain: Optional[str] = None,
    tx_type: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user)
):
    """Get portfolio transactions with filtering"""
    try:
        type_filter = TransactionType(tx_type) if tx_type else None
        
        txs = await portfolio_service.get_transactions(
            user_id=user["id"],
            chain=chain,
            tx_type=type_filter,
            limit=limit,
            offset=offset
        )
        
        return {
            "transactions": [
                {
                    "tx_id": tx.tx_id,
                    "tx_hash": tx.tx_hash,
                    "chain": tx.chain,
                    "timestamp": tx.timestamp.isoformat(),
                    "tx_type": tx.user_classification or tx.tx_type,
                    "is_internal_transfer": tx.is_internal_transfer,
                    "asset_symbol": tx.asset_symbol,
                    "quantity": tx.quantity,
                    "value_usd": tx.value_usd,
                    "from_address": tx.from_address,
                    "to_address": tx.to_address,
                    "realized_gain_usd": tx.realized_gain_usd,
                    "user_notes": tx.user_notes
                }
                for tx in txs
            ],
            "count": len(txs),
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transactions: {str(e)}")


@router.post("/transactions/classify")
async def classify_transaction(
    request: ClassifyTransactionRequest,
    user: dict = Depends(get_current_user)
):
    """Manually classify a transaction"""
    try:
        success = await portfolio_service.reclassify_transaction(
            user_id=user["id"],
            tx_id=request.tx_id,
            new_type=request.tx_type,
            notes=request.notes
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        return {"success": True, "message": "Transaction classified"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to classify: {str(e)}")


# ========== HOLDINGS ==========

@router.get("/holdings")
async def get_holdings(
    wallet_id: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get current token holdings"""
    try:
        holdings = await portfolio_service.get_holdings(user["id"], wallet_id)
        
        return {
            "holdings": [
                {
                    "asset_symbol": h.asset_symbol,
                    "asset_name": h.asset_name,
                    "chain": h.chain,
                    "wallet_address": h.wallet_address,
                    "balance": h.balance,
                    "price_usd": h.price_usd,
                    "value_usd": h.value_usd,
                    "contract_address": h.contract_address,
                    "last_updated": h.last_updated.isoformat()
                }
                for h in holdings
            ],
            "count": len(holdings),
            "total_value_usd": sum(h.value_usd or 0 for h in holdings)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get holdings: {str(e)}")


# ========== TAX LOTS / COST BASIS ==========

@router.get("/tax-lots")
async def get_tax_lots(
    asset_symbol: Optional[str] = None,
    include_disposed: bool = False,
    user: dict = Depends(get_current_user)
):
    """Get tax lots for cost basis tracking"""
    try:
        query = {"user_id": user["id"]}
        if asset_symbol:
            query["asset_symbol"] = asset_symbol.upper()
        if not include_disposed:
            query["is_fully_disposed"] = False
        
        lots = await portfolio_service.db.tax_lots.find(
            query, {"_id": 0}
        ).sort("acquisition_date", 1).to_list(length=1000)
        
        return {
            "tax_lots": [
                {
                    "lot_id": lot["lot_id"],
                    "asset_symbol": lot["asset_symbol"],
                    "chain": lot["chain"],
                    "acquisition_date": lot["acquisition_date"],
                    "acquisition_type": lot["acquisition_type"],
                    "quantity": lot["quantity"],
                    "remaining_quantity": lot["remaining_quantity"],
                    "cost_basis_usd": lot["cost_basis_usd"],
                    "cost_per_unit_usd": lot["cost_per_unit_usd"],
                    "is_fully_disposed": lot["is_fully_disposed"],
                    "disposal_count": len(lot.get("disposals", []))
                }
                for lot in lots
            ],
            "count": len(lots)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get tax lots: {str(e)}")


class AddTaxLotRequest(BaseModel):
    """Request to manually add a tax lot"""
    asset_symbol: str
    chain: str
    acquisition_date: datetime
    acquisition_type: str = "buy"
    quantity: float
    cost_basis_usd: float
    source_wallet: str
    tx_hash: Optional[str] = None


@router.post("/tax-lots")
async def add_tax_lot(
    request: AddTaxLotRequest,
    user: dict = Depends(get_current_user)
):
    """Manually add a tax lot (for imports or corrections)"""
    try:
        acq_type = TransactionType(request.acquisition_type)
        
        lot = await portfolio_service.create_tax_lot(
            user_id=user["id"],
            asset_symbol=request.asset_symbol,
            chain=request.chain,
            acquisition_date=request.acquisition_date,
            acquisition_type=acq_type,
            quantity=request.quantity,
            cost_basis_usd=request.cost_basis_usd,
            source_wallet=request.source_wallet,
            tx_hash=request.tx_hash
        )
        
        return {
            "success": True,
            "lot_id": lot.lot_id,
            "message": f"Tax lot created for {request.quantity} {request.asset_symbol}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create tax lot: {str(e)}")


# ========== PORTFOLIO SUMMARY ==========

@router.get("/summary")
async def get_portfolio_summary(user: dict = Depends(get_current_user)):
    """Get aggregated portfolio summary with gains/losses"""
    try:
        summary = await portfolio_service.get_portfolio_summary(user["id"])
        
        return {
            "total_value_usd": summary.total_value_usd,
            "total_cost_basis_usd": summary.total_cost_basis_usd,
            "unrealized_gain_usd": summary.total_unrealized_gain_usd,
            "unrealized_gain_percent": (
                (summary.total_unrealized_gain_usd / summary.total_cost_basis_usd * 100)
                if summary.total_cost_basis_usd > 0 else 0
            ),
            "realized_gain_usd": summary.total_realized_gain_usd,
            "holdings": summary.holdings[:20],  # Top 20 by value
            "wallets": summary.wallets,
            "last_synced_at": summary.last_synced_at.isoformat() if summary.last_synced_at else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")


# ========== SYNC ==========

class SyncWalletRequest(BaseModel):
    wallet_id: str


@router.post("/sync")
async def sync_wallet(
    request: SyncWalletRequest,
    user: dict = Depends(get_current_user)
):
    """Sync a wallet - fetch transactions and update holdings"""
    try:
        # Get the wallet
        wallet = await portfolio_service.db.linked_wallets.find_one({
            "user_id": user["id"],
            "wallet_id": request.wallet_id
        })
        
        if not wallet:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        # Update sync status
        await portfolio_service.db.linked_wallets.update_one(
            {"wallet_id": request.wallet_id},
            {"$set": {"sync_status": "syncing"}}
        )
        
        # Import the chain analyzers
        from multi_chain_service import MultiChainService
        multi_chain_service = MultiChainService()
        
        # Analyze wallet
        analysis = multi_chain_service.analyze_wallet(
            address=wallet["address"],
            chain=wallet["chain"]
        )
        
        # Update holdings for native token
        chain_symbols = {
            "ethereum": "ETH", "polygon": "MATIC", "arbitrum": "ETH",
            "bsc": "BNB", "bitcoin": "BTC", "solana": "SOL",
            "algorand": "ALGO", "dogecoin": "DOGE", "xrp": "XRP", "xlm": "XLM"
        }
        native_symbol = chain_symbols.get(wallet["chain"], "ETH")
        
        await portfolio_service.update_token_holding(
            user_id=user["id"],
            wallet_id=wallet["wallet_id"],
            wallet_address=wallet["address"],
            chain=wallet["chain"],
            asset_symbol=native_symbol,
            balance=analysis.get("current_balance", 0),
            balance_raw=str(analysis.get("current_balance", 0)),
            price_usd=analysis.get("price_usd")
        )
        
        # Process recent transactions
        for tx in analysis.get("recent_transactions", [])[:50]:
            try:
                await portfolio_service.classify_transaction(
                    user_id=user["id"],
                    tx_hash=tx.get("hash", ""),
                    chain=wallet["chain"],
                    from_address=tx.get("from", ""),
                    to_address=tx.get("to", ""),
                    asset_symbol=tx.get("asset", native_symbol),
                    quantity=abs(float(tx.get("value", 0))),
                    timestamp=datetime.fromisoformat(tx.get("timestamp", datetime.now(timezone.utc).isoformat()).replace("Z", "+00:00")),
                    price_usd=tx.get("price_usd")
                )
            except Exception as tx_error:
                # Log but continue
                print(f"Error processing tx: {tx_error}")
        
        # Update sync status
        await portfolio_service.db.linked_wallets.update_one(
            {"wallet_id": request.wallet_id},
            {"$set": {
                "sync_status": "synced",
                "last_synced_at": datetime.now(timezone.utc)
            }}
        )
        
        return {
            "success": True,
            "message": "Wallet synced successfully",
            "transactions_processed": len(analysis.get("recent_transactions", [])),
            "current_balance": analysis.get("current_balance", 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Update sync status to error
        await portfolio_service.db.linked_wallets.update_one(
            {"wallet_id": request.wallet_id},
            {"$set": {"sync_status": "error"}}
        )
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
