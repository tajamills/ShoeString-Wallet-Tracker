"""Custody routes - Chain of Custody analysis and PDF reports"""
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
        elif chain == 'solana':
            # Solana addresses are base58, typically 32-44 chars
            if len(address) < 32 or len(address) > 44:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Solana address format. Must be 32-44 characters."
                )
        elif chain == 'bitcoin':
            # Bitcoin addresses vary: legacy (26-35), segwit (42-62)
            if len(address) < 26 or len(address) > 62:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Bitcoin address format."
                )
            raise HTTPException(
                status_code=400,
                detail="Bitcoin chain of custody analysis is coming soon! Currently EVM chains and Solana are supported."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Chain '{chain}' is not yet supported for custody analysis. Supported: {', '.join(evm_chains + ['solana'])}."
            )
        
        # Run custody analysis
        result = custody_service.analyze_chain_of_custody(
            address=address,
            chain=chain,
            max_depth=request.max_depth,
            dormancy_days=request.dormancy_days
        )
        
        analysis_record = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "address": address,
            "chain": request.chain,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": result["summary"],
            "settings": result["settings"]
        }
        await db.custody_analyses.insert_one(analysis_record)
        
        logger.info(f"Chain of custody analysis completed for {address[:10]}... - {result['summary']['total_links_traced']} links traced")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chain of custody analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chain of custody analysis failed: {str(e)}")


@router.get("/history")
async def get_custody_analysis_history(
    user: dict = Depends(get_current_user)
):
    """Get user's chain of custody analysis history"""
    try:
        analyses = await db.custody_analyses.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("analysis_timestamp", -1).to_list(50)
        
        return {"analyses": analyses}
        
    except Exception as e:
        logger.error(f"Error fetching custody history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch analysis history")


@router.get("/known-addresses")
async def get_known_addresses():
    """Get list of known exchange and DEX addresses for reference"""
    return {
        "exchanges": [
            {"address": addr, "name": name} 
            for addr, name in KNOWN_EXCHANGE_ADDRESSES.items()
        ],
        "dexes": [
            {"address": addr, "name": name}
            for addr, name in KNOWN_DEX_ADDRESSES.items()
        ]
    }


@router.post("/export-pdf")
async def export_custody_pdf(
    request: CustodyAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """Generate a PDF report for Chain of Custody analysis"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="PDF reports require Unlimited subscription."
            )
        
        address = request.address.strip().lower()
        if not address.startswith('0x') or len(address) != 42:
            raise HTTPException(
                status_code=400,
                detail="Invalid EVM address format."
            )
        
        result = custody_service.analyze_chain_of_custody(
            address=address,
            chain=request.chain,
            max_depth=request.max_depth,
            dormancy_days=request.dormancy_days
        )
        
        user_info = {
            "email": user.get("email"),
            "id": user.get("id")
        }
        
        pdf_bytes = custody_report_generator.generate_report(result, user_info)
        
        filename = f"chain_of_custody_{address[:10]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        logger.info(f"Generated PDF report for {address[:10]}...")
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")


@router.post("/export-pdf-from-result")
async def export_custody_pdf_from_result(
    result: Dict[str, Any],
    user: dict = Depends(get_current_user)
):
    """Generate a PDF report from an existing custody analysis result"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="PDF reports require Unlimited subscription."
            )
        
        user_info = {
            "email": user.get("email"),
            "id": user.get("id")
        }
        
        pdf_bytes = custody_report_generator.generate_report(result, user_info)
        
        address = result.get('analyzed_address', 'unknown')[:10]
        filename = f"chain_of_custody_{address}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating PDF from result: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate PDF report")


# ========================================
# LINKAGE ENGINE ENDPOINTS
# ========================================

from linkage_engine_service import linkage_engine, LinkType, ChainStatus, ReviewStatus, ConfidenceLevel
from pydantic import BaseModel
from typing import Optional, List


class LinkWalletRequest(BaseModel):
    from_address: str
    to_address: str
    chain: str = "ethereum"
    reason: Optional[str] = None


class ResolveReviewRequest(BaseModel):
    review_id: str
    decision: str  # "yes", "no", "ignore"
    override_reason: Optional[str] = None


class DetectBreaksRequest(BaseModel):
    addresses: List[str]
    chain: str = "ethereum"


