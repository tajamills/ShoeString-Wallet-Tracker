"""
Review Queue Routes

Handles review queue operations for wallet ownership verification.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import logging

from .dependencies import db, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/custody", tags=["Review Queue"])


class ReviewDecisionRequest(BaseModel):
    """Request model for review decision"""
    tx_id: str
    decision: str  # "yes" (mine), "no" (external), "ignore"


class BulkResolveRequest(BaseModel):
    """Request model for bulk resolution"""
    tx_ids: List[str]
    decision: str  # "mine" or "external"


# Import service lazily to avoid circular imports
def get_review_queue_service():
    from review_queue_enhancements import ReviewQueueEnhancementService
    return ReviewQueueEnhancementService(db)


@router.get("/review-queue")
async def get_review_queue(
    user: dict = Depends(get_current_user),
    status: Optional[str] = None
):
    """Get pending review queue items for wallet ownership verification"""
    try:
        query = {"user_id": user["id"]}
        if status:
            query["review_status"] = status
        else:
            query["review_status"] = "pending"
        
        items = await db.review_queue.find(query, {"_id": 0}).to_list(1000)
        
        return {
            "success": True,
            "count": len(items),
            "items": items
        }
        
    except Exception as e:
        logger.error(f"Error getting review queue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get review queue: {str(e)}")


@router.post("/resolve-review")
async def resolve_review(
    request: ReviewDecisionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Submit decision for a review queue item.
    
    Decisions:
    - "yes" / "mine": The destination wallet belongs to the user (creates linkage)
    - "no" / "external": The destination is external (creates tax event)
    - "ignore": Skip this item
    """
    try:
        # Validate decision
        valid_decisions = ["yes", "no", "ignore", "mine", "external"]
        if request.decision not in valid_decisions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid decision: {request.decision}. Must be one of: {valid_decisions}"
            )
        
        # Normalize decision
        decision = request.decision
        if decision == "mine":
            decision = "yes"
        elif decision == "external":
            decision = "no"
        
        # Find the review item
        review_item = await db.review_queue.find_one({
            "tx_id": request.tx_id,
            "user_id": user["id"]
        })
        
        if not review_item:
            raise HTTPException(status_code=404, detail="Review item not found")
        
        # Process decision
        if decision == "yes":
            # Create wallet linkage
            from linkage_engine_service import linkage_engine
            await linkage_engine.create_user_confirmed_link(
                user_id=user["id"],
                from_address=review_item.get("source_wallet", "user_wallet"),
                to_address=review_item.get("destination_wallet", "unknown"),
                db=db
            )
            
            # Update transaction chain status
            await db.exchange_transactions.update_one(
                {"tx_id": request.tx_id, "user_id": user["id"]},
                {"$set": {"chain_status": "linked"}}
            )
            
        elif decision == "no":
            # Mark as external - this is a taxable disposal
            await db.exchange_transactions.update_one(
                {"tx_id": request.tx_id, "user_id": user["id"]},
                {"$set": {"chain_status": "external_transfer"}}
            )
        
        # Update review status
        await db.review_queue.update_one(
            {"tx_id": request.tx_id, "user_id": user["id"]},
            {
                "$set": {
                    "review_status": "resolved",
                    "decision": decision,
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # Mark pending recompute
        from recompute_service import RecomputeService, RecomputeTrigger
        recompute = RecomputeService(db)
        await recompute.mark_pending_recompute(
            user["id"],
            RecomputeTrigger.LINKAGE_CHANGE,
            {"tx_id": request.tx_id, "decision": decision}
        )
        
        return {
            "success": True,
            "tx_id": request.tx_id,
            "decision": decision,
            "message": f"Review resolved as '{decision}'"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving review: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve review: {str(e)}")


@router.get("/review-queue/suggestions")
async def get_wallet_suggestions(
    user: dict = Depends(get_current_user)
):
    """Get AI-powered wallet link suggestions based on transaction patterns"""
    try:
        service = get_review_queue_service()
        suggestions = await service.generate_wallet_link_suggestions(user["id"])
        
        return {
            "success": True,
            "suggestions": suggestions
        }
        
    except Exception as e:
        logger.error(f"Error getting suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


@router.post("/review-queue/bulk-resolve")
async def bulk_resolve_reviews(
    request: BulkResolveRequest,
    user: dict = Depends(get_current_user)
):
    """
    Bulk resolve multiple review queue items with the same decision.
    """
    try:
        if request.decision not in ["mine", "external"]:
            raise HTTPException(
                status_code=400,
                detail="Decision must be 'mine' or 'external'"
            )
        
        service = get_review_queue_service()
        results = await service.bulk_resolve(
            user_id=user["id"],
            tx_ids=request.tx_ids,
            decision=request.decision
        )
        
        # Mark pending recompute
        from recompute_service import RecomputeService, RecomputeTrigger
        recompute = RecomputeService(db)
        await recompute.mark_pending_recompute(
            user["id"],
            RecomputeTrigger.LINKAGE_CHANGE,
            {"bulk_resolve": len(request.tx_ids)}
        )
        
        return {
            "success": True,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk resolving: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to bulk resolve: {str(e)}")


@router.post("/review-queue/bulk-resolve-category/{category}")
async def bulk_resolve_category(
    category: str,
    user: dict = Depends(get_current_user),
    decision: str = "external"
):
    """
    Bulk resolve all items in a category.
    
    Categories: unknown_wallet, exchange_address, dex_address
    """
    try:
        if decision not in ["mine", "external"]:
            raise HTTPException(
                status_code=400,
                detail="Decision must be 'mine' or 'external'"
            )
        
        service = get_review_queue_service()
        results = await service.bulk_resolve_category(
            user_id=user["id"],
            category=category,
            decision=decision
        )
        
        # Mark pending recompute
        from recompute_service import RecomputeService, RecomputeTrigger
        recompute = RecomputeService(db)
        await recompute.mark_pending_recompute(
            user["id"],
            RecomputeTrigger.LINKAGE_CHANGE,
            {"category": category, "decision": decision}
        )
        
        return {
            "success": True,
            "category": category,
            "decision": decision,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk resolving category: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to bulk resolve: {str(e)}")


@router.get("/review-queue/grouped")
async def get_grouped_review_queue(
    user: dict = Depends(get_current_user)
):
    """Get review queue items grouped by pattern for efficient resolution"""
    try:
        service = get_review_queue_service()
        grouped = await service.get_grouped_review_queue(user["id"])
        
        return {
            "success": True,
            "grouped_items": grouped
        }
        
    except Exception as e:
        logger.error(f"Error getting grouped queue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get grouped queue: {str(e)}")
