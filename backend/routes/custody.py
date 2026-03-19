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
        
        address = request.address.strip().lower()
        if not address.startswith('0x') or len(address) != 42:
            raise HTTPException(
                status_code=400,
                detail="Invalid EVM address format. Must start with 0x and be 42 characters."
            )
        
        supported_chains = ['ethereum', 'polygon', 'arbitrum', 'bsc', 'base', 'optimism']
        if request.chain not in supported_chains:
            raise HTTPException(
                status_code=400,
                detail=f"Chain not supported for custody analysis. Supported: {', '.join(supported_chains)}"
            )
        
        result = custody_service.analyze_chain_of_custody(
            address=address,
            chain=request.chain,
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