@router.post("/link-wallet")
async def link_wallet(
    request: LinkWalletRequest,
    user: dict = Depends(get_current_user)
):
    """
    Manually link two wallet addresses as owned by the user.
    Creates a high-confidence linkage edge and updates clusters.
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="Wallet linking requires a paid subscription."
            )
        
        edge = await linkage_engine.create_linkage_edge(
            user_id=user["id"],
            from_address=request.from_address,
            to_address=request.to_address,
            link_type=LinkType.USER_CONFIRMED,
            confidence=ConfidenceLevel.USER_CONFIRMED,
            reason="user_manual_link",
            chain=request.chain,
            metadata={"manual_reason": request.reason}
        )
        
        # Remove _id if present
        if "_id" in edge:
            del edge["_id"]
        
        return {
            "success": True,
            "message": "Wallets linked successfully",
            "edge": edge
        }
        
    except Exception as e:
        logger.error(f"Error linking wallets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to link wallets: {str(e)}")


@router.delete("/unlink-wallet/{edge_id}")
async def unlink_wallet(
    edge_id: str,
    user: dict = Depends(get_current_user)
):
    """Revoke a wallet linkage"""
    try:
        success = await linkage_engine.revoke_linkage_edge(
            edge_id=edge_id,
            user_id=user["id"],
            reason="user_revoked"
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Linkage not found")
        
        return {"success": True, "message": "Linkage revoked successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unlinking wallets: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to unlink wallets: {str(e)}")


@router.get("/linkages")
async def get_linkages(
    user: dict = Depends(get_current_user)
):
    """Get all wallet linkages for the user"""
    try:
        edges = await linkage_engine.get_edges_for_user(user["id"])
        
        return {
            "linkages": edges,
            "count": len(edges)
        }
        
    except Exception as e:
        logger.error(f"Error fetching linkages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch linkages: {str(e)}")


@router.get("/clusters")
async def get_clusters(
    user: dict = Depends(get_current_user)
):
    """Get all wallet clusters for the user"""
    try:
        clusters = await db.wallet_clusters.find({
            "user_id": user["id"],
            "is_active": True
        }, {"_id": 0}).to_list(100)
        
        # Add member addresses to each cluster
        for cluster in clusters:
            members = await db.cluster_members.find({
                "cluster_id": cluster["id"],
                "is_active": True
            }, {"_id": 0}).to_list(1000)
            cluster["addresses"] = [m["address"] for m in members]
        
        return {
            "clusters": clusters,
            "count": len(clusters)
        }
        
    except Exception as e:
        logger.error(f"Error fetching clusters: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch clusters: {str(e)}")


@router.post("/recompute-clusters")
async def recompute_clusters(
    user: dict = Depends(get_current_user)
):
    """Force recomputation of wallet clusters from linkage edges"""
    try:
        await linkage_engine.recompute_clusters(user["id"])
        
        return {"success": True, "message": "Clusters recomputed successfully"}
        
    except Exception as e:
        logger.error(f"Error recomputing clusters: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to recompute clusters: {str(e)}")


# ========================================
# REVIEW QUEUE ENDPOINTS
# ========================================

@router.get("/review-queue")
async def get_review_queue(
    user: dict = Depends(get_current_user)
):
    """Get pending chain break reviews for the user"""
    try:
        user_id = user["id"]
        logger.info(f"Fetching reviews for user_id: {user_id}")
        
        reviews = await linkage_engine.get_pending_reviews(user_id)
        
        logger.info(f"Found {len(reviews)} reviews for user {user_id}")
        
        return {
            "reviews": reviews,
            "count": len(reviews)
        }
        
    except Exception as e:
        logger.error(f"Error fetching review queue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch review queue: {str(e)}")


@router.post("/resolve-review")
async def resolve_review(
    request: ResolveReviewRequest,
    user: dict = Depends(get_current_user)
):
    """
    Resolve a chain break review.
    
    - decision: "yes" = it's my wallet (creates linkage, no tax event)
    - decision: "no" = external transfer (creates tax event)
    - decision: "ignore" = skip for now
    """
    try:
        if request.decision not in ["yes", "no", "ignore"]:
            raise HTTPException(
                status_code=400,
                detail="Decision must be 'yes', 'no', or 'ignore'"
            )
        
        result = await linkage_engine.resolve_review(
            review_id=request.review_id,
            user_id=user["id"],
            decision=request.decision,
            override_reason=request.override_reason
        )
        
        # Clean up _id fields
        for key in ["review", "tax_event", "linkage_edge"]:
            if result.get(key) and "_id" in result[key]:
                del result[key]["_id"]
        
        return {
            "success": True,
            "message": f"Review resolved: {request.decision}",
            "result": result
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error resolving review: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to resolve review: {str(e)}")


@router.post("/detect-breaks")
async def detect_chain_breaks(
    request: DetectBreaksRequest,
    user: dict = Depends(get_current_user)
):
    """
    Detect chain breaks for a set of addresses.
    Returns unlinked transfers that need review.
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="Chain break detection requires a paid subscription."
            )
        
        # Get all transactions for the user
        transactions = await db.exchange_transactions.find({
            "user_id": user["id"]
        }, {"_id": 0}).to_list(10000)
        
        # Get owned addresses
        owned_addresses = await linkage_engine.get_all_owned_addresses(user["id"])
        
        # Add requested addresses to owned set
        for addr in request.addresses:
            owned_addresses.add(addr.lower())
        
        # Detect breaks
        chain_breaks = await linkage_engine.detect_chain_breaks(
            user_id=user["id"],
            transactions=transactions,
            owned_addresses=owned_addresses
        )
        
        # Add to review queue
        for break_event in chain_breaks:
            await linkage_engine.add_to_review_queue(
                user_id=user["id"],
                tx_id=break_event["tx_id"],
                source_address=break_event["source_address"],
                destination_address=break_event["destination_address"],
                asset=break_event["asset"],
                amount=break_event["amount"],
                detected_reason=break_event["detected_reason"],
                confidence=break_event["confidence"],
                chain=break_event.get("chain", "ethereum")
            )
        
        return {
            "breaks_detected": len(chain_breaks),
            "chain_breaks": chain_breaks,
            "owned_addresses_count": len(owned_addresses)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting chain breaks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to detect chain breaks: {str(e)}")


# ========================================
# TAX EVENTS & FORM 8949 EXPORT
# ========================================

@router.get("/tax-events")
async def get_tax_events(
    tax_year: Optional[int] = None,
    user: dict = Depends(get_current_user)
):
    """Get tax events generated from chain break resolutions"""
    try:
        query = {"user_id": user["id"], "is_active": True}
        
        if tax_year:
            query["date_disposed"] = {
                "$gte": f"{tax_year}-01-01",
                "$lte": f"{tax_year}-12-31"
            }
        
        events = await db.tax_events.find(query, {"_id": 0}).sort("date_disposed", -1).to_list(10000)
        
        # Calculate totals
        total_gain = sum(e.get("gain_loss", 0) for e in events if e.get("gain_loss", 0) > 0)
        total_loss = sum(e.get("gain_loss", 0) for e in events if e.get("gain_loss", 0) < 0)
        
        return {
            "tax_events": events,
            "count": len(events),
            "summary": {
                "total_gain": total_gain,
                "total_loss": total_loss,
                "net": total_gain + total_loss
            },
            "tax_year": tax_year
        }
        
    except Exception as e:
        logger.error(f"Error fetching tax events: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch tax events: {str(e)}")


@router.get("/export-form-8949")
async def export_form_8949(
    tax_year: int,
    validate: bool = True,
    user: dict = Depends(get_current_user)
):
    """
    Export tax events in Form 8949 compatible CSV format.
    
    Args:
        tax_year: Tax year to export
        validate: If True, run validation before export (default True)
    
    Returns:
        CSV file or validation errors if validation fails
    """
    try:
        import csv
        from tax_validation_service import tax_validation_service, TxClassification
        
        events = await db.tax_events.find({
            "user_id": user["id"],
            "is_active": True,
            "date_disposed": {
                "$gte": f"{tax_year}-01-01",
                "$lte": f"{tax_year}-12-31"
            }
        }, {"_id": 0}).sort("date_disposed", 1).to_list(10000)
        
        # Build Form 8949 records for validation
        form_8949_records = []
        for event in events:
            form_data = event.get("form_8949_data", {})
            record = {
                "description": form_data.get("description", f"{event.get('quantity', 0)} {event.get('asset', '')}"),
                "date_acquired": form_data.get("date_acquired", event.get("date_acquired", "")),
                "date_sold": form_data.get("date_sold", event.get("date_disposed", "")),
                "proceeds": form_data.get("proceeds", event.get("proceeds", 0)),
                "cost_basis": form_data.get("cost_basis", event.get("cost_basis", 0)),
                "adjustment_code": form_data.get("adjustment_code", ""),
                "adjustment_amount": form_data.get("adjustment_amount", 0),
                "gain_or_loss": form_data.get("gain_or_loss", event.get("gain_loss", 0))
            }
            form_8949_records.append(record)
        
        # Run validation if enabled
        if validate and form_8949_records:
            can_export, validation_result = tax_validation_service.validate_form_8949_export(form_8949_records)
            
            if not can_export:
                # Return validation errors instead of CSV
                return {
                    "error": "Form 8949 validation failed",
                    "can_export": False,
                    "validation_result": validation_result.to_dict(),
                    "message": "Fix the following issues before exporting",
                    "issues": [v.to_dict() for v in validation_result.violations]
                }
        
        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header row (Form 8949 format)
        writer.writerow([
            "Description of Property",
            "Date Acquired",
            "Date Sold or Disposed",
            "Proceeds (Sales Price)",
            "Cost or Other Basis",
            "Adjustment Code",
            "Adjustment Amount",
            "Gain or (Loss)"
        ])
        
        for record in form_8949_records:
            writer.writerow([
                record["description"],
                record["date_acquired"],
                record["date_sold"],
                f"${record['proceeds']:.2f}",
                f"${record['cost_basis']:.2f}",
                record["adjustment_code"],
                f"${record['adjustment_amount']:.2f}" if record['adjustment_amount'] else "",
                f"${record['gain_or_loss']:.2f}"
            ])
        
        output.seek(0)
        
        filename = f"form_8949_{tax_year}_{datetime.now().strftime('%Y%m%d')}.csv"
        
        logger.info(f"Exported Form 8949 for {tax_year}: {len(form_8949_records)} records, validated={validate}")
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting Form 8949: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export Form 8949: {str(e)}")


@router.get("/export-review-queue")
async def export_review_queue_csv(
    user: dict = Depends(get_current_user)
):
    """
    Export review queue to CSV for offline review/updates.
    Users can modify this CSV and re-import to bulk resolve reviews.
    """
    try:
        import csv
        
        reviews = await db.review_queue.find({
            "user_id": user["id"]
        }, {"_id": 0}).sort("created_at", -1).to_list(10000)
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header row
        writer.writerow([
            "Review ID",
            "Transaction ID",
            "Source Address",
            "Destination Address",
            "Asset",
            "Amount",
            "Chain",
            "Detected Reason",
            "Confidence",
            "Status",
            "Decision",
            "Created At",
            "Resolved At",
            "Notes (for your use)"
        ])
        
        for review in reviews:
            writer.writerow([
                review.get("id"),
                review.get("tx_id"),
                review.get("source_address"),
                review.get("destination_address"),
                review.get("asset"),
                review.get("amount"),
                review.get("chain"),
                review.get("detected_reason"),
                review.get("confidence"),
                review.get("review_status"),
                review.get("user_decision", ""),
                review.get("created_at", ""),
                review.get("resolved_at", ""),
                ""  # Empty notes column for user
            ])
        
        output.seek(0)
        
        filename = f"review_queue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting review queue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export review queue: {str(e)}")



