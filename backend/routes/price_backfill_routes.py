"""
Price Backfill Routes

Handles historical price backfill for disposals missing USD valuation.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import logging

from .dependencies import db, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/custody", tags=["Price Backfill"])


class PriceBackfillRequest(BaseModel):
    """Request model for price backfill"""
    tx_ids: Optional[List[str]] = None
    dry_run: bool = True
    allow_approximate: bool = True


class BackfillRollbackRequest(BaseModel):
    """Request model for backfill rollback"""
    batch_id: str


@router.get("/price-backfill/preview")
async def preview_price_backfill(
    user: dict = Depends(get_current_user)
):
    """
    Preview price backfill for disposals missing USD valuation.
    
    Returns:
    - Total disposals missing price
    - Successfully backfillable (exact + approximate)
    - Still missing (no price data available)
    - Breakdown by valuation status, source, and asset
    """
    try:
        from price_backfill_service import PriceBackfillService
        service = PriceBackfillService(db)
        
        summary = await service.preview_backfill(user["id"])
        
        return {
            "success": True,
            "summary": {
                "total_missing": summary.total_missing,
                "successfully_backfillable": summary.successfully_backfilled,
                "still_missing": summary.still_missing,
                "exact_matches": summary.exact_matches,
                "approximate_matches": summary.approximate_matches
            },
            "by_status": summary.by_status,
            "by_source": summary.by_source,
            "by_asset": summary.by_asset,
            "results": [r.to_dict() for r in summary.results[:100]]
        }
        
    except Exception as e:
        logger.error(f"Error previewing price backfill: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to preview: {str(e)}")


@router.post("/price-backfill/apply")
async def apply_price_backfill(
    request: PriceBackfillRequest,
    user: dict = Depends(get_current_user)
):
    """
    Apply price backfill to disposals missing USD valuation.
    
    For each disposal:
    1. Fetches historical USD price at or nearest to timestamp
    2. Stores: asset, timestamp_used, price_source, confidence
    3. Marks valuation as: exact, approximate, or unavailable
    4. Creates audit trail entry
    """
    try:
        from price_backfill_service import PriceBackfillService
        service = PriceBackfillService(db)
        
        results = await service.apply_backfill(
            user_id=user["id"],
            tx_ids=request.tx_ids,
            dry_run=request.dry_run,
            allow_approximate=request.allow_approximate
        )
        
        # Mark pending recompute if not dry run
        if not request.dry_run and results.get("applied_count", 0) > 0:
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.PRICE_BACKFILL,
                {"backfilled_count": results["applied_count"]}
            )
        
        return {
            "success": True,
            "dry_run": results["dry_run"],
            "total_processed": results["total_processed"],
            "backfillable_count": results["backfillable_count"],
            "applied_count": results["applied_count"],
            "still_missing": results["still_missing"],
            "backfill_batch_id": results.get("backfill_batch_id"),
            "applied_records": results.get("applied_records", [])[:50],
            "preview": results.get("preview", [])[:50]
        }
        
    except Exception as e:
        logger.error(f"Error applying price backfill: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")


@router.post("/price-backfill/rollback")
async def rollback_price_backfill(
    request: BackfillRollbackRequest,
    user: dict = Depends(get_current_user)
):
    """
    Rollback a batch of price backfills.
    
    Removes price data backfilled in the specified batch.
    """
    try:
        from price_backfill_service import PriceBackfillService
        service = PriceBackfillService(db)
        
        results = await service.rollback_backfill(
            user_id=user["id"],
            batch_id=request.batch_id
        )
        
        if not results["success"]:
            raise HTTPException(status_code=404, detail=results["message"])
        
        # Mark pending recompute
        from recompute_service import RecomputeService, RecomputeTrigger
        recompute = RecomputeService(db)
        await recompute.mark_pending_recompute(
            user["id"],
            RecomputeTrigger.ROLLBACK,
            {"backfill_batch_id": request.batch_id}
        )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rolling back price backfill: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")


@router.get("/price-backfill/batches")
async def list_backfill_batches(
    user: dict = Depends(get_current_user)
):
    """List all price backfill batches for the user"""
    try:
        from price_backfill_service import PriceBackfillService
        service = PriceBackfillService(db)
        
        batches = await service.list_backfill_batches(user["id"])
        
        return {
            "success": True,
            "batches": batches
        }
        
    except Exception as e:
        logger.error(f"Error listing backfill batches: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list batches: {str(e)}")
