"""
Core Custody Routes

Handles chain of custody analysis, PDF reports, wallet linkages, and Form 8949 export.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import uuid
import io
import os
import logging

from .dependencies import db, get_current_user, require_unlimited_tier
from .models import CustodyAnalysisRequest
from custody_service import custody_service, KNOWN_EXCHANGE_ADDRESSES, KNOWN_DEX_ADDRESSES
from custody_report_generator import custody_report_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/custody", tags=["Chain of Custody"])


@router.post("/analyze")
async def analyze_chain_of_custody(
    request: CustodyAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """Analyze chain of custody for a wallet address (Unlimited tier)"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="Chain of Custody analysis requires Unlimited subscription."
            )
        
        address = request.address.strip()
        chain = request.chain.lower()
        
        # Validate address format based on chain
        evm_chains = ['ethereum', 'polygon', 'arbitrum', 'bsc', 'base', 'optimism']
        
        if chain in evm_chains:
            address = address.lower()
            if not address.startswith('0x') or len(address) != 42:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid EVM address format. Must start with 0x and be 42 characters."
                )
        
        result = await custody_service.analyze_chain_of_custody(
            address=address,
            chain=chain,
            depth=request.depth,
            db=db
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Custody analysis error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/history")
async def get_custody_history(
    user: dict = Depends(get_current_user)
):
    """Get custody analysis history for the user"""
    try:
        history = await db.custody_analyses.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("timestamp", -1).limit(20).to_list(20)
        
        return {"success": True, "history": history}
        
    except Exception as e:
        logger.error(f"Error getting custody history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/known-addresses")
async def get_known_addresses():
    """Get known exchange and DEX addresses for reference"""
    return {
        "success": True,
        "exchanges": KNOWN_EXCHANGE_ADDRESSES,
        "dexes": KNOWN_DEX_ADDRESSES
    }


@router.post("/export-pdf")
async def export_custody_pdf(
    request: CustodyAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """Export custody analysis as PDF"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="PDF export requires Unlimited subscription."
            )
        
        # Run analysis
        result = await custody_service.analyze_chain_of_custody(
            address=request.address.strip(),
            chain=request.chain.lower(),
            depth=request.depth,
            db=db
        )
        
        # Generate PDF
        pdf_bytes = await custody_report_generator.generate_pdf_report(result)
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=custody_report_{request.address[:10]}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF export error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF export failed: {str(e)}")


@router.post("/link-wallet")
async def link_wallet(
    user: dict = Depends(get_current_user),
    from_address: str = None,
    to_address: str = None,
    confidence: float = 1.0
):
    """Create a user-confirmed wallet linkage"""
    try:
        if not from_address or not to_address:
            raise HTTPException(status_code=400, detail="Both from_address and to_address required")
        
        from linkage_engine_service import linkage_engine
        
        result = await linkage_engine.create_user_confirmed_link(
            user_id=user["id"],
            from_address=from_address,
            to_address=to_address,
            db=db,
            confidence=confidence
        )
        
        # Mark pending recompute
        from recompute_service import RecomputeService, RecomputeTrigger
        recompute = RecomputeService(db)
        await recompute.mark_pending_recompute(
            user["id"],
            RecomputeTrigger.LINKAGE_CHANGE,
            {"link_created": f"{from_address}->{to_address}"}
        )
        
        return {"success": True, "linkage": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error linking wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to link wallet: {str(e)}")


@router.delete("/unlink-wallet/{edge_id}")
async def unlink_wallet(
    edge_id: str,
    user: dict = Depends(get_current_user)
):
    """Remove a wallet linkage"""
    try:
        result = await db.linkage_edges.delete_one({
            "edge_id": edge_id,
            "user_id": user["id"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Linkage not found")
        
        # Mark pending recompute
        from recompute_service import RecomputeService, RecomputeTrigger
        recompute = RecomputeService(db)
        await recompute.mark_pending_recompute(
            user["id"],
            RecomputeTrigger.LINKAGE_CHANGE,
            {"link_deleted": edge_id}
        )
        
        return {"success": True, "deleted": edge_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlinking wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to unlink: {str(e)}")


@router.get("/linkages")
async def get_wallet_linkages(
    user: dict = Depends(get_current_user)
):
    """Get all wallet linkages for the user"""
    try:
        linkages = await db.linkage_edges.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(10000)
        
        return {"success": True, "linkages": linkages}
        
    except Exception as e:
        logger.error(f"Error getting linkages: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clusters")
async def get_wallet_clusters(
    user: dict = Depends(get_current_user)
):
    """Get wallet clusters (groups of linked wallets)"""
    try:
        from linkage_engine_service import linkage_engine
        
        clusters = await linkage_engine.get_user_wallet_clusters(
            user_id=user["id"],
            db=db
        )
        
        return {"success": True, "clusters": clusters}
        
    except Exception as e:
        logger.error(f"Error getting clusters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect-breaks")
async def detect_chain_breaks(
    user: dict = Depends(get_current_user)
):
    """Detect chain of custody breaks (unlinked transfers)"""
    try:
        from linkage_engine_service import linkage_engine
        
        breaks = await linkage_engine.detect_chain_breaks(
            user_id=user["id"],
            db=db
        )
        
        return {"success": True, "chain_breaks": breaks}
        
    except Exception as e:
        logger.error(f"Error detecting breaks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# === FORM 8949 EXPORT ===

@router.get("/export-form-8949")
async def export_form_8949(
    user: dict = Depends(get_current_user),
    tax_year: Optional[int] = None,
    format: str = "csv",
    force: bool = False
):
    """
    Export Form 8949 data.
    
    Uses Export Safety Guard to ensure validation passes.
    Set force=True to bypass validation (not recommended).
    """
    try:
        from export_safety_guard import ExportSafetyGuard
        guard = ExportSafetyGuard(db)
        
        # Use safe export
        result = await guard.safe_export(
            user_id=user["id"],
            tax_year=tax_year,
            force=force
        )
        
        if not result["success"]:
            return {
                "success": False,
                "blocked": True,
                "error": result.get("error", {}),
                "message": "Export blocked - validation failed"
            }
        
        # Format response
        if format == "csv":
            import csv
            import io
            
            output = io.StringIO()
            if result["data"]:
                writer = csv.DictWriter(output, fieldnames=result["data"][0].keys())
                writer.writeheader()
                writer.writerows(result["data"])
            
            return StreamingResponse(
                io.BytesIO(output.getvalue().encode()),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f"attachment; filename=form_8949_{tax_year or 'all'}.csv"
                }
            )
        else:
            return {
                "success": True,
                "summary": result["summary"],
                "data": result["data"]
            }
        
    except Exception as e:
        logger.error(f"Error exporting Form 8949: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@router.get("/tax-events")
async def get_tax_events(
    user: dict = Depends(get_current_user),
    tax_year: Optional[int] = None
):
    """Get all tax events for the user"""
    try:
        from exchange_tax_service import exchange_tax_service
        
        events = await exchange_tax_service.calculate_tax_events(
            user_id=user["id"],
            db=db
        )
        
        # Filter by tax year if specified
        if tax_year:
            events = [
                e for e in events 
                if str(e.get("timestamp", "")).startswith(str(tax_year))
            ]
        
        return {
            "success": True,
            "count": len(events),
            "events": events
        }
        
    except Exception as e:
        logger.error(f"Error getting tax events: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# === TAX LOTS ===

class CreateTaxLotRequest(BaseModel):
    """Request model for creating tax lot"""
    asset: str
    quantity: float
    cost_basis: float
    acquisition_date: str
    acquisition_type: str = "manual"


@router.post("/tax-lots/create")
async def create_tax_lot(
    request: CreateTaxLotRequest,
    user: dict = Depends(get_current_user)
):
    """Manually create a tax lot"""
    try:
        lot = {
            "lot_id": str(uuid.uuid4()),
            "user_id": user["id"],
            "source_tx_id": f"manual_{uuid.uuid4()}",
            "asset": request.asset.upper(),
            "original_quantity": request.quantity,
            "remaining_quantity": request.quantity,
            "cost_basis": request.cost_basis,
            "cost_per_unit": request.cost_basis / request.quantity if request.quantity > 0 else 0,
            "acquisition_date": request.acquisition_date,
            "acquisition_type": request.acquisition_type,
            "manual": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.tax_lots.insert_one(lot)
        
        # Mark pending recompute
        from recompute_service import RecomputeService, RecomputeTrigger
        recompute = RecomputeService(db)
        await recompute.mark_pending_recompute(
            user["id"],
            RecomputeTrigger.CLASSIFICATION_CHANGE,
            {"lot_created": lot["lot_id"]}
        )
        
        return {"success": True, "lot": {k: v for k, v in lot.items() if k != "_id"}}
        
    except Exception as e:
        logger.error(f"Error creating tax lot: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tax-lots")
async def get_tax_lots(
    user: dict = Depends(get_current_user),
    asset: Optional[str] = None
):
    """Get all tax lots for the user"""
    try:
        query = {"user_id": user["id"]}
        if asset:
            query["asset"] = asset.upper()
        
        lots = await db.tax_lots.find(query, {"_id": 0}).to_list(100000)
        
        return {
            "success": True,
            "count": len(lots),
            "lots": lots
        }
        
    except Exception as e:
        logger.error(f"Error getting tax lots: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tax-lots/balances")
async def get_tax_lot_balances(
    user: dict = Depends(get_current_user)
):
    """Get aggregated tax lot balances by asset"""
    try:
        pipeline = [
            {"$match": {"user_id": user["id"]}},
            {"$group": {
                "_id": "$asset",
                "total_remaining": {"$sum": "$remaining_quantity"},
                "total_cost_basis": {"$sum": {"$multiply": ["$remaining_quantity", "$cost_per_unit"]}},
                "lot_count": {"$sum": 1}
            }},
            {"$sort": {"_id": 1}}
        ]
        
        balances = await db.tax_lots.aggregate(pipeline).to_list(1000)
        
        return {
            "success": True,
            "balances": [
                {
                    "asset": b["_id"],
                    "remaining_quantity": round(b["total_remaining"], 8),
                    "total_cost_basis": round(b["total_cost_basis"], 2),
                    "lot_count": b["lot_count"]
                }
                for b in balances
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting balances: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tax-lots/recompute")
async def recompute_tax_lots(
    user: dict = Depends(get_current_user)
):
    """Trigger full recompute of tax lots and disposals"""
    try:
        from recompute_service import RecomputeService, RecomputeTrigger
        service = RecomputeService(db)
        
        result = await service.full_recompute(
            user_id=user["id"],
            trigger=RecomputeTrigger.MANUAL_REQUEST
        )
        
        return {
            "success": True,
            "recompute": result
        }
        
    except Exception as e:
        logger.error(f"Error recomputing tax lots: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