# ========================================
# TAX VALIDATION ENDPOINTS
# ========================================

from tax_validation_service import (
    tax_validation_service, 
    TxClassification, 
    ValidationStatus,
    InvariantType
)


class ValidateTransactionsRequest(BaseModel):
    """Request to validate a batch of transactions"""
    transactions: List[Dict[str, Any]]
    check_balances: bool = False
    balances: Optional[Dict[str, Dict[str, float]]] = None


class RunInvariantsRequest(BaseModel):
    """Request to run invariant checks"""
    balances: Optional[Dict[str, Dict[str, float]]] = None


@router.post("/validate/transactions")
async def validate_transactions(
    request: ValidateTransactionsRequest,
    user: dict = Depends(get_current_user)
):
    """
    Validate and classify a batch of transactions.
    
    Returns:
        - Classified transactions
        - Any that need review
        - Validation warnings
    """
    try:
        validated = []
        needs_review = []
        
        for tx in request.transactions:
            tx_validated = tax_validation_service.validate_classification(tx)
            validated.append(tx_validated)
            
            if tx_validated.get("needs_review"):
                needs_review.append(tx_validated)
        
        return {
            "success": True,
            "total_transactions": len(validated),
            "validated_transactions": validated,
            "needs_review_count": len(needs_review),
            "needs_review": needs_review
        }
        
    except Exception as e:
        logger.error(f"Error validating transactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to validate transactions: {str(e)}")


