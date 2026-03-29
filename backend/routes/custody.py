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
from constrained_proceeds_service import ConstrainedProceedsService
from price_backfill_service import PriceBackfillService
from staged_proceeds_service import StagedProceedsService, StagedApplicationFilters, ValuationFilter

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
    user: dict = Depends(get_current_user),
    include_pending_sends: bool = True
):
    """
    Get pending chain break reviews for the user.
    
    Also includes exchange send/withdrawal transactions that haven't been
    verified as internal transfers or external sends.
    """
    try:
        user_id = user["id"]
        logger.info(f"Fetching reviews for user_id: {user_id}")
        
        items = []
        
        # 1. Get traditional chain break reviews
        reviews = await linkage_engine.get_pending_reviews(user_id)
        items.extend(reviews)
        
        # 2. Get pending send/withdrawal transactions from exchange data
        if include_pending_sends:
            pending_sends = await db.exchange_transactions.find({
                "user_id": user_id,
                "tx_type": {"$in": ["send", "withdrawal", "transfer"]},
                "chain_status": {"$in": ["pending", "unknown", None]}
            }, {"_id": 0}).to_list(1000)
            
            # Convert to review format
            for tx in pending_sends:
                # Skip if already in reviews
                existing = next((r for r in reviews if r.get("tx_id") == tx.get("tx_id")), None)
                if existing:
                    continue
                
                # Determine destination - try notes, then tx_hash, then tx_id
                destination = tx.get("notes") or tx.get("to_address") or tx.get("destination")
                if not destination or destination.strip() == "":
                    # Use tx_id as identifier if no destination
                    destination = f"TX: {tx.get('tx_id', 'unknown')}"
                
                items.append({
                    "tx_id": tx.get("tx_id"),
                    "review_id": tx.get("tx_id"),  # For compatibility
                    "user_id": user_id,
                    "review_status": "pending",
                    "source_type": "exchange_transaction",
                    "source_address": f"{tx.get('exchange', 'exchange')}_wallet",
                    "destination_address": destination,
                    "asset": tx.get("asset"),
                    "amount": tx.get("amount"),
                    "timestamp": tx.get("timestamp").isoformat() if hasattr(tx.get("timestamp"), 'isoformat') else str(tx.get("timestamp", "")),
                    "exchange": tx.get("exchange"),
                    "source_file": tx.get("source_file"),
                    "detected_reason": "outgoing_transfer_needs_verification",
                    "question": f"Did you send {tx.get('amount', 0):.4f} {tx.get('asset', 'CRYPTO')} to your own wallet?",
                    "options": [
                        {"value": "yes", "label": "Yes, my wallet (internal transfer - not taxable)"},
                        {"value": "no", "label": "No, external payment (taxable event)"},
                        {"value": "connect_wallet", "label": "I need to connect a wallet to verify"}
                    ],
                    "help_text": "If this was a transfer to another wallet you own (like a hardware wallet or another exchange), mark it as 'My wallet'. Otherwise, it will be treated as a taxable disposal."
                })
        
        # Sort by timestamp (newest first)
        items.sort(key=lambda x: str(x.get("timestamp", "")), reverse=True)
        
        # Deduplicate by tx_id
        seen_tx_ids = set()
        unique_items = []
        for item in items:
            tx_id = item.get("tx_id") or item.get("review_id")
            if tx_id and tx_id not in seen_tx_ids:
                seen_tx_ids.add(tx_id)
                unique_items.append(item)
        items = unique_items
        
        # Count stats
        pending_count = len([i for i in items if i.get("review_status") == "pending"])
        exchange_sends = len([i for i in items if i.get("source_type") == "exchange_transaction"])
        
        logger.info(f"Found {len(items)} unique reviews for user {user_id} ({exchange_sends} exchange sends)")
        
        return {
            "reviews": items,
            "count": len(items),
            "pending_count": pending_count,
            "exchange_sends_count": exchange_sends,
            "message": f"{pending_count} transactions need review. Connect wallets to auto-verify ownership." if pending_count > 0 else "All transactions verified.",
            "action_required": pending_count > 0
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
    Resolve a chain break review or exchange send transaction.
    
    - decision: "yes" = it's my wallet (internal transfer, no tax event)
    - decision: "no" = external transfer (taxable disposal event)
    - decision: "ignore" = skip for now
    
    P1: Auto-triggers recompute when linkage changes
    """
    try:
        if request.decision not in ["yes", "no", "ignore"]:
            raise HTTPException(
                status_code=400,
                detail="Decision must be 'yes', 'no', or 'ignore'"
            )
        
        # First, check if this is an exchange transaction
        exchange_tx = await db.exchange_transactions.find_one({
            "tx_id": request.review_id,
            "user_id": user["id"],
            "tx_type": {"$in": ["send", "withdrawal", "transfer"]}
        })
        
        if exchange_tx:
            # Handle exchange transaction resolution
            if request.decision == "yes":
                # Internal transfer - not taxable
                await db.exchange_transactions.update_one(
                    {"tx_id": request.review_id, "user_id": user["id"]},
                    {"$set": {
                        "chain_status": "linked",
                        "is_internal_transfer": True,
                        "resolved_at": datetime.now(timezone.utc).isoformat(),
                        "resolution_decision": "internal"
                    }}
                )
                return {
                    "success": True,
                    "message": "Marked as internal transfer (not taxable)",
                    "tx_id": request.review_id,
                    "chain_status": "linked"
                }
            elif request.decision == "no":
                # External send - taxable disposal
                await db.exchange_transactions.update_one(
                    {"tx_id": request.review_id, "user_id": user["id"]},
                    {"$set": {
                        "chain_status": "external",
                        "is_internal_transfer": False,
                        "resolved_at": datetime.now(timezone.utc).isoformat(),
                        "resolution_decision": "external"
                    }}
                )
                return {
                    "success": True,
                    "message": "Marked as external send (taxable disposal)",
                    "tx_id": request.review_id,
                    "chain_status": "external"
                }
            else:  # ignore
                await db.exchange_transactions.update_one(
                    {"tx_id": request.review_id, "user_id": user["id"]},
                    {"$set": {
                        "chain_status": "ignored",
                        "resolved_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                return {
                    "success": True,
                    "message": "Transaction ignored",
                    "tx_id": request.review_id
                }
        
        # Fall back to linkage engine for traditional chain break reviews
        result = await linkage_engine.resolve_review(
            review_id=request.review_id,
            user_id=user["id"],
            decision=request.decision,
            override_reason=request.override_reason
        )
        
        # P1: Auto-trigger recompute when linkage changes
        if request.decision in ["yes", "no"]:
            try:
                from persistent_tax_validation import hook_linkage_change
                recompute_result = await hook_linkage_change(
                    db, user["id"], f"review_resolved_{request.decision}"
                )
                result["recompute_triggered"] = True
                result["recompute_result"] = recompute_result
            except Exception as e:
                logger.warning(f"Failed to trigger recompute: {e}")
                result["recompute_triggered"] = False
        
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
    force: bool = False,
    user: dict = Depends(get_current_user)
):
    """
    Export tax events in Form 8949 compatible CSV format.
    
    Args:
        tax_year: Tax year to export
        validate: If True, run validation before export (default True)
        force: If True, skip validation and export anyway (use with caution)
    
    Returns:
        CSV file or validation errors if validation fails
    """
    try:
        import csv
        from tax_validation_service import tax_validation_service, TxClassification
        from beta_validation_harness import create_validation_harness
        
        # P0 ENFORCEMENT: Run full account validation before export
        if validate and not force:
            harness = create_validation_harness(db)
            report = await harness.validate_account(user["id"], tax_year)
            
            if not report.can_export:
                # BLOCK EXPORT - return detailed error
                return {
                    "error": "Export blocked - validation failed",
                    "can_export": False,
                    "validation_status": report.validation_status,
                    "blocked_reason": report.export_blocked_reason,
                    "critical_issues": report.critical_issues,
                    "high_issues": report.high_issues,
                    "unresolved_review_items": report.review_queue_count,
                    "invariants_failed": report.invariants_failed,
                    "message": "Resolve the following issues before exporting Form 8949",
                    "issues": [i.to_dict() for i in report.issues if i.severity.value in ["critical", "high"]],
                    "failed_invariants": [c.to_dict() for c in report.invariant_checks if not c.passed]
                }
        
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
        
        # Run record-level validation if enabled
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
                detail="Report not found. Run /api/custody/beta/validate first."
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



# ========================================
# P0: ORPHAN DISPOSAL ANALYSIS & FIXES
# ========================================

from orphan_disposal_fixer import OrphanDisposalAnalyzer, ReviewQueueAnalyzer, run_p0_analysis


@router.get("/analysis/orphan-disposals")
async def analyze_orphan_disposals(
    user: dict = Depends(get_current_user)
):
    """
    Analyze all assets for orphan disposal issues.
    
    Returns:
        Detailed analysis with root causes and recommended fixes
    """
    try:
        analyzer = OrphanDisposalAnalyzer(db)
        results = await analyzer.analyze_orphan_disposals(user["id"])
        
        return {
            "success": True,
            "analysis": results
        }
        
    except Exception as e:
        logger.error(f"Error analyzing orphan disposals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/analysis/review-queue-breakdown")
async def analyze_review_queue(
    user: dict = Depends(get_current_user)
):
    """
    Categorize review queue items by cause and frequency.
    
    Returns:
        Breakdown by category, asset, and status with recommendations
    """
    try:
        analyzer = ReviewQueueAnalyzer(db)
        results = await analyzer.categorize_review_queue(user["id"])
        
        return {
            "success": True,
            "analysis": results
        }
        
    except Exception as e:
        logger.error(f"Error analyzing review queue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/analysis/full-p0-report")
async def get_full_p0_report(
    user: dict = Depends(get_current_user)
):
    """
    Run complete P0 analysis: orphan disposals + review queue categorization.
    
    Returns:
        Combined analysis with all issues and recommendations
    """
    try:
        results = await run_p0_analysis(db, user["id"])
        
        # Save report to file
        import json
        report_path = f"/app/test_reports/p0_analysis_{user['id']}.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        return {
            "success": True,
            "report": results,
            "report_file": report_path
        }
        
    except Exception as e:
        logger.error(f"Error in P0 analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"P0 analysis failed: {str(e)}")


@router.post("/fix/create-proceeds-acquisitions")
async def create_proceeds_acquisitions(
    dry_run: bool = True,
    user: dict = Depends(get_current_user)
):
    """
    Create proceeds acquisition records from crypto sell proceeds.
    
    P1.5 Constraints enforced:
    - Linked source disposal (references the sell tx that generated proceeds)
    - Exact amount match (proceeds amount = acquisition amount)
    - Timestamp match (same as source disposal)
    - Price source tracking (e.g., "proceeds_from_BTC_sell")
    - Audit trail entry linking disposal → proceeds acquisition
    
    Args:
        dry_run: If True, show what would be created without actually creating
    
    Returns:
        List of proceeds acquisitions to create (or created if dry_run=False)
    """
    try:
        analyzer = OrphanDisposalAnalyzer(db)
        results = await analyzer.create_proceeds_acquisitions(user["id"], dry_run=dry_run)
        
        return {
            "success": True,
            "dry_run": dry_run,
            "proceeds_acquisitions_count": len(results["proceeds_acquisitions"]),
            "total_value": results["total_value"],
            "validation_errors": results["validation_errors"],
            "audit_entries_count": len(results["audit_entries"]),
            "proceeds_acquisitions": results["proceeds_acquisitions"][:20],  # First 20
            "message": f"{'Would create' if dry_run else 'Created'} {len(results['proceeds_acquisitions'])} proceeds acquisitions totaling ${results['total_value']:,.2f}"
        }
        
    except Exception as e:
        logger.error(f"Error creating proceeds acquisitions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")


# Legacy endpoint alias for backwards compatibility
@router.post("/fix/create-implicit-acquisitions")
async def create_implicit_acquisitions_legacy(
    dry_run: bool = True,
    user: dict = Depends(get_current_user)
):
    """
    DEPRECATED: Use /fix/create-proceeds-acquisitions instead.
    This endpoint is kept for backwards compatibility.
    """
    return await create_proceeds_acquisitions(dry_run, user)



# ========================================
# P1: PERSISTENT TAX VALIDATION
# ========================================

from persistent_tax_validation import (
    PersistentTaxValidationService,
    hook_linkage_change,
    hook_classification_change,
    add_validation_status_to_response
)


class CreateLotRequest(BaseModel):
    """Request to create a tax lot"""
    tx_id: str
    asset: str
    acquisition_date: str
    quantity: float
    cost_basis_per_unit: float
    source: str
    classification: str = "acquisition"
    price_source: str = "original"


class DisposeRequest(BaseModel):
    """Request to dispose from lots"""
    tx_id: str
    asset: str
    disposal_date: str
    quantity: float
    proceeds: float


@router.post("/tax-lots/create")
async def create_tax_lot(
    request: CreateLotRequest,
    user: dict = Depends(get_current_user)
):
    """Create a new tax lot (persisted to MongoDB)"""
    try:
        service = PersistentTaxValidationService(db)
        
        lot = await service.create_lot(
            user_id=user["id"],
            tx_id=request.tx_id,
            asset=request.asset,
            acquisition_date=datetime.fromisoformat(request.acquisition_date),
            quantity=request.quantity,
            cost_basis_per_unit=request.cost_basis_per_unit,
            source=request.source,
            classification=request.classification,
            price_source=request.price_source
        )
        
        return {"success": True, "lot": lot}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating lot: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create lot: {str(e)}")


@router.get("/tax-lots")
async def get_tax_lots(
    asset: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get all tax lots for the user"""
    try:
        service = PersistentTaxValidationService(db)
        lots = await service.get_lots(user["id"], asset)
        
        return {
            "success": True,
            "lots": lots,
            "count": len(lots)
        }
        
    except Exception as e:
        logger.error(f"Error getting lots: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get lots: {str(e)}")


@router.post("/tax-lots/dispose")
async def dispose_from_tax_lots(
    request: DisposeRequest,
    user: dict = Depends(get_current_user)
):
    """Dispose from tax lots using FIFO (persisted to MongoDB)"""
    try:
        service = PersistentTaxValidationService(db)
        
        disposal = await service.dispose_from_lots(
            user_id=user["id"],
            tx_id=request.tx_id,
            asset=request.asset,
            disposal_date=datetime.fromisoformat(request.disposal_date),
            quantity=request.quantity,
            proceeds=request.proceeds
        )
        
        return {"success": True, "disposal": disposal}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error disposing: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to dispose: {str(e)}")


@router.get("/tax-lots/disposals")
async def get_disposals(
    tax_year: Optional[int] = None,
    user: dict = Depends(get_current_user)
):
    """Get all disposals for the user"""
    try:
        service = PersistentTaxValidationService(db)
        disposals = await service.get_disposals(user["id"], tax_year)
        
        total_gain_loss = sum(d["gain_loss"] for d in disposals)
        
        return {
            "success": True,
            "disposals": disposals,
            "count": len(disposals),
            "total_gain_loss": total_gain_loss
        }
        
    except Exception as e:
        logger.error(f"Error getting disposals: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get disposals: {str(e)}")


@router.get("/tax-lots/balances")
async def get_asset_balances(
    user: dict = Depends(get_current_user)
):
    """Get current balances and cost basis for all assets"""
    try:
        service = PersistentTaxValidationService(db)
        balances = await service.get_all_balances(user["id"])
        
        return {
            "success": True,
            "balances": balances,
            "asset_count": len(balances)
        }
        
    except Exception as e:
        logger.error(f"Error getting balances: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get balances: {str(e)}")


@router.post("/tax-lots/recompute")
async def trigger_recompute(
    reason: str = "manual",
    user: dict = Depends(get_current_user)
):
    """Trigger full recomputation of tax data"""
    try:
        service = PersistentTaxValidationService(db)
        result = await service.trigger_full_recompute(user["id"], reason)
        
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Error triggering recompute: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger recompute: {str(e)}")


@router.get("/tax-lots/audit-trail")
async def get_lot_audit_trail(
    limit: int = 100,
    user: dict = Depends(get_current_user)
):
    """Get audit trail for tax lot operations"""
    try:
        service = PersistentTaxValidationService(db)
        entries = await service.get_audit_trail(user["id"], limit)
        
        return {
            "success": True,
            "audit_trail": entries,
            "count": len(entries)
        }
        
    except Exception as e:
        logger.error(f"Error getting audit trail: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get audit trail: {str(e)}")


@router.get("/validation-status")
async def get_user_validation_status(
    user: dict = Depends(get_current_user)
):
    """Get validation status for the current user"""
    try:
        service = PersistentTaxValidationService(db)
        status = await service.get_validation_status(user["id"])
        
        return {
            "success": True,
            "validation_status": status
        }
        
    except Exception as e:
        logger.error(f"Error getting validation status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get validation status: {str(e)}")



# ========================================
# P2: REVIEW QUEUE ENHANCEMENTS
# ========================================

from review_queue_enhancements import (
    WalletLinkSuggestionEngine,
    BulkResolutionService,
    ReviewQueueGroupingService
)


class BulkResolveRequest(BaseModel):
    """Request for bulk resolution"""
    review_ids: Optional[List[str]] = None
    category: Optional[str] = None
    destination_wallet: Optional[str] = None
    decision: str = "mine"  # "mine" or "external"
    reason: str = "bulk_resolution"


@router.get("/review-queue/suggestions")
async def get_wallet_link_suggestions(
    user: dict = Depends(get_current_user)
):
    """
    Get wallet link suggestions based on review queue patterns.
    
    Analyzes repeated destinations, transaction patterns, and known
    wallet signatures to suggest which wallets belong to the user.
    
    Returns suggestions grouped by confidence level.
    """
    try:
        engine = WalletLinkSuggestionEngine(db)
        suggestions = await engine.generate_suggestions(user["id"])
        
        return {
            "success": True,
            "suggestions": suggestions
        }
        
    except Exception as e:
        logger.error(f"Error generating suggestions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {str(e)}")


@router.post("/review-queue/bulk-resolve")
async def bulk_resolve_reviews(
    request: BulkResolveRequest,
    user: dict = Depends(get_current_user)
):
    """
    Bulk resolve multiple review items at once.
    
    Can resolve by:
    - Specific review IDs
    - Category (unknown_wallet, bridge_transfer, dust_amount)
    - Destination wallet address
    
    Decision:
    - "mine": Creates linkage edge (internal transfer, no tax event)
    - "external": Creates tax event (disposal)
    """
    try:
        service = BulkResolutionService(db)
        
        results = await service.bulk_resolve(
            user_id=user["id"],
            review_ids=request.review_ids,
            category=request.category,
            destination_wallet=request.destination_wallet,
            decision=request.decision,
            reason=request.reason
        )
        
        # Trigger recompute if any items were resolved
        if results["resolved_count"] > 0:
            try:
                from persistent_tax_validation import hook_linkage_change
                await hook_linkage_change(db, user["id"], "bulk_resolution")
            except Exception as e:
                logger.warning(f"Failed to trigger recompute: {e}")
        
        return {
            "success": True,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in bulk resolution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk resolution failed: {str(e)}")


@router.post("/review-queue/bulk-resolve-category/{category}")
async def bulk_resolve_by_category(
    category: str,
    decision: str = "mine",
    limit: int = 100,
    user: dict = Depends(get_current_user)
):
    """
    Resolve all review items of a specific category.
    
    Categories:
    - unknown_wallet: Unknown wallet interactions
    - bridge_transfer: Bridge/cross-chain transfers
    - dust_amount: Very small amounts (<$1)
    - dex_swap: DEX swap transactions
    - exchange_withdrawal: Exchange withdrawals
    
    Args:
        category: Category to resolve
        decision: "mine" or "external"
        limit: Maximum items to resolve (default 100)
    """
    try:
        service = BulkResolutionService(db)
        
        results = await service.bulk_resolve_by_category(
            user_id=user["id"],
            category=category,
            decision=decision,
            limit=limit
        )
        
        # Trigger recompute
        if results.get("resolved_count", 0) > 0:
            try:
                from persistent_tax_validation import hook_linkage_change
                await hook_linkage_change(db, user["id"], f"bulk_category_{category}")
            except Exception:
                pass
        
        return {
            "success": True,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error in category resolution: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Category resolution failed: {str(e)}")


@router.get("/review-queue/grouped")
async def get_grouped_review_queue(
    user: dict = Depends(get_current_user)
):
    """
    Get review queue items grouped by source, destination, asset, and amount range.
    
    Returns actionable groups with recommendations for bulk processing.
    """
    try:
        service = ReviewQueueGroupingService(db)
        grouped = await service.group_review_queue(user["id"])
        
        return {
            "success": True,
            "grouped": grouped
        }
        
    except Exception as e:
        logger.error(f"Error grouping review queue: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to group review queue: {str(e)}")


@router.post("/review-queue/apply-suggestion/{suggestion_id}")
async def apply_wallet_suggestion(
    suggestion_id: str,
    decision: str = "mine",
    user: dict = Depends(get_current_user)
):
    """
    Apply a wallet link suggestion to resolve related review items.
    
    This takes a suggestion from /review-queue/suggestions and applies
    the recommended action to all affected review items.
    """
    try:
        # First get the suggestion to find affected review IDs
        engine = WalletLinkSuggestionEngine(db)
        all_suggestions = await engine.generate_suggestions(user["id"])
        
        # Find the specific suggestion
        target_suggestion = None
        for s in all_suggestions.get("suggestions", []):
            if s.get("suggestion_id") == suggestion_id:
                target_suggestion = s
                break
        
        if not target_suggestion:
            raise HTTPException(status_code=404, detail="Suggestion not found")
        
        # Get affected review IDs
        affected_ids = target_suggestion.get("affected_review_ids", [])
        
        if not affected_ids:
            return {
                "success": False,
                "message": "No review items affected by this suggestion"
            }
        
        # Apply bulk resolution
        service = BulkResolutionService(db)
        results = await service.bulk_resolve(
            user_id=user["id"],
            review_ids=affected_ids,
            decision=decision,
            reason=f"suggestion_{suggestion_id}"
        )
        
        return {
            "success": True,
            "suggestion_applied": target_suggestion,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying suggestion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to apply suggestion: {str(e)}")


# ============================================================
# CONSTRAINED PROCEEDS ACQUISITION REMEDIATION ENDPOINTS
# ============================================================

class ProceedsRemediationRequest(BaseModel):
    """Request model for proceeds acquisition remediation"""
    candidate_tx_ids: Optional[List[str]] = None  # Specific tx_ids to fix (None = all)
    dry_run: bool = True  # Preview mode by default


class RollbackRequest(BaseModel):
    """Request model for rollback"""
    batch_id: str


@router.get("/proceeds/preview")
async def preview_proceeds_candidates(
    user: dict = Depends(get_current_user)
):
    """
    Preview all candidate proceeds acquisitions before applying.
    
    Shows:
    - Fixable disposals with proposed proceeds acquisitions
    - Non-fixable disposals with reasons they were skipped
    - Summary counts and total value
    
    This is a read-only operation that does not create any records.
    """
    try:
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
    """
    Apply constrained proceeds acquisition fixes.
    
    Requirements:
    - Only creates proceeds acquisition when linked to known source disposal
    - Requires: source_disposal_tx_id, proceeds_asset, exact_amount, timestamp, price_source
    - Tags all records as `derived_proceeds_acquisition`
    - All records are reversible via rollback
    
    Exclusions:
    - Unresolved wallet ownership (pending review queue)
    - Missing acquisition history
    - Inferred internal transfers
    - Bridge/DEX ambiguity without explicit proceeds leg
    
    Args:
        candidate_tx_ids: Specific disposal tx_ids to fix (None = all eligible)
        dry_run: If True (default), preview only without creating records
    
    Returns:
        Created records and rollback_batch_id for reversibility
    """
    try:
        service = ConstrainedProceedsService(db)
        results = await service.apply_fixes(
            user_id=user["id"],
            candidate_tx_ids=request.candidate_tx_ids,
            dry_run=request.dry_run
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
    """
    Rollback a batch of created proceeds acquisitions.
    
    Use the rollback_batch_id returned from /proceeds/apply to undo the changes.
    This removes all derived proceeds acquisition records from that batch.
    """
    try:
        service = ConstrainedProceedsService(db)
        results = await service.rollback_batch(
            user_id=user["id"],
            batch_id=request.batch_id
        )
        
        if not results["success"]:
            raise HTTPException(status_code=404, detail=results["message"])
        
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
    """
    List all rollback batches for the user.
    
    Returns batches that can be rolled back with their record counts and values.
    """
    try:
        service = ConstrainedProceedsService(db)
        batches = await service.list_rollback_batches(user["id"])
        
        return {
            "success": True,
            "batches": batches
        }
        
    except Exception as e:
        logger.error(f"Error listing rollback batches: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list batches: {str(e)}")


# ============================================================
# PRICE BACKFILL PIPELINE ENDPOINTS
# ============================================================

class PriceBackfillRequest(BaseModel):
    """Request model for price backfill"""
    tx_ids: Optional[List[str]] = None  # Specific tx_ids to backfill (None = all)
    dry_run: bool = True  # Preview mode by default
    allow_approximate: bool = True  # Include approximate matches


class BackfillRollbackRequest(BaseModel):
    """Request model for backfill rollback"""
    batch_id: str


@router.get("/price-backfill/preview")
async def preview_price_backfill(
    user: dict = Depends(get_current_user)
):
    """
    Preview price backfill for disposals missing USD valuation.
    
    Returns a dry-run report showing:
    - Total disposals missing price
    - Successfully backfillable (exact + approximate matches)
    - Still missing (no price data available)
    - Breakdown by valuation status, price source, and asset
    
    Valuation statuses:
    - exact: Price from exact transaction date
    - approximate: Price from nearest available date within 24h window
    - stablecoin: Fixed 1:1 USD peg
    - unavailable: No price data found
    """
    try:
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
            "results": [r.to_dict() for r in summary.results[:100]]  # Limit to first 100
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
    1. Fetches historical USD price at or nearest to transaction timestamp
    2. Stores: asset, timestamp_used, price_source, confidence
    3. Marks valuation as: exact, approximate, or unavailable
    4. Creates audit trail entry
    
    Only exact or policy-allowed approximate valuations enable downstream
    proceeds-acquisition creation.
    
    Args:
        tx_ids: Specific disposal tx_ids to backfill (None = all eligible)
        dry_run: If True (default), preview only without applying
        allow_approximate: If True, apply approximate matches too
    
    Returns:
        Applied records and backfill_batch_id for rollback capability
    """
    try:
        service = PriceBackfillService(db)
        results = await service.apply_backfill(
            user_id=user["id"],
            tx_ids=request.tx_ids,
            dry_run=request.dry_run,
            allow_approximate=request.allow_approximate
        )
        
        return {
            "success": True,
            "dry_run": results["dry_run"],
            "total_processed": results["total_processed"],
            "backfillable_count": results["backfillable_count"],
            "applied_count": results["applied_count"],
            "still_missing": results["still_missing"],
            "backfill_batch_id": results.get("backfill_batch_id"),
            "applied_records": results.get("applied_records", [])[:50],  # Limit response size
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
    
    Removes price data that was backfilled in the specified batch,
    reverting transactions to their original state (no price data).
    """
    try:
        service = PriceBackfillService(db)
        results = await service.rollback_backfill(
            user_id=user["id"],
            batch_id=request.batch_id
        )
        
        if not results["success"]:
            raise HTTPException(status_code=404, detail=results["message"])
        
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
    """
    List all price backfill batches for the user.
    
    Returns batches that can be rolled back with their record counts and values.
    """
    try:
        service = PriceBackfillService(db)
        batches = await service.list_backfill_batches(user["id"])
        
        return {
            "success": True,
            "batches": batches
        }
        
    except Exception as e:
        logger.error(f"Error listing backfill batches: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list batches: {str(e)}")


# ============================================================
# STAGED PROCEEDS APPLICATION ENDPOINTS
# ============================================================

class StagedApplyRequest(BaseModel):
    """Request model for staged proceeds application"""
    assets: Optional[List[str]] = None
    date_from: Optional[str] = None  # YYYY-MM-DD
    date_to: Optional[str] = None    # YYYY-MM-DD
    valuation_filter: str = "exact_only"  # exact_only, stablecoin_only, high_confidence, all_eligible
    min_confidence: float = 0.7
    max_time_delta_hours: Optional[float] = None
    exclude_wide_window: bool = True
    dry_run: bool = True
    force_override: bool = False  # Override safety blocks


@router.get("/proceeds/staged/stages")
async def get_application_stages(
    user: dict = Depends(get_current_user)
):
    """
    Get recommended application stages for proceeds acquisitions.
    
    Returns a plan for staged application with:
    - Stage 1: Exact + Stablecoin valuations (low risk, recommended first)
    - Stage 2: High-confidence approximate (medium risk)
    - Stage 3: Low-confidence approximate (high risk, requires manual review)
    """
    try:
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
    assets: Optional[str] = None,  # Comma-separated list
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    valuation_filter: str = "exact_only",
    min_confidence: float = 0.7
):
    """
    Preview staged proceeds application with filters.
    
    Groups candidates by valuation quality:
    - exact: Price from exact transaction date
    - stablecoin: Fixed 1:1 USD peg
    - high_confidence_approximate: Approximate with confidence >= 0.8
    - low_confidence_approximate: Approximate with lower confidence
    
    Args:
        assets: Comma-separated list of assets to filter (e.g., "BTC,ETH")
        date_from: Start date (YYYY-MM-DD)
        date_to: End date (YYYY-MM-DD)
        valuation_filter: exact_only, stablecoin_only, high_confidence, all_eligible
        min_confidence: Minimum confidence threshold (0.0-1.0)
    """
    try:
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
    """
    Apply proceeds acquisitions with staged controls.
    
    Safety Features:
    - Exact-valuation candidates recommended first
    - Low-confidence approximates blocked unless force_override=True
    - Wide-window approximates (>12h) blocked by default
    - Automatic validation after each batch
    - Returns delta metrics showing impact
    
    Args:
        assets: Filter by specific assets
        date_from/date_to: Filter by date range
        valuation_filter: exact_only, stablecoin_only, high_confidence, all_eligible
        min_confidence: Minimum confidence threshold
        max_time_delta_hours: Maximum time delta for approximate matches
        exclude_wide_window: Block wide-window (>12h) approximates
        dry_run: If True, preview only
        force_override: Override safety blocks (use with caution)
    
    Returns:
        StagedApplicationResult with validation delta showing:
        - orphan_disposals before/after
        - validation_status before/after
        - can_export before/after
        - new warnings/errors introduced
    """
    try:
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
    """
    Convenience endpoint: Apply only exact-valuation candidates.
    
    This is the safest application mode with highest confidence.
    Recommended as first stage of application.
    """
    try:
        asset_list = [a.strip().upper() for a in assets.split(",")] if assets else None
        
        service = StagedProceedsService(db)
        result = await service.apply_exact_only(
            user_id=user["id"],
            assets=asset_list,
            dry_run=dry_run
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
    """
    Convenience endpoint: Apply only stablecoin candidates.
    
    Stablecoins have 1:1 USD peg with confidence 1.0.
    """
    try:
        service = StagedProceedsService(db)
        result = await service.apply_stablecoins_only(
            user_id=user["id"],
            dry_run=dry_run
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
    """
    Convenience endpoint: Apply exact + high-confidence approximate.
    
    Includes:
    - Exact valuations
    - Stablecoin valuations
    - Approximate valuations with confidence >= 0.8
    """
    try:
        asset_list = [a.strip().upper() for a in assets.split(",")] if assets else None
        
        service = StagedProceedsService(db)
        result = await service.apply_high_confidence(
            user_id=user["id"],
            assets=asset_list,
            dry_run=dry_run
        )
        
        return {
            "success": True,
            "result": result.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Error applying high-confidence proceeds: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to apply: {str(e)}")

