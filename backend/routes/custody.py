"""Custody routes - Chain of Custody analysis and PDF reports"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from datetime import datetime, timezone
import uuid
import io
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
            "message": f"Wallets linked successfully",
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
        reviews = await linkage_engine.get_pending_reviews(user["id"])
        
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
    user: dict = Depends(get_current_user)
):
    """
    Export tax events in Form 8949 compatible CSV format.
    """
    try:
        import csv
        
        events = await db.tax_events.find({
            "user_id": user["id"],
            "is_active": True,
            "date_disposed": {
                "$gte": f"{tax_year}-01-01",
                "$lte": f"{tax_year}-12-31"
            }
        }, {"_id": 0}).sort("date_disposed", 1).to_list(10000)
        
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
        
        for event in events:
            form_data = event.get("form_8949_data", {})
            writer.writerow([
                form_data.get("description", f"{event.get('quantity', 0)} {event.get('asset', '')}"),
                form_data.get("date_acquired", event.get("date_acquired", "")),
                form_data.get("date_sold", event.get("date_disposed", "")),
                f"${form_data.get('proceeds', event.get('proceeds', 0)):.2f}",
                f"${form_data.get('cost_basis', event.get('cost_basis', 0)):.2f}",
                form_data.get("adjustment_code", ""),
                f"${form_data.get('adjustment_amount', 0):.2f}" if form_data.get('adjustment_amount') else "",
                f"${form_data.get('gain_or_loss', event.get('gain_loss', 0)):.2f}"
            ])
        
        output.seek(0)
        
        filename = f"form_8949_{tax_year}_{datetime.now().strftime('%Y%m%d')}.csv"
        
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