@router.post("/validate/invariants")
async def run_invariant_checks(
    request: RunInvariantsRequest,
    user: dict = Depends(get_current_user)
):
    """
    Run all invariant checks on the user's tax data.
    
    Checks:
    - Balance reconciliation
    - Cost basis conservation
    - No double spend
    - No orphan disposals
    
    Returns:
        Validation result with any violations
    """
    try:
        result = tax_validation_service.run_all_invariant_checks(
            balances=request.balances
        )
        
        return {
            "success": result.is_valid,
            "status": result.status.value,
            "can_export_taxes": result.is_valid,
            "violations_count": len(result.violations),
            "violations": [v.to_dict() for v in result.violations],
            "warnings": result.warnings,
            "audit_entries": len(result.audit_trail)
        }
        
    except Exception as e:
        logger.error(f"Error running invariant checks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to run invariant checks: {str(e)}")


@router.get("/validate/account-status")
async def get_account_tax_status(
    user: dict = Depends(get_current_user)
):
    """
    Get the current tax validation status for the account.
    
    Returns:
        - Whether account is in valid tax state
        - Any active violations
        - Recent audit trail
    """
    try:
        is_valid = tax_validation_service.is_account_tax_state_valid()
        violations = tax_validation_service.violations
        audit_trail = tax_validation_service.get_audit_trail(limit=50)
        
        return {
            "account_tax_state_valid": is_valid,
            "can_export_form_8949": is_valid,
            "active_violations": len(violations),
            "violations": [v.to_dict() for v in violations],
            "recent_audit_entries": audit_trail
        }
        
    except Exception as e:
        logger.error(f"Error getting account tax status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get account tax status: {str(e)}")


