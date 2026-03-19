"""Wallet routes - analyze, export, history, saved wallets"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List
from datetime import datetime, timezone
import logging

from .dependencies import db, get_current_user, check_usage_limit
from .models import (
    WalletAnalysisRequest, WalletAnalysisResponse, 
    SavedWallet, SavedWalletCreate, ChainRequest
)
from multi_chain_service import MultiChainService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Wallets"])

multi_chain_service = MultiChainService()


@router.post("/wallet/analyze", response_model=WalletAnalysisResponse)
async def analyze_wallet(request: WalletAnalysisRequest, user: dict = Depends(check_usage_limit)):
    """Analyze a crypto wallet across multiple blockchains (requires authentication)"""
    try:
        address = request.address.strip()
        chain = request.chain.lower()
        
        user_tier = user.get('subscription_tier', 'free')
        if chain != 'ethereum' and user_tier == 'free':
            raise HTTPException(
                status_code=403, 
                detail="Multi-chain analysis is a Premium feature. Upgrade to analyze 10+ chains including Bitcoin, Solana, Algorand, Avalanche, and Dogecoin."
            )
        
        if chain in ["ethereum", "arbitrum", "bsc", "polygon"]:
            if not address.startswith('0x') or len(address) != 42:
                raise HTTPException(status_code=400, detail=f"Invalid {chain} address format")
        elif chain == "bitcoin":
            if len(address) < 26 or len(address) > 62:
                raise HTTPException(status_code=400, detail="Invalid Bitcoin address format")
        elif chain == "solana":
            if len(address) < 32 or len(address) > 44:
                raise HTTPException(status_code=400, detail="Invalid Solana address format")
        
        analysis_data = multi_chain_service.analyze_wallet(
            address, 
            chain=chain,
            start_date=request.start_date,
            end_date=request.end_date,
            user_tier=user.get('subscription_tier', 'free')
        )
        
        all_transactions = analysis_data['recentTransactions']
        display_transactions = sorted(
            all_transactions, 
            key=lambda x: x.get('blockTime') or x.get('timestamp') or 0, 
            reverse=True
        )[:100]
        
        analysis_response = WalletAnalysisResponse(
            address=analysis_data['address'],
            chain=analysis_data.get('chain'),
            totalEthSent=analysis_data['totalEthSent'],
            totalEthReceived=analysis_data['totalEthReceived'],
            totalGasFees=analysis_data['totalGasFees'],
            currentBalance=analysis_data.get('currentBalance', analysis_data['netEth']),
            netEth=analysis_data['netEth'],
            netFlow=analysis_data.get('netFlow', analysis_data['netEth']),
            outgoingTransactionCount=analysis_data['outgoingTransactionCount'],
            incomingTransactionCount=analysis_data['incomingTransactionCount'],
            tokensSent=analysis_data['tokensSent'],
            tokensReceived=analysis_data['tokensReceived'],
            recentTransactions=display_transactions,
            total_transaction_count=len(all_transactions),
            current_price_usd=analysis_data.get('current_price_usd'),
            total_value_usd=analysis_data.get('total_value_usd'),
            total_received_usd=analysis_data.get('total_received_usd'),
            total_sent_usd=analysis_data.get('total_sent_usd'),
            total_gas_fees_usd=analysis_data.get('total_gas_fees_usd'),
            tax_data=analysis_data.get('tax_data'),
            exchange_deposit_warning=analysis_data.get('exchange_deposit_warning')
        )
        
        doc = analysis_response.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        doc['user_id'] = user['id']
        if doc.get('tax_data'):
            doc['tax_data'].pop('all_transactions', None)
            doc['tax_data'].pop('enriched_transactions', None)
            doc['tax_data'].pop('realized_gains', None)
            doc['tax_data'].pop('remaining_lots', None)
        await db.wallet_analyses.insert_one(doc)
        
        await db.users.update_one(
            {"id": user["id"]},
            {"$inc": {"daily_usage_count": 1, "analysis_count": 1}}
        )
        
        return analysis_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze wallet: {str(e)}")


@router.post("/wallet/analyze-all")
async def analyze_all_chains(request: WalletAnalysisRequest, user: dict = Depends(check_usage_limit)):
    """Analyze wallet across all supported chains (Unlimited feature)"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro']:
            raise HTTPException(
                status_code=403, 
                detail="Scan All Chains is a Premium feature. Upgrade to analyze your MetaMask wallet across all EVM blockchains simultaneously."
            )
        
        address = request.address.strip()
        
        evm_chains = ['ethereum', 'polygon', 'arbitrum', 'bsc']
        
        chains_to_analyze = []
        
        if address.startswith('0x') and len(address) == 42:
            chains_to_analyze.extend(evm_chains)
        
        if not chains_to_analyze:
            raise HTTPException(
                status_code=400,
                detail="Address format not recognized. Currently supporting EVM addresses (0x...) for multi-chain analysis."
            )
        
        import asyncio
        
        async def analyze_single_chain(chain: str):
            try:
                return {
                    'chain': chain,
                    'success': True,
                    'data': multi_chain_service.analyze_wallet(
                        address, 
                        chain=chain,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        user_tier=user.get('subscription_tier', 'free')
                    )
                }
            except Exception as e:
                logger.error(f"Error analyzing {chain}: {str(e)}")
                return {
                    'chain': chain,
                    'success': False,
                    'error': str(e)
                }
        
        results = await asyncio.gather(
            *[analyze_single_chain(chain) for chain in chains_to_analyze],
            return_exceptions=True
        )
        
        successful_analyses = []
        failed_chains = []
        
        total_value = 0.0
        total_gas_fees = 0.0
        total_transactions = 0
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Chain analysis failed with exception: {str(result)}")
                continue
                
            if result['success']:
                data = result['data']
                successful_analyses.append({
                    'chain': result['chain'],
                    'totalSent': data['totalEthSent'],
                    'totalReceived': data['totalEthReceived'],
                    'netBalance': data['netEth'],
                    'gasFees': data['totalGasFees'],
                    'transactionCount': data['outgoingTransactionCount'] + data['incomingTransactionCount'],
                    'tokensCount': len(data.get('tokensSent', {})) + len(data.get('tokensReceived', {}))
                })
                
                total_value += abs(data['totalEthReceived'])
                total_gas_fees += data['totalGasFees']
                total_transactions += data['outgoingTransactionCount'] + data['incomingTransactionCount']
            else:
                failed_chains.append({
                    'chain': result['chain'],
                    'error': result.get('error', 'Unknown error')
                })
        
        if not successful_analyses:
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze any chains. Please try again."
            )
        
        await db.users.update_one(
            {"id": user["id"]},
            {"$inc": {"daily_usage_count": 1}}
        )
        
        return {
            'address': address,
            'chains_analyzed': len(successful_analyses),
            'total_chains': len(chains_to_analyze),
            'results': successful_analyses,
            'failed_chains': failed_chains,
            'aggregated': {
                'total_value': total_value,
                'total_gas_fees': total_gas_fees,
                'total_transactions': total_transactions
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in multi-chain analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Multi-chain analysis failed: {str(e)}")


@router.post("/wallet/export-paginated")
async def export_wallet_paginated(
    request: WalletAnalysisRequest, 
    page: int = 1,
    page_size: int = 1000,
    user: dict = Depends(get_current_user)
):
    """Export wallet transactions in paginated batches (Premium/Pro feature)"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403, 
                detail="CSV Export is a Premium feature. Upgrade to download your transaction history."
            )
        
        address = request.address.strip()
        chain = request.chain.lower()
        
        if chain != 'ethereum' and user_tier == 'free':
            raise HTTPException(status_code=403, detail="Multi-chain export requires Premium")
        
        analysis_data = multi_chain_service.analyze_wallet(
            address, 
            chain=chain,
            start_date=request.start_date,
            end_date=request.end_date,
            user_tier=user.get('subscription_tier', 'free')
        )
        
        total_transactions = analysis_data.get('totalTransactionCount', 0)
        total_pages = (total_transactions + page_size - 1) // page_size
        
        return {
            'address': analysis_data['address'],
            'chain': chain,
            'page': page,
            'page_size': page_size,
            'total_transactions': total_transactions,
            'total_pages': total_pages,
            'has_more': page < total_pages,
            'transactions': analysis_data['recentTransactions'],
            'summary': {
                'totalEthSent': analysis_data['totalEthSent'],
                'totalEthReceived': analysis_data['totalEthReceived'],
                'totalGasFees': analysis_data['totalGasFees'],
                'netEth': analysis_data['netEth']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export wallet: {str(e)}")


@router.get("/wallet/history", response_model=List[WalletAnalysisResponse])
async def get_wallet_history(limit: int = 10):
    """Get wallet analysis history"""
    try:
        analyses = await db.wallet_analyses.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
        
        for analysis in analyses:
            if isinstance(analysis['timestamp'], str):
                analysis['timestamp'] = datetime.fromisoformat(analysis['timestamp'])
        
        return analyses
    except Exception as e:
        logger.error(f"Error fetching wallet history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch wallet history")


@router.get("/chains/supported")
async def get_supported_chains():
    """Get list of supported blockchain networks"""
    try:
        chains = multi_chain_service.get_supported_chains()
        return {"chains": chains}
    except Exception as e:
        logger.error(f"Error fetching supported chains: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch supported chains")


@router.post("/chains/request")
async def request_chain(
    request: ChainRequest,
    user: dict = Depends(get_current_user)
):
    """Request a new blockchain to be added (Unlimited users only)"""
    try:
        if user.get('subscription_tier') == 'free':
            raise HTTPException(
                status_code=403,
                detail="Chain requests are available for Unlimited users only. Upgrade to request new chains."
            )
        
        chain_request = {
            "user_id": user["id"],
            "user_email": user.get("email", ""),
            "chain_name": request.chain_name,
            "chain_symbol": request.chain_symbol,
            "reason": request.reason,
            "sample_address": request.sample_address,
            "status": "pending",
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.chain_requests.insert_one(chain_request)
        
        logger.info(f"Chain request received: {request.chain_name} from user {user.get('email')}")
        
        return {
            "message": f"Thank you! Your request for {request.chain_name} has been submitted.",
            "chain_name": request.chain_name,
            "status": "pending",
            "estimated_response": "48 hours",
            "note": "We'll notify you by email when the chain is added."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting chain request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit chain request")


@router.get("/chains/requests")
async def get_my_chain_requests(user: dict = Depends(get_current_user)):
    """Get user's chain requests and their status"""
    try:
        requests = await db.chain_requests.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("created_at", -1).to_list(20)
        
        return {"requests": requests}
    except Exception as e:
        logger.error(f"Error fetching chain requests: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch chain requests")


@router.post("/wallets/save")
async def save_wallet(
    wallet_data: SavedWalletCreate,
    user: dict = Depends(get_current_user)
):
    """Save a wallet for quick access"""
    try:
        existing = await db.saved_wallets.find_one({
            "user_id": user["id"],
            "address": wallet_data.address.lower(),
            "chain": wallet_data.chain
        })
        
        if existing:
            raise HTTPException(status_code=400, detail="Wallet already saved")
        
        saved_wallet = SavedWallet(
            user_id=user["id"],
            address=wallet_data.address.lower(),
            nickname=wallet_data.nickname,
            chain=wallet_data.chain
        )
        
        doc = saved_wallet.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.saved_wallets.insert_one(doc)
        
        return {"message": "Wallet saved successfully", "wallet": saved_wallet}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving wallet: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save wallet")


@router.get("/wallets/saved")
async def get_saved_wallets(user: dict = Depends(get_current_user)):
    """Get all saved wallets for current user"""
    try:
        wallets = await db.saved_wallets.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(100)
        
        return {"wallets": wallets}
    except Exception as e:
        logger.error(f"Error fetching saved wallets: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch saved wallets")


@router.delete("/wallets/saved/{wallet_id}")
async def delete_saved_wallet(
    wallet_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a saved wallet"""
    try:
        result = await db.saved_wallets.delete_one({
            "id": wallet_id,
            "user_id": user["id"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        return {"message": "Wallet deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting wallet: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete wallet")
