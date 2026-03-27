"""
Proceeds Acquisition Routes

Handles constrained proceeds acquisition and staged application.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import logging

from .dependencies import db, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/custody", tags=["Proceeds Acquisition"])


class ProceedsRemediationRequest(BaseModel):
    """Request model for proceeds acquisition remediation"""
    candidate_tx_ids: Optional[List[str]] = None
    dry_run: bool = True


class RollbackRequest(BaseModel):
    """Request model for rollback"""
    batch_id: str


class StagedApplyRequest(BaseModel):
    """Request model for staged proceeds application"""
    assets: Optional[List[str]] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    valuation_filter: str = "exact_only"
    min_confidence: float = 0.7
    max_time_delta_hours: Optional[float] = None
    exclude_wide_window: bool = True
    dry_run: bool = True
    force_override: bool = False


# === CONSTRAINED PROCEEDS ROUTES ===

@router.get("/proceeds/preview")
async def preview_proceeds_candidates(
    user: dict = Depends(get_current_user)
):
    """Preview all candidate proceeds acquisitions before applying"""
    try:
        from constrained_proceeds_service import ConstrainedProceedsService
        service = ConstrainedProceedsService(db)
        
        summary = await service.preview_candidates(user["id"])
        
        return {
            "success": True,
            "preview": summary.to_dict(),
            "summary": {
                "fixable_count": summary.fixable_count,
                "fixable_total_value": round(summary.fixable_total_value, 2),
                "non_fixable_count": summary.non_fixable_count,
                "non_fixable_reasons": summary.non_fixable_by_reason
            }
        }
        
    except Exception as e:
        logger.error(f"Error previewing proceeds candidates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to preview: {str(e)}")


@router.post("/proceeds/apply")
async def apply_proceeds_acquisitions(
    request: ProceedsRemediationRequest,
    user: dict = Depends(get_current_user)
):
    """Apply constrained proceeds acquisition fixes"""
    try:
        from constrained_proceeds_service import ConstrainedProceedsService
        service = ConstrainedProceedsService(db)
        
        results = await service.apply_fixes(
            user_id=user["id"],
            candidate_tx_ids=request.candidate_tx_ids,
            dry_run=request.dry_run
        )
        
        # Mark pending recompute if not dry run
        if not request.dry_run and results.get("created_count", 0) > 0:
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.PROCEEDS_APPLICATION,
                {"created_count": results["created_count"]}
            )
        
        return {
            "success": True,
            "dry_run": results["dry_run"],
            "created_count": results["created_count"],
            "total_value": round(results["total_value"], 2),
            "rollback_batch_id": results.get("rollback_batch_id"),
            "created_records": results.get("created_records", []),
            "preview": results.get("preview", [])
        }
        
    except Exception as e:
        logger.error(f"Error applying proceeds acquisitions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")


@router.post("/proceeds/rollback")
async def rollback_proceeds_batch(
    request: RollbackRequest,
    user: dict = Depends(get_current_user)
):
    """Rollback a batch of created proceeds acquisitions"""
    try:
        from constrained_proceeds_service import ConstrainedProceedsService
        service = ConstrainedProceedsService(db)
        
        results = await service.rollback_batch(
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
            {"batch_id": request.batch_id}
        )
        
        return results
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rolling back proceeds batch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")


@router.get("/proceeds/rollback-batches")
async def list_rollback_batches(
    user: dict = Depends(get_current_user)
):
    """List all rollback batches for the user"""
    try:
        from constrained_proceeds_service import ConstrainedProceedsService
        service = ConstrainedProceedsService(db)
        
        batches = await service.list_rollback_batches(user["id"])
        
        return {
            "success": True,
            "batches": batches
        }
        
    except Exception as e:
        logger.error(f"Error listing rollback batches: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list batches: {str(e)}")


# === STAGED APPLICATION ROUTES ===

@router.get("/proceeds/staged/stages")
async def get_application_stages(
    user: dict = Depends(get_current_user)
):
    """Get recommended application stages for proceeds acquisitions"""
    try:
        from staged_proceeds_service import StagedProceedsService
        service = StagedProceedsService(db)
        
        stages = await service.get_application_stages(user["id"])
        
        return {
            "success": True,
            "stages": stages
        }
        
    except Exception as e:
        logger.error(f"Error getting application stages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stages: {str(e)}")


@router.get("/proceeds/staged/preview")
async def preview_staged_application(
    user: dict = Depends(get_current_user),
    assets: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    valuation_filter: str = "exact_only",
    min_confidence: float = 0.7
):
    """Preview staged proceeds application with filters"""
    try:
        from staged_proceeds_service import StagedProceedsService, StagedApplicationFilters, ValuationFilter
        
        # Parse assets
        asset_list = [a.strip().upper() for a in assets.split(",")] if assets else None
        
        # Parse valuation filter
        try:
            val_filter = ValuationFilter(valuation_filter)
        except ValueError:
            val_filter = ValuationFilter.EXACT_ONLY
        
        filters = StagedApplicationFilters(
            assets=asset_list,
            date_from=date_from,
            date_to=date_to,
            valuation_filter=val_filter,
            min_confidence=min_confidence
        )
        
        service = StagedProceedsService(db)
        preview = await service.preview_staged(user["id"], filters)
        
        return {
            "success": True,
            "preview": preview
        }
        
    except Exception as e:
        logger.error(f"Error previewing staged application: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to preview: {str(e)}")


@router.post("/proceeds/staged/apply")
async def apply_staged_proceeds(
    request: StagedApplyRequest,
    user: dict = Depends(get_current_user)
):
    """Apply proceeds acquisitions with staged controls"""
    try:
        from staged_proceeds_service import StagedProceedsService, StagedApplicationFilters, ValuationFilter
        
        # Parse valuation filter
        try:
            val_filter = ValuationFilter(request.valuation_filter)
        except ValueError:
            val_filter = ValuationFilter.EXACT_ONLY
        
        filters = StagedApplicationFilters(
            assets=request.assets,
            date_from=request.date_from,
            date_to=request.date_to,
            valuation_filter=val_filter,
            min_confidence=request.min_confidence,
            max_time_delta_hours=request.max_time_delta_hours,
            exclude_wide_window=request.exclude_wide_window
        )
        
        service = StagedProceedsService(db)
        result = await service.apply_staged(
            user_id=user["id"],
            filters=filters,
            dry_run=request.dry_run,
            force_override=request.force_override
        )
        
        # Mark pending recompute if not dry run
        if not request.dry_run and result.candidates_applied > 0:
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.PROCEEDS_APPLICATION,
                {"staged_applied": result.candidates_applied}
            )
        
        return {
            "success": True,
            "result": result.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Error applying staged proceeds: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")


@router.post("/proceeds/staged/apply-exact")
async def apply_exact_only(
    user: dict = Depends(get_current_user),
    assets: Optional[str] = None,
    dry_run: bool = True
):
    """Convenience endpoint: Apply only exact-valuation candidates"""
    try:
        from staged_proceeds_service import StagedProceedsService
        
        asset_list = [a.strip().upper() for a in assets.split(",")] if assets else None
        
        service = StagedProceedsService(db)
        result = await service.apply_exact_only(
            user_id=user["id"],
            assets=asset_list,
            dry_run=dry_run
        )
        
        # Mark pending recompute if not dry run
        if not dry_run and result.candidates_applied > 0:
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.PROCEEDS_APPLICATION,
                {"exact_applied": result.candidates_applied}
            )
        
        return {
            "success": True,
            "result": result.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Error applying exact-only proceeds: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")


@router.post("/proceeds/staged/apply-stablecoins")
async def apply_stablecoins_only(
    user: dict = Depends(get_current_user),
    dry_run: bool = True
):
    """Convenience endpoint: Apply only stablecoin candidates"""
    try:
        from staged_proceeds_service import StagedProceedsService
        
        service = StagedProceedsService(db)
        result = await service.apply_stablecoins_only(
            user_id=user["id"],
            dry_run=dry_run
        )
        
        # Mark pending recompute if not dry run
        if not dry_run and result.candidates_applied > 0:
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.PROCEEDS_APPLICATION,
                {"stablecoin_applied": result.candidates_applied}
            )
        
        return {
            "success": True,
            "result": result.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Error applying stablecoin proceeds: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")


@router.post("/proceeds/staged/apply-high-confidence")
async def apply_high_confidence(
    user: dict = Depends(get_current_user),
    assets: Optional[str] = None,
    dry_run: bool = True
):
    """Convenience endpoint: Apply exact + high-confidence approximate"""
    try:
        from staged_proceeds_service import StagedProceedsService
        
        asset_list = [a.strip().upper() for a in assets.split(",")] if assets else None
        
        service = StagedProceedsService(db)
        result = await service.apply_high_confidence(
            user_id=user["id"],
            assets=asset_list,
            dry_run=dry_run
        )
        
        # Mark pending recompute if not dry run
        if not dry_run and result.candidates_applied > 0:
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.PROCEEDS_APPLICATION,
                {"high_confidence_applied": result.candidates_applied}
            )
        
        return {
            "success": True,
            "result": result.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Error applying high-confidence proceeds: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")
