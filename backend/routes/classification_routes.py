"""
Classification Routes

Handles unknown transaction classification, pattern detection, and auto-classification.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import logging

from .dependencies import db, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/custody", tags=["Classification"])


class BulkClassifyRequest(BaseModel):
    """Request model for bulk classification"""
    classification: str
    dry_run: bool = True


class PatternClassifyRequest(BaseModel):
    """Request model for pattern-based classification"""
    pattern_id: str
    classification: str
    dry_run: bool = True


class DestinationClassifyRequest(BaseModel):
    """Request model for destination-based classification"""
    destination_wallet: str
    classification: str
    dry_run: bool = True


class SuggestionDecisionRequest(BaseModel):
    """Request model for accepting/rejecting a suggestion"""
    tx_id: str
    accept: bool
    override_type: Optional[str] = None


# Lazy import to avoid circular imports
def get_classifier():
    from unknown_transaction_classifier import UnknownTransactionClassifier
    return UnknownTransactionClassifier(db)


@router.get("/classify/analyze")
async def analyze_unknown_transactions(
    user: dict = Depends(get_current_user),
    limit: int = 10000
):
    """
    Analyze all unknown transactions and generate classification suggestions.
    
    Returns:
    - Pattern detection results
    - Classification suggestions grouped by confidence level
    - Metrics on classification system performance
    
    Confidence Levels:
    - auto_apply: > 0.95 (can be auto-classified)
    - suggest: 0.7 - 0.95 (suggest for user confirmation)
    - unresolved: < 0.7 (needs manual review)
    """
    try:
        classifier = get_classifier()
        analysis = await classifier.analyze_unknown_transactions(
            user_id=user["id"],
            limit=limit
        )
        
        return {
            "success": True,
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Error analyzing unknown transactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/classify/auto-apply")
async def auto_classify_high_confidence(
    user: dict = Depends(get_current_user),
    dry_run: bool = True
):
    """
    Auto-classify transactions with confidence > 0.95.
    
    Only applies classifications that meet the auto-apply threshold.
    Use dry_run=true to preview what would be classified.
    """
    try:
        classifier = get_classifier()
        result = await classifier.auto_classify_high_confidence(
            user_id=user["id"],
            dry_run=dry_run
        )
        
        # Mark pending recompute if not dry run
        if not dry_run and result.get("classified_count", 0) > 0:
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.CLASSIFICATION_CHANGE,
                {"auto_classified": result["classified_count"]}
            )
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error auto-classifying: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Auto-classification failed: {str(e)}")


@router.post("/classify/by-pattern")
async def bulk_classify_by_pattern(
    request: PatternClassifyRequest,
    user: dict = Depends(get_current_user)
):
    """
    Bulk classify all transactions matching a specific pattern.
    
    Pattern IDs are returned from the /classify/analyze endpoint.
    """
    try:
        classifier = get_classifier()
        result = await classifier.bulk_classify_by_pattern(
            user_id=user["id"],
            pattern_id=request.pattern_id,
            classification=request.classification,
            dry_run=request.dry_run
        )
        
        # Mark pending recompute if not dry run
        if not request.dry_run and result.get("classified_count", 0) > 0:
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.CLASSIFICATION_CHANGE,
                {"pattern_classified": result["classified_count"]}
            )
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error bulk classifying by pattern: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.post("/classify/by-destination")
async def bulk_classify_by_destination(
    request: DestinationClassifyRequest,
    user: dict = Depends(get_current_user)
):
    """
    Bulk classify all unknown transactions to a specific destination wallet.
    """
    try:
        classifier = get_classifier()
        result = await classifier.bulk_classify_by_destination(
            user_id=user["id"],
            destination_wallet=request.destination_wallet,
            classification=request.classification,
            dry_run=request.dry_run
        )
        
        # Mark pending recompute if not dry run
        if not request.dry_run and result.get("classified_count", 0) > 0:
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.CLASSIFICATION_CHANGE,
                {"destination_classified": result["classified_count"]}
            )
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error bulk classifying by destination: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")


@router.post("/classify/decide")
async def apply_suggestion_decision(
    request: SuggestionDecisionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Apply or reject a single classification suggestion.
    
    This is the feedback loop - user decisions improve future suggestions.
    
    Args:
        tx_id: Transaction ID
        accept: True to accept suggestion, False to reject
        override_type: Optional classification to use instead of suggestion
    """
    try:
        classifier = get_classifier()
        result = await classifier.apply_single_suggestion(
            user_id=user["id"],
            tx_id=request.tx_id,
            accept=request.accept,
            override_type=request.override_type
        )
        
        # Mark pending recompute
        if result.get("success") and result.get("new_type") != "unknown":
            from recompute_service import RecomputeService, RecomputeTrigger
            recompute = RecomputeService(db)
            await recompute.mark_pending_recompute(
                user["id"],
                RecomputeTrigger.CLASSIFICATION_CHANGE,
                {"user_decision": request.tx_id}
            )
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error applying decision: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Decision failed: {str(e)}")


