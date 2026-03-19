"""Affiliate routes - registration, info, validation, admin reports"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime, timezone
import os
import logging

from .dependencies import db, get_current_user, get_current_quarter
from .models import Affiliate, AffiliateRegisterRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/affiliate", tags=["Affiliates"])


@router.post("/register")
async def register_affiliate(
    request: AffiliateRegisterRequest,
    user: dict = Depends(get_current_user)
):
    """Register as an affiliate"""
    try:
        existing = await db.affiliates.find_one({"user_id": user["id"]})
        if existing:
            raise HTTPException(status_code=400, detail="You are already registered as an affiliate")
        
        code = request.affiliate_code.upper().strip()
        if len(code) < 3 or len(code) > 20:
            raise HTTPException(status_code=400, detail="Affiliate code must be 3-20 characters")
        
        code_exists = await db.affiliates.find_one({"affiliate_code": code})
        if code_exists:
            raise HTTPException(status_code=400, detail="This affiliate code is already taken")
        
        affiliate = Affiliate(
            user_id=user["id"],
            affiliate_code=code,
            email=user["email"],
            name=request.name,
            paypal_email=request.paypal_email
        )
        
        doc = affiliate.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.affiliates.insert_one(doc)
        
        logger.info(f"New affiliate registered: {code} by user {user['id']}")
        
        return {
            "message": "Successfully registered as affiliate",
            "affiliate_code": code,
            "share_link": f"Use code '{code}' for $10 off!"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering affiliate: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to register as affiliate")


@router.get("/me")
async def get_my_affiliate_info(user: dict = Depends(get_current_user)):
    """Get current user's affiliate information"""
    try:
        affiliate = await db.affiliates.find_one(
            {"user_id": user["id"]},
            {"_id": 0}
        )
        
        if not affiliate:
            return {"is_affiliate": False}
        
        referrals = await db.affiliate_referrals.find(
            {"affiliate_id": affiliate["id"]},
            {"_id": 0}
        ).sort("created_at", -1).limit(10).to_list(10)
        
        return {
            "is_affiliate": True,
            "affiliate_code": affiliate["affiliate_code"],
            "name": affiliate["name"],
            "total_earnings": affiliate["total_earnings"],
            "pending_earnings": affiliate["pending_earnings"],
            "referral_count": affiliate["referral_count"],
            "paypal_email": affiliate.get("paypal_email"),
            "recent_referrals": referrals,
            "created_at": affiliate["created_at"]
        }
        
    except Exception as e:
        logger.error(f"Error getting affiliate info: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get affiliate info")


@router.get("/validate/{code}")
async def validate_affiliate_code(code: str):
    """Validate an affiliate code (public endpoint)"""
    try:
        affiliate = await db.affiliates.find_one({
            "affiliate_code": code.upper(),
            "is_active": True
        })
        
        if affiliate:
            return {
                "valid": True,
                "discount": 10.0,
                "message": f"Code '{code.upper()}' applied! You'll get $10 off."
            }
        else:
            return {
                "valid": False,
                "discount": 0,
                "message": "Invalid affiliate code"
            }
            
    except Exception as e:
        logger.error(f"Error validating affiliate code: {str(e)}")
        return {"valid": False, "discount": 0, "message": "Error validating code"}


@router.put("/update")
async def update_affiliate_info(
    paypal_email: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Update affiliate payment info"""
    try:
        result = await db.affiliates.update_one(
            {"user_id": user["id"]},
            {"$set": {"paypal_email": paypal_email}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Affiliate not found")
        
        return {"message": "Affiliate info updated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating affiliate: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update affiliate info")


@router.get("/admin/report")
async def get_affiliate_payout_report(
    quarter: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Get affiliate payout report for a quarter (Admin only)"""
    try:
        admin_emails = os.environ.get('ADMIN_EMAILS', '').split(',')
        if user['email'] not in admin_emails and user['email'] != 'admin@cryptobagtracker.io':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        if not quarter:
            quarter = get_current_quarter()
        
        pipeline = [
            {"$match": {"quarter": quarter, "paid_out": False}},
            {"$group": {
                "_id": "$affiliate_id",
                "affiliate_code": {"$first": "$affiliate_code"},
                "total_earned": {"$sum": "$amount_earned"},
                "referral_count": {"$sum": 1},
                "referral_ids": {"$push": "$id"}
            }},
            {"$sort": {"total_earned": -1}}
        ]
        
        results = await db.affiliate_referrals.aggregate(pipeline).to_list(100)
        
        report = []
        total_payout = 0
        
        for item in results:
            affiliate = await db.affiliates.find_one(
                {"id": item["_id"]},
                {"_id": 0, "email": 1, "name": 1, "paypal_email": 1, "affiliate_code": 1}
            )
            
            if affiliate:
                report.append({
                    "affiliate_code": affiliate["affiliate_code"],
                    "name": affiliate["name"],
                    "email": affiliate["email"],
                    "paypal_email": affiliate.get("paypal_email", "NOT SET"),
                    "referral_count": item["referral_count"],
                    "amount_owed": item["total_earned"],
                    "referral_ids": item["referral_ids"]
                })
                total_payout += item["total_earned"]
        
        return {
            "quarter": quarter,
            "total_affiliates": len(report),
            "total_payout": total_payout,
            "affiliates": report,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating payout report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate report")


@router.post("/admin/mark-paid")
async def mark_affiliates_paid(
    quarter: str,
    affiliate_ids: List[str],
    user: dict = Depends(get_current_user)
):
    """Mark affiliate referrals as paid (Admin only)"""
    try:
        admin_emails = os.environ.get('ADMIN_EMAILS', '').split(',')
        if user['email'] not in admin_emails and user['email'] != 'admin@cryptobagtracker.io':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        now = datetime.now(timezone.utc).isoformat()
        
        result = await db.affiliate_referrals.update_many(
            {
                "quarter": quarter,
                "affiliate_id": {"$in": affiliate_ids},
                "paid_out": False
            },
            {
                "$set": {
                    "paid_out": True,
                    "paid_out_date": now
                }
            }
        )
        
        for aff_id in affiliate_ids:
            paid_amount = await db.affiliate_referrals.count_documents({
                "affiliate_id": aff_id,
                "quarter": quarter,
                "paid_out": True,
                "paid_out_date": now
            }) * 10.0
            
            await db.affiliates.update_one(
                {"id": aff_id},
                {"$inc": {"pending_earnings": -paid_amount}}
            )
        
        logger.info(f"Admin marked {result.modified_count} referrals as paid for {quarter}")
        
        return {
            "message": f"Marked {result.modified_count} referrals as paid",
            "quarter": quarter
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking affiliates paid: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to mark as paid")
