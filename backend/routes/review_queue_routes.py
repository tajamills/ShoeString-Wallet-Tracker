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
    status: Optional[str] = None,
    include_pending_sends: bool = True
):
    """
    Get pending review queue items for wallet ownership verification.
    
    Also includes exchange send/withdrawal transactions that haven't been
    verified as internal transfers or external sends.
    """
    try:
        items = []
        
        # 1. Get items from review_queue collection
        query = {"user_id": user["id"]}
        if status:
            query["review_status"] = status
        else:
            query["review_status"] = "pending"
        
        review_items = await db.review_queue.find(query, {"_id": 0}).to_list(1000)
        items.extend(review_items)
        
        # 2. Get pending send/withdrawal transactions from exchange data
        if include_pending_sends:
            pending_sends = await db.exchange_transactions.find({
                "user_id": user["id"],
                "tx_type": {"$in": ["send", "withdrawal", "transfer"]},
                "chain_status": {"$in": ["pending", "unknown", None]}
            }, {"_id": 0}).to_list(1000)
            
            # Convert to review format
            for tx in pending_sends:
                # Skip if already in review queue
                existing = next((r for r in review_items if r.get("tx_id") == tx.get("tx_id")), None)
                if existing:
                    continue
                
                items.append({
                    "tx_id": tx.get("tx_id"),
                    "user_id": user["id"],
                    "review_status": "pending",
                    "source_type": "exchange_transaction",
                    "source_address": f"{tx.get('exchange', 'exchange')}_wallet",
                    "destination_address": tx.get("notes", "unknown_destination"),
                    "asset": tx.get("asset"),
                    "amount": tx.get("amount"),
                    "timestamp": tx.get("timestamp"),
                    "exchange": tx.get("exchange"),
                    "detected_reason": "outgoing_transfer",
                    "question": f"Did you send {tx.get('amount', 0):.4f} {tx.get('asset', 'CRYPTO')} to your own wallet, or was this an external payment?",
                    "options": [
                        {"value": "internal", "label": "My wallet (internal transfer - not taxable)"},
                        {"value": "external", "label": "External payment (taxable event)"},
                        {"value": "connect_wallet", "label": "Connect wallet to verify"}
                    ]
                })
        
        # Sort by timestamp (newest first)
        items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        # Count by type
        pending_count = len([i for i in items if i.get("review_status") == "pending"])
        exchange_sends = len([i for i in items if i.get("source_type") == "exchange_transaction"])
        
        return {
            "success": True,
            "count": len(items),
            "pending_count": pending_count,
            "exchange_sends_count": exchange_sends,
            "items": items,
            "message": f"{pending_count} transactions need review. Connect wallets or APIs to auto-verify ownership." if pending_count > 0 else "All transactions verified."
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
    - "yes" / "mine" / "internal": The destination wallet belongs to the user (internal transfer - not taxable)
    - "no" / "external": The destination is external (taxable event)
    - "ignore": Skip this item
    """
    try:
        # Validate decision
        valid_decisions = ["yes", "no", "ignore", "mine", "external", "internal"]
        if request.decision not in valid_decisions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid decision: {request.decision}. Must be one of: {valid_decisions}"
            )
        
        # Normalize decision
        decision = request.decision
        if decision in ["mine", "internal"]:
            decision = "yes"
        elif decision == "external":
            decision = "no"
        
        # First, try to find in review_queue collection
        review_item = await db.review_queue.find_one({
            "tx_id": request.tx_id,
            "user_id": user["id"]
        })
        
        # If not found in review_queue, check if it's an exchange transaction
        exchange_tx = None
        if not review_item:
            exchange_tx = await db.exchange_transactions.find_one({
                "tx_id": request.tx_id,
                "user_id": user["id"],
                "tx_type": {"$in": ["send", "withdrawal", "transfer"]}
            })
            
            if not exchange_tx:
                raise HTTPException(status_code=404, detail="Review item not found")
        
        # Process decision
        if decision == "yes":
            # Internal transfer - mark as linked (not a taxable event)
            chain_status = "linked"
            
            if review_item:
                # Update review queue item
                await db.review_queue.update_one(
                    {"tx_id": request.tx_id, "user_id": user["id"]},
                    {"$set": {
                        "review_status": "resolved_yes",
                        "resolved_at": datetime.now(timezone.utc).isoformat(),
                        "resolution": "internal_transfer"
                    }}
                )
            
            # Update exchange transaction
            await db.exchange_transactions.update_one(
                {"tx_id": request.tx_id, "user_id": user["id"]},
                {"$set": {
                    "chain_status": "linked",
                    "is_internal_transfer": True,
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return {
                "success": True,
                "message": "Marked as internal transfer (not taxable)",
                "tx_id": request.tx_id,
                "chain_status": "linked"
            }
            
        elif decision == "no":
            # External send - mark as external (taxable disposal)
            if review_item:
                await db.review_queue.update_one(
                    {"tx_id": request.tx_id, "user_id": user["id"]},
                    {"$set": {
                        "review_status": "resolved_no",
                        "resolved_at": datetime.now(timezone.utc).isoformat(),
                        "resolution": "external_send"
                    }}
                )
            
            # Update exchange transaction
            await db.exchange_transactions.update_one(
                {"tx_id": request.tx_id, "user_id": user["id"]},
                {"$set": {
                    "chain_status": "external",
                    "is_internal_transfer": False,
                    "resolved_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return {
                "success": True,
                "message": "Marked as external send (taxable event)",
                "tx_id": request.tx_id,
                "chain_status": "external"
            }
            
        else:  # ignore
            if review_item:
                await db.review_queue.update_one(
                    {"tx_id": request.tx_id, "user_id": user["id"]},
                    {"$set": {
                        "review_status": "ignored",
                        "resolved_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
            
            await db.exchange_transactions.update_one(
                {"tx_id": request.tx_id, "user_id": user["id"]},
                {"$set": {"chain_status": "ignored"}}
            )
            
            return {
                "success": True,
                "message": "Transaction ignored",
                "tx_id": request.tx_id
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