@router.post("/validate/recompute")
async def trigger_tax_recompute(
    reason: str = "user_requested",
    user: dict = Depends(get_current_user)
):
    """
    Trigger full recomputation of tax data.
    
    Use when:
    - Wallet linkage changes
    - Transaction classification changes
    - Data corrections made
    
    No partial updates - full recalculation.
    """
    try:
        result = tax_validation_service.trigger_full_recompute(reason)
        
        return {
            "success": True,
            "message": "Tax data recomputation triggered",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error triggering recompute: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger recompute: {str(e)}")


@router.get("/validate/lot-status/{asset}")
async def get_lot_status(
    asset: str,
    user: dict = Depends(get_current_user)
):
    """
    Get current lot status for a specific asset.
    
    Shows:
    - All lots with remaining quantities
    - Total cost basis
    - Disposed vs remaining
    """
    try:
        lot_status = tax_validation_service.get_lot_status(asset)
        
        return {
            "success": True,
            "asset": asset,
            "lot_status": lot_status
        }
        
    except Exception as e:
        logger.error(f"Error getting lot status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get lot status: {str(e)}")


@router.get("/validate/audit-trail")
async def get_audit_trail(
    limit: int = 100,
    user: dict = Depends(get_current_user)
):
    """
    Get recent audit trail entries.
    
    Returns chronological list of tax calculation actions
    for auditability and debugging.
    """
    try:
        audit_trail = tax_validation_service.get_audit_trail(limit=limit)
        
        return {
            "success": True,
            "entries_count": len(audit_trail),
            "audit_trail": audit_trail
        }
        
    except Exception as e:
        logger.error(f"Error getting audit trail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get audit trail: {str(e)}")



# ========================================
# BETA VALIDATION HARNESS ENDPOINTS
# ========================================

from beta_validation_harness import BetaValidationHarness, create_validation_harness, SeverityLevel


class BetaValidateRequest(BaseModel):
    """Request to validate a beta account"""
    user_id: Optional[str] = None  # If None, uses current user
    tax_year: int = 2024
    include_all_transactions: bool = True


class BatchValidateRequest(BaseModel):
    """Request to validate multiple accounts"""
    user_ids: List[str]
    tax_year: int = 2024


@router.post("/beta/validate")
async def beta_validate_account(
    request: BetaValidateRequest,
    user: dict = Depends(get_current_user)
):
    """
    Run full validation on an account for beta testing.
    
    Generates a comprehensive report including:
    - Transaction classification summary
    - Unresolved review items
    - Lot reconciliation summary
    - Disposal summary
    - Validation status and can_export flag
    - All invariant check results
    - Highlighted issues (orphan disposals, balance mismatches, etc.)
    """
    try:
        # Use current user if not specified
        target_user_id = request.user_id or user["id"]
        
        # Create harness with db
        harness = create_validation_harness(db)
        
        # Run validation
        report = await harness.validate_account(
            user_id=target_user_id,
            tax_year=request.tax_year,
            include_all_transactions=request.include_all_transactions
        )
        
        # Export to file for manual review
        report_path = f"/app/test_reports/beta_validation_{target_user_id}_{request.tax_year}"
        harness.export_report(report, report_path, format="both")
        
        return {
            "success": True,
            "report": report.to_dict(),
            "human_readable": report.to_human_readable(),
            "report_files": {
                "json": f"{report_path}.json",
                "text": f"{report_path}.txt"
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in beta validation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Beta validation failed: {str(e)}")


@router.post("/beta/validate-batch")
async def beta_validate_batch(
    request: BatchValidateRequest,
    user: dict = Depends(get_current_user)
):
    """
    Run validation on multiple accounts for beta testing.
    
    Returns individual reports plus a batch summary.
    """
    try:
        harness = create_validation_harness(db)
        
        # Run validation on all accounts
        reports = await harness.validate_multiple_accounts(
            user_ids=request.user_ids,
            tax_year=request.tax_year
        )
        
        # Generate batch summary
        batch_summary = harness.generate_batch_summary(reports)
        
        # Export individual reports
        for user_id, report in reports.items():
            report_path = f"/app/test_reports/beta_validation_{user_id}_{request.tax_year}"
            harness.export_report(report, report_path, format="both")
        
        # Export batch summary
        batch_summary_path = f"/app/test_reports/beta_batch_summary_{request.tax_year}.json"
        with open(batch_summary_path, "w") as f:
            import json
            json.dump(batch_summary, f, indent=2)
        
        return {
            "success": True,
            "batch_summary": batch_summary,
            "individual_reports": {
                user_id: report.to_dict() 
                for user_id, report in reports.items()
            },
            "batch_summary_file": batch_summary_path
        }
        
    except Exception as e:
        logger.error(f"Error in batch validation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch validation failed: {str(e)}")


@router.get("/beta/validation-report/{user_id}")
async def get_beta_validation_report(
    user_id: str,
    tax_year: int = 2024,
    format: str = "json",
    user: dict = Depends(get_current_user)
):
    """
    Get a previously generated validation report.
    
    Args:
        user_id: The user ID to get report for
        tax_year: Tax year of the report
        format: "json" or "text"
    """
    try:
        if format == "json":
            report_path = f"/app/test_reports/beta_validation_{user_id}_{tax_year}.json"
        else:
            report_path = f"/app/test_reports/beta_validation_{user_id}_{tax_year}.txt"
        
        if not os.path.exists(report_path):
            raise HTTPException(
                status_code=404, 
                detail=f"Report not found. Run /api/custody/beta/validate first."
            )
        
        with open(report_path, "r") as f:
            content = f.read()
        
        if format == "json":
            import json
            return json.loads(content)
        else:
            return {"report_text": content}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting validation report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get report: {str(e)}")


@router.get("/beta/pre-export-check")
async def pre_export_check(
    tax_year: int = 2024,
    user: dict = Depends(get_current_user)
):
    """
    Quick pre-export check before Form 8949 generation.
    
    Returns a summary of blocking issues without full report generation.
    """
    try:
        harness = create_validation_harness(db)
        report = await harness.validate_account(
            user_id=user["id"],
            tax_year=tax_year
        )
        
        # Extract key blocking issues
        blocking_issues = [
            i.to_dict() for i in report.issues 
            if i.severity in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]
        ]
        
        failed_invariants = [
            c.to_dict() for c in report.invariant_checks 
            if not c.passed
        ]
        
        return {
            "can_export": report.can_export,
            "validation_status": report.validation_status,
            "export_blocked_reason": report.export_blocked_reason,
            "blocking_issues_count": len(blocking_issues),
            "blocking_issues": blocking_issues,
            "failed_invariants": failed_invariants,
            "unresolved_review_count": report.review_queue_count,
            "recommendation": (
                "Ready for Form 8949 export" if report.can_export 
                else "Resolve blocking issues before export"
            )
        }
        
    except Exception as e:
        logger.error(f"Error in pre-export check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Pre-export check failed: {str(e)}")
