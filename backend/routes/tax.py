"""Tax routes - Form 8949, categorization, unified tax calculations"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import io
import logging

from .dependencies import db, get_current_user, require_unlimited_tier
from .models import (
    Form8949Request, BatchCategoryRequest, AutoCategorizeRequest,
    UnifiedTaxRequest, ExchangeTaxRequest
)
from multi_chain_service import MultiChainService
from tax_report_service import tax_report_service
from unified_tax_service import unified_tax_service
from exchange_tax_service import exchange_tax_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tax", tags=["Tax"])

multi_chain_service = MultiChainService()


@router.post("/export-form-8949")
async def export_form_8949(
    request: Form8949Request,
    user: dict = Depends(get_current_user)
):
    """Export IRS Form 8949 compatible CSV (Premium/Pro feature)"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Form 8949 export is a Premium feature. Upgrade to access tax reports."
            )
        
        address = request.address.strip() if request.address else None
        chain = request.chain.lower()
        data_source = request.data_source
        
        symbol_map = {
            'ethereum': 'ETH',
            'bitcoin': 'BTC',
            'polygon': 'MATIC',
            'arbitrum': 'ETH',
            'bsc': 'BNB',
            'solana': 'SOL'
        }
        symbol = symbol_map.get(chain, 'ETH')
        
        wallet_transactions = []
        exchange_transactions = []
        current_balance = 0
        current_price = 0
        
        if data_source in ["wallet_only", "combined"] and address:
            analysis_data = multi_chain_service.analyze_wallet(
                address=address,
                chain=chain,
                user_tier=user_tier
            )
            wallet_transactions = analysis_data.get('recentTransactions', [])
            current_balance = analysis_data.get('currentBalance', 0)
            current_price = analysis_data.get('current_price_usd', 0)
        
        if data_source in ["exchange_only", "combined"]:
            exchange_txs = await db.exchange_transactions.find(
                {"user_id": user["id"]},
                {"_id": 0}
            ).to_list(10000)
            exchange_transactions = exchange_txs
        
        tax_data = unified_tax_service.calculate_unified_tax_data(
            wallet_transactions=wallet_transactions,
            exchange_transactions=exchange_transactions,
            symbol=symbol,
            current_price=current_price,
            current_balance=current_balance
        )
        
        realized_gains = tax_data.get('realized_gains', [])
        
        if not realized_gains:
            raise HTTPException(
                status_code=400,
                detail="No realized gains found. Import exchange transactions or analyze a wallet with sell transactions."
            )
        
        # Filter by tax year if specified
        if request.tax_year:
            realized_gains = [
                g for g in realized_gains
                if g.get('sell_date', '').startswith(str(request.tax_year))
            ]
        
        # Generate CSV
        csv_content = tax_report_service.generate_form_8949_csv(realized_gains)
        
        filename = f"Form_8949_{request.tax_year or 'All'}_{data_source}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating Form 8949: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate Form 8949: {str(e)}")


@router.get("/categories/{address}")
async def get_transaction_categories(
    address: str,
    chain: str = "ethereum",
    user: dict = Depends(get_current_user)
):
    """Get saved transaction categories for a wallet"""
    try:
        categories_doc = await db.transaction_categories.find_one(
            {
                "user_id": user["id"],
                "address": address.lower(),
                "chain": chain
            },
            {"_id": 0}
        )
        
        if categories_doc:
            return {
                "address": address,
                "chain": chain,
                "categories": categories_doc.get("categories", {}),
                "updated_at": categories_doc.get("updated_at")
            }
        
        return {
            "address": address,
            "chain": chain,
            "categories": {},
            "updated_at": None
        }
        
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch transaction categories")


