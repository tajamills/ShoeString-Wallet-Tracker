"""Authentication routes - login, register, password reset, terms"""
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone, timedelta
import secrets
import logging
import os

from .dependencies import db, auth_service, get_current_user
from .models import (
    User, UserRegister, UserLogin, UserResponse, TokenResponse,
    PasswordResetRequest, PasswordResetConfirm
)
from email_service import (
    send_welcome_email, send_password_reset_email
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """Register a new user"""
    if not auth_service.validate_email(user_data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    is_valid, error_msg = auth_service.validate_password(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    existing_user = await db.users.find_one({"email": user_data.email.lower()})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=user_data.email.lower(),
        password_hash=auth_service.get_password_hash(user_data.password)
    )
    
    doc = user.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['last_usage_reset'] = doc['last_usage_reset'].isoformat()
    await db.users.insert_one(doc)
    
    access_token = auth_service.create_access_token(data={"sub": user.id})
    
    try:
        await send_welcome_email(user.email)
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")
    
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        subscription_tier=user.subscription_tier,
        daily_usage_count=user.daily_usage_count,
        analysis_count=user.analysis_count,
        created_at=user.created_at,
        terms_accepted=user.terms_accepted
    )
    
    return TokenResponse(access_token=access_token, user=user_response)


@router.post("/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Login user"""
    user = await db.users.find_one({"email": user_data.email.lower()})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not auth_service.verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    access_token = auth_service.create_access_token(data={"sub": user["id"]})
    
    created_at = datetime.fromisoformat(user["created_at"]) if isinstance(user["created_at"], str) else user["created_at"]
    
    user_response = UserResponse(
        id=user["id"],
        email=user["email"],
        subscription_tier=user["subscription_tier"],
        daily_usage_count=user["daily_usage_count"],
        analysis_count=user.get("analysis_count", 0),
        created_at=created_at,
        terms_accepted=user.get("terms_accepted", False)
    )
    
    return TokenResponse(access_token=access_token, user=user_response)


@router.post("/forgot-password")
async def forgot_password(request: PasswordResetRequest):
    """Request password reset - sends email with reset link"""
    user = await db.users.find_one({"email": request.email.lower()})
    
    if not user:
        return {"message": "If this email exists, a reset link has been sent."}
    
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    await db.password_resets.update_one(
        {"user_id": user["id"]},
        {
            "$set": {
                "user_id": user["id"],
                "token": reset_token,
                "expires_at": expires_at.isoformat(),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
        },
        upsert=True
    )
    
    try:
        await send_password_reset_email(user["email"], reset_token)
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
    
    return {"message": "If this email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(request: PasswordResetConfirm):
    """Reset password using token from email"""
    reset_record = await db.password_resets.find_one({"token": request.token})
    
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    expires_at = datetime.fromisoformat(reset_record["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        await db.password_resets.delete_one({"token": request.token})
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    is_valid, error_msg = auth_service.validate_password(request.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    new_hash = auth_service.get_password_hash(request.new_password)
    await db.users.update_one(
        {"id": reset_record["user_id"]},
        {"$set": {"password_hash": new_hash}}
    )
    
    await db.password_resets.delete_one({"token": request.token})
    
    return {"message": "Password successfully reset. You can now log in."}


@router.post("/accept-terms")
async def accept_terms(user: dict = Depends(get_current_user)):
    """Accept Terms of Service"""
    try:
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "terms_accepted": True,
                "terms_accepted_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        logger.info(f"User {user['id']} accepted Terms of Service")
        
        return {"message": "Terms accepted successfully", "terms_accepted": True}
    except Exception as e:
        logger.error(f"Error accepting terms: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to accept terms")


@router.get("/me")
async def get_current_user_info(user: dict = Depends(get_current_user)):
    """Get current user information with subscription details"""
    response = {
        "id": user["id"],
        "email": user["email"],
        "subscription_tier": user.get("subscription_tier", "free"),
        "subscription_status": user.get("subscription_status"),
        "daily_usage_count": user.get("daily_usage_count", 0),
        "analysis_count": user.get("analysis_count", 0),
        "created_at": user.get("created_at"),
        "terms_accepted": user.get("terms_accepted", False)
    }
    
    if user.get('stripe_subscription_id'):
        try:
            import stripe as stripe_lib
            stripe_lib.api_key = os.environ.get('STRIPE_API_KEY')
            
            subscription = stripe_lib.Subscription.retrieve(user['stripe_subscription_id'])
            response["subscription_details"] = {
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "status": subscription.status
            }
        except Exception as e:
            logger.error(f"Failed to fetch subscription details: {str(e)}")
    
    return response


@router.post("/downgrade")
async def downgrade_subscription(
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Downgrade user subscription tier and cancel Stripe subscription"""
    try:
        body = await request.json()
        new_tier = body.get('new_tier')
        
        if new_tier not in ['free', 'premium', 'pro']:
            raise HTTPException(status_code=400, detail="Invalid tier")
        
        current_tier = user.get('subscription_tier')
        
        valid_downgrades = {
            'pro': 'premium',
            'premium': 'free'
        }
        
        if current_tier not in valid_downgrades:
            raise HTTPException(status_code=400, detail="Cannot downgrade from current tier")
        
        if new_tier != valid_downgrades[current_tier]:
            raise HTTPException(status_code=400, detail="Invalid downgrade path")
        
        if new_tier == 'free' and user.get('stripe_subscription_id'):
            try:
                import stripe as stripe_lib
                stripe_lib.api_key = os.environ.get('STRIPE_API_KEY')
                
                stripe_lib.Subscription.modify(
                    user['stripe_subscription_id'],
                    cancel_at_period_end=True
                )
                logger.info(f"Canceled Stripe subscription {user['stripe_subscription_id']} for user {user['id']}")
            except Exception as e:
                logger.error(f"Failed to cancel Stripe subscription: {str(e)}")
        
        update_data = {
            "subscription_tier": new_tier,
            "daily_usage_count": 0
        }
        
        if new_tier == 'free':
            update_data["subscription_status"] = "canceled"
        
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": update_data}
        )
        
        logger.info(f"User {user['id']} downgraded from {current_tier} to {new_tier}")
        
        return {"message": "Subscription downgraded successfully", "new_tier": new_tier}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Downgrade error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to downgrade subscription")
