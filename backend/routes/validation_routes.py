"""
Validation Routes

Handles tax validation, invariant checking, and account status.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel
import logging

from .dependencies import db, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/custody", tags=["Validation"])


class ValidateTransactionsRequest(BaseModel):
    """Request model for transaction validation"""
    tax_year: Optional[int] = None


@router.post("/validate/transactions")
async def validate_transactions(
    request: ValidateTransactionsRequest,
    user: dict = Depends(get_current_user)
):
    """Validate all transactions for tax compliance"""
    try:
        from tax_validation_service import TaxValidationService
        service = TaxValidationService(db)
        
        result = await service.validate_transactions(
            user_id=user["id"],
            tax_year=request.tax_year
        )
        
        return {
            "success": True,
            "validation": result
        }
        
    except Exception as e:
        logger.error(f"Error validating transactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/validate/invariants")
async def validate_invariants(
    user: dict = Depends(get_current_user)
):
    """Check all tax invariants (balance reconciliation, cost basis conservation, etc.)"""
    try:
        from tax_validation_service import TaxValidationService
        service = TaxValidationService(db)
        
        result = await service.check_all_invariants(user["id"])
        
        return {
            "success": True,
            "invariants": result
        }
        
    except Exception as e:
        logger.error(f"Error checking invariants: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Invariant check failed: {str(e)}")


@router.get("/validate/account-status")
async def get_account_validation_status(
    user: dict = Depends(get_current_user)
):
    """Get overall validation status for the account"""
    try:
        from export_safety_guard import ExportSafetyGuard
        guard = ExportSafetyGuard(db)
        
        summary = await guard.get_pre_export_summary(user["id"])
        
        return {
            "success": True,
            "status": summary.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Error getting validation status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/validate/recompute")
async def trigger_recompute(
    user: dict = Depends(get_current_user)
):
    """Trigger full recompute of tax lots, disposals, and validation state"""
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
        logger.error(f"Error triggering recompute: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Recompute failed: {str(e)}")


@router.get("/validate/lot-status/{asset}")
async def get_lot_status_for_asset(
    asset: str,
    user: dict = Depends(get_current_user)
):
    """Get tax lot status for a specific asset"""
    try:
        lots = await db.tax_lots.find({
            "user_id": user["id"],
            "asset": asset.upper()
        }, {"_id": 0}).to_list(10000)
        
        total_remaining = sum(lot.get("remaining_quantity", 0) for lot in lots)
        total_cost_basis = sum(
            lot.get("cost_per_unit", 0) * lot.get("remaining_quantity", 0) 
            for lot in lots
        )
        
        return {
            "success": True,
            "asset": asset.upper(),
            "lot_count": len(lots),
            "total_remaining": total_remaining,
            "total_cost_basis": round(total_cost_basis, 2),
            "lots": lots[:50]  # Limit to first 50
        }
        
    except Exception as e:
        logger.error(f"Error getting lot status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get lot status: {str(e)}")


@router.get("/validate/audit-trail")
async def get_audit_trail(
    user: dict = Depends(get_current_user),
    limit: int = 100,
    action: Optional[str] = None
):
    """Get audit trail entries for the user"""
    try:
        query = {"user_id": user["id"]}
        if action:
            query["action"] = action
        
        entries = await db.tax_audit_trail.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        return {
            "success": True,
            "count": len(entries),
            "entries": entries
        }
        
    except Exception as e:
        logger.error(f"Error getting audit trail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get audit trail: {str(e)}")


@router.post("/beta/validate")
async def beta_validate_account(
    user: dict = Depends(get_current_user)
):
    """Run beta validation harness on the account"""
    try:
        from beta_validation_harness import BetaValidationHarness
        harness = BetaValidationHarness(db)
        
        report = await harness.validate_user_account(user["id"])
        
        return {
            "success": True,
            "report": report
        }
        
    except Exception as e:
        logger.error(f"Error running beta validation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Beta validation failed: {str(e)}")


@router.get("/beta/pre-export-check")
async def pre_export_check(
    user: dict = Depends(get_current_user),
    tax_year: Optional[int] = None
):
    """
    Run pre-export validation check.
    
    Returns comprehensive summary including:
    - validation_status
    - can_export
    - blocking issues
    - recommendations
    """
    try:
        from export_safety_guard import ExportSafetyGuard
        guard = ExportSafetyGuard(db)
        
        # Get pre-export summary
        summary = await guard.get_pre_export_summary(user["id"], tax_year)
        
        # Check if export is allowed
        allowed, error = await guard.check_export_allowed(user["id"], tax_year)
        
        return {
            "success": True,
            "can_export": allowed,
            "summary": summary.to_dict(),
            "blocking_error": error.to_dict() if error else None
        }
        
    except Exception as e:
        logger.error(f"Error running pre-export check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pre-export check failed: {str(e)}")


@router.get("/validation-status")
async def get_validation_status(
    user: dict = Depends(get_current_user)
):
    """Get current validation status (lightweight check)"""
    try:
        from export_safety_guard import ExportSafetyGuard
        guard = ExportSafetyGuard(db)
        
        summary = await guard.get_pre_export_summary(user["id"])
        
        return {
            "success": True,
            "validation_status": summary.validation_status,
            "can_export": summary.can_export,
            "blocking_issues_count": summary.blocking_issues_count,
            "unresolved_review_count": summary.unresolved_review_count,
            "last_recompute": summary.last_recompute_timestamp
        }
        
    except Exception as e:
        logger.error(f"Error getting validation status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


# === REGRESSION FIXTURE ROUTES ===

class CreateFixtureRequest(BaseModel):
    """Request model for creating regression fixture"""
    version_tag: str
    description: Optional[str] = ""


@router.post("/regression/create-fixture")
async def create_regression_fixture(
    request: CreateFixtureRequest,
    user: dict = Depends(get_current_user)
):
    """
    Create a regression fixture for the current account state.
    
    Snapshots:
    - Raw transactions
    - Normalized transfers
    - Wallet linkages
    - Tax lots and disposals
    - Validation state
    - Form 8949 dataset
    """
    try:
        from regression_fixture_service import RegressionFixtureService
        service = RegressionFixtureService(db)
        
        fixture = await service.create_fixture(
            user_id=user["id"],
            version_tag=request.version_tag,
            description=request.description
        )
        
        return {
            "success": True,
            "fixture": fixture.metadata.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Error creating fixture: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create fixture: {str(e)}")


@router.post("/regression/run-test/{fixture_id}")
async def run_regression_test(
    fixture_id: str,
    user: dict = Depends(get_current_user),
    recompute: bool = True
):
    """
    Run regression test against a stored fixture.
    
    Re-runs the full pipeline and compares:
    - Disposal count
    - Total proceeds
    - Total cost basis
    - Total gain/loss
    - Validation status
    - can_export
    """
    try:
        from regression_fixture_service import RegressionFixtureService
        service = RegressionFixtureService(db)
        
        result = await service.run_regression_test(
            fixture_id=fixture_id,
            recompute=recompute
        )
        
        return {
            "success": True,
            "passed": result.passed,
            "result": result.to_dict()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error running regression test: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Regression test failed: {str(e)}")


@router.get("/regression/fixtures")
async def list_regression_fixtures(
    user: dict = Depends(get_current_user)
):
    """List all regression fixtures for the user"""
    try:
        from regression_fixture_service import RegressionFixtureService
        service = RegressionFixtureService(db)
        
        fixtures = await service.list_fixtures(user["id"])
        
        return {
            "success": True,
            "fixtures": fixtures
        }
        
    except Exception as e:
        logger.error(f"Error listing fixtures: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list fixtures: {str(e)}")


@router.delete("/regression/fixtures/{fixture_id}")
async def delete_regression_fixture(
    fixture_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a regression fixture"""
    try:
        from regression_fixture_service import RegressionFixtureService
        service = RegressionFixtureService(db)
        
        deleted = await service.delete_fixture(fixture_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Fixture not found")
        
        return {"success": True, "deleted": fixture_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting fixture: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete fixture: {str(e)}")