@router.post("/batch-categorize")
async def batch_categorize_transactions(
    request: BatchCategoryRequest,
    user: dict = Depends(get_current_user)
):
    """Batch update transaction categories"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Transaction categorization is a Premium feature."
            )
        
        address = request.address.strip().lower()
        chain = request.chain.lower()
        categories = request.categories
        
        category_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "address": address,
            "chain": chain,
            "categories": categories,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.transaction_categories.update_one(
            {
                "user_id": user["id"],
                "address": address,
                "chain": chain
            },
            {"$set": category_doc},
            upsert=True
        )
        
        logger.info(f"Batch categorized {len(categories)} transactions for user {user['id']}")
        
        return {
            "message": "Transactions categorized successfully",
            "count": len(categories),
            "categories": categories
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error batch categorizing: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to batch categorize transactions")


@router.post("/auto-categorize")
async def auto_categorize_transactions(
    request: AutoCategorizeRequest,
    user: dict = Depends(get_current_user)
):
    """Auto-categorize transactions using smart detection (Premium/Pro)"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Auto categorization is a Premium feature."
            )
        
        address = request.address.strip()
        chain = request.chain.lower()
        
        analysis_data = multi_chain_service.analyze_wallet(
            address,
            chain=chain,
            user_tier=user_tier
        )
        
        transactions = analysis_data.get('recentTransactions', [])
        
        if not transactions:
            raise HTTPException(
                status_code=400,
                detail="No transactions found for this wallet."
            )
        
        categories = tax_report_service.auto_categorize_transactions(
            transactions=transactions,
            known_addresses=request.known_addresses
        )
        
        category_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "address": address.lower(),
            "chain": chain,
            "categories": categories,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.transaction_categories.update_one(
            {
                "user_id": user["id"],
                "address": address.lower(),
                "chain": chain
            },
            {"$set": category_doc},
            upsert=True
        )
        
        logger.info(f"Auto-categorized {len(categories)} transactions for user {user['id']}")
        
        return {
            "message": "Transactions auto-categorized successfully",
            "count": len(categories),
            "categories": categories
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error auto-categorizing: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to auto-categorize transactions")


@router.get("/supported-years")
async def get_supported_tax_years():
    """Get list of supported tax years for reports"""
    current_year = datetime.now().year
    return {
        "years": list(range(2020, current_year + 1)),
        "current_year": current_year
    }


@router.post("/unified")
async def get_unified_tax_data(
    request: UnifiedTaxRequest,
    user: dict = Depends(get_current_user)
):
    """Get unified tax data with flexible data source selection"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Unified tax calculation requires Unlimited subscription."
            )
        
        data_source = request.data_source
        wallet_transactions = []
        exchange_transactions = []
        current_balance = 0
        current_price = 0
        symbol = 'USD'
        address = request.address.lower() if request.address else None
        chain = request.chain
        
        if data_source in ["wallet_only", "combined"]:
            if not address:
                raise HTTPException(
                    status_code=400,
                    detail="Wallet address required for wallet_only or combined data source"
                )
            
            analysis_data = multi_chain_service.analyze_wallet(
                address=address,
                chain=chain,
                user_tier=user_tier
            )
            
            wallet_transactions = analysis_data.get('recentTransactions', [])
            current_balance = analysis_data.get('currentBalance', 0)
            current_price = analysis_data.get('current_price_usd', 0)
            symbol = {
                'ethereum': 'ETH',
                'bitcoin': 'BTC',
                'polygon': 'MATIC',
                'arbitrum': 'ETH',
                'bsc': 'BNB',
                'solana': 'SOL'
            }.get(chain, 'ETH')
        
        if data_source in ["exchange_only", "combined"]:
            exchange_txs = await db.exchange_transactions.find(
                {"user_id": user["id"]},
                {"_id": 0}
            ).to_list(5000)
            exchange_transactions = exchange_txs
            
            if data_source == "exchange_only" and exchange_transactions:
                assets = set(tx.get('asset', '') for tx in exchange_transactions)
                if len(assets) == 1:
                    symbol = list(assets)[0]
                else:
                    symbol = "MULTI"
        
        tax_data = unified_tax_service.calculate_unified_tax_data(
            wallet_transactions=wallet_transactions,
            exchange_transactions=exchange_transactions,
            symbol=symbol,
            current_price=current_price,
            current_balance=current_balance,
            asset_filter=request.asset_filter
        )
        
        if request.tax_year:
            tax_data['realized_gains'] = [
                g for g in tax_data['realized_gains']
                if g.get('sell_date', '').startswith(str(request.tax_year))
            ]
            tax_data['summary']['total_realized_gain'] = sum(
                g['gain_loss'] for g in tax_data['realized_gains']
            )
            tax_data['summary']['short_term_gains'] = sum(
                g['gain_loss'] for g in tax_data['realized_gains'] 
                if g['holding_period'] == 'short-term'
            )
            tax_data['summary']['long_term_gains'] = sum(
                g['gain_loss'] for g in tax_data['realized_gains'] 
                if g['holding_period'] == 'long-term'
            )
        
        assets_summary = unified_tax_service.get_assets_summary(
            wallet_transactions,
            exchange_transactions,
            symbol
        )
        
        return {
            "wallet_address": address,
            "chain": chain,
            "symbol": symbol,
            "current_price": current_price,
            "tax_year": request.tax_year,
            "data_source": data_source,
            "data_sources_used": {
                "wallet": len(wallet_transactions) > 0,
                "wallet_tx_count": len(wallet_transactions),
                "exchange": len(exchange_transactions) > 0,
                "exchange_tx_count": len(exchange_transactions)
            },
            "tax_data": tax_data,
            "assets_summary": assets_summary,
            "message": f"Tax data calculated using {data_source} source(s)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating unified tax: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate unified tax data: {str(e)}")


@router.post("/detect-transfers")
async def detect_wallet_exchange_transfers(
    request: UnifiedTaxRequest,
    user: dict = Depends(get_current_user)
):
    """Detect transfers between wallet and exchange"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Transfer detection requires Unlimited subscription."
            )
        
        address = request.address.lower() if request.address else None
        chain = request.chain
        
        if not address:
            raise HTTPException(status_code=400, detail="Wallet address required")
        
        analysis_data = multi_chain_service.analyze_wallet(
            address=address,
            chain=chain,
            user_tier=user_tier
        )
        
        wallet_transactions = analysis_data.get('recentTransactions', [])
        symbol = {
            'ethereum': 'ETH',
            'bitcoin': 'BTC',
            'polygon': 'MATIC',
            'arbitrum': 'ETH',
            'bsc': 'BNB',
            'solana': 'SOL'
        }.get(chain, 'ETH')
        
        exchange_txs = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(5000)
        
        normalized_wallet = []
        for tx in wallet_transactions:
            normalized_wallet.append(unified_tax_service.normalize_wallet_transaction(tx, symbol))
        
        normalized_exchange = []
        for tx in exchange_txs:
            normalized_exchange.append(unified_tax_service.normalize_exchange_transaction(tx))
        
        detected = unified_tax_service.detect_transfers_between_sources(
            normalized_wallet, 
            normalized_exchange,
            tolerance_hours=48
        )
        
        return {
            "wallet_address": address,
            "chain": chain,
            "symbol": symbol,
            "transfers_detected": len(detected),
            "transfers": detected,
            "message": f"Found {len(detected)} potential transfers from wallet to exchange"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting transfers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to detect transfers: {str(e)}")


@router.get("/unified/assets")
async def get_unified_assets_summary(user: dict = Depends(get_current_user)):
    """Get summary of all assets across wallet analyses and exchange imports"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Asset summary requires Unlimited subscription."
            )
        
        exchange_txs = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(5000)
        
        assets = {}
        for tx in exchange_txs:
            asset = tx.get('asset', 'UNKNOWN')
            if asset not in assets:
                assets[asset] = {
                    'asset': asset,
                    'exchange_txs': 0,
                    'total_bought': 0,
                    'total_sold': 0,
                    'exchanges': set()
                }
            
            assets[asset]['exchange_txs'] += 1
            assets[asset]['exchanges'].add(tx.get('exchange', 'unknown'))
            
            amount = float(tx.get('amount', 0))
            tx_type = tx.get('tx_type', '').lower()
            if tx_type in ['buy', 'receive', 'deposit', 'reward']:
                assets[asset]['total_bought'] += amount
            elif tx_type in ['sell', 'send', 'withdrawal']:
                assets[asset]['total_sold'] += amount
        
        for asset in assets.values():
            asset['exchanges'] = list(asset['exchanges'])
            asset['net_position'] = asset['total_bought'] - asset['total_sold']
        
        return {
            "assets": list(assets.values()),
            "total_assets": len(assets),
            "total_exchange_txs": len(exchange_txs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assets summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get assets summary")