@router.get("/classify/metrics")
async def get_classification_metrics(
    user: dict = Depends(get_current_user),
    days: int = 30
):
    """
    Get classification metrics over time.
    
    Returns:
    - Current unknown count
    - Auto-classification rate
    - Suggestion accuracy
    - Daily stats breakdown
    """
    try:
        classifier = get_classifier()
        metrics = await classifier.get_classification_metrics(
            user_id=user["id"],
            days=days
        )
        
        return {
            "success": True,
            "metrics": metrics
        }
        
    except Exception as e:
        logger.error(f"Error getting metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.get("/classify/patterns")
async def get_detected_patterns(
    user: dict = Depends(get_current_user)
):
    """
    Get all detected patterns for unknown transactions.
    
    Patterns can be used for bulk classification.
    """
    try:
        patterns = await db.classification_patterns.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("confidence", -1).to_list(200)
        
        return {
            "success": True,
            "patterns": patterns
        }
        
    except Exception as e:
        logger.error(f"Error getting patterns: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get patterns: {str(e)}")


@router.post("/classify/rollback/{batch_id}")
async def rollback_classification_batch(
    batch_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Rollback a batch of classifications.
    
    Returns transactions to their original (unknown) state.
    """
    try:
        classifier = get_classifier()
        result = await classifier.rollback_classification_batch(
            user_id=user["id"],
            batch_id=batch_id
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error", "Batch not found"))
        
        # Mark pending recompute
        from recompute_service import RecomputeService, RecomputeTrigger
        recompute = RecomputeService(db)
        await recompute.mark_pending_recompute(
            user["id"],
            RecomputeTrigger.CLASSIFICATION_CHANGE,
            {"rollback_batch": batch_id}
        )
        
        return {
            "success": True,
            "result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rolling back batch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")


@router.get("/classify/batches")
async def get_classification_batches(
    user: dict = Depends(get_current_user)
):
    """
    Get all classification batches for potential rollback.
    """
    try:
        batches = await db.classification_batches.find(
            {"user_id": user["id"]},
            {"_id": 0, "classified": 0}  # Exclude large classified array
        ).sort("created_at", -1).to_list(100)
        
        return {
            "success": True,
            "batches": batches
        }
        
    except Exception as e:
        logger.error(f"Error getting batches: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get batches: {str(e)}")


@router.get("/classify/suggestions/{tx_id}")
async def get_suggestion_for_transaction(
    tx_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Get classification suggestion for a specific transaction.
    """
    try:
        # Get transaction
        tx = await db.exchange_transactions.find_one({
            "tx_id": tx_id,
            "user_id": user["id"]
        })
        
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Get analysis to generate suggestion
        classifier = get_classifier()
        known_wallets = await classifier._get_user_wallets(user["id"])
        linkages = await classifier._get_user_linkages(user["id"])
        historical = await classifier._get_historical_classifications(user["id"])
        patterns = await db.classification_patterns.find(
            {"user_id": user["id"]}
        ).to_list(1000)
        
        # Convert to PatternMatch objects
        from unknown_transaction_classifier import PatternMatch
        pattern_objects = [
            PatternMatch(**{k: v for k, v in p.items() if k != "_id" and k != "user_id" and k != "updated_at"})
            for p in patterns
        ]
        
        suggestion = classifier._generate_suggestion(
            tx, pattern_objects, known_wallets, linkages, historical
        )
        
        return {
            "success": True,
            "suggestion": suggestion.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting suggestion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get suggestion: {str(e)}")
