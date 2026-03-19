from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import logging
import json
import secrets
import sentry_sdk
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone, timedelta
from wallet_service import WalletService
from auth_service import AuthService
from stripe_service import StripeService
from multi_chain_service import MultiChainService
from multi_chain_service_v2 import multi_chain_service_v2  # New refactored service
from tax_report_service import tax_report_service
from email_service import send_welcome_email, send_password_reset_email, send_subscription_upgraded_email, send_subscription_expired_email, send_subscription_expiring_email
from fastapi.responses import Response


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Initialize Sentry for error monitoring
SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.2,  # 20% of transactions for performance monitoring
        environment=os.environ.get("ENVIRONMENT", "production"),
        send_default_pii=False,  # Don't send PII by default
    )
    logging.info("Sentry initialized for error monitoring")

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class WalletAnalysisRequest(BaseModel):
    address: str
    chain: str = "ethereum"  # ethereum, bitcoin, polygon, bsc, arbitrum
    start_date: Optional[str] = None  # Format: YYYY-MM-DD
    end_date: Optional[str] = None    # Format: YYYY-MM-DD

class SavedWallet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    address: str
    nickname: str
    chain: str  # ethereum, bitcoin, polygon, bsc, arbitrum
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SavedWalletCreate(BaseModel):
    address: str
    nickname: str
    chain: str = "ethereum"

class ChainRequest(BaseModel):
    chain_name: str
    reason: Optional[str] = None

class WalletAnalysisResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str
    chain: Optional[str] = None
    totalEthSent: float
    totalEthReceived: float
    totalGasFees: float
    currentBalance: float  # Current wallet balance (cannot be negative)
    netEth: float  # Keep for backward compatibility
    netFlow: float  # Flow calculation (can be negative)
    outgoingTransactionCount: int
    incomingTransactionCount: int
    tokensSent: Dict[str, float]
    tokensReceived: Dict[str, float]
    recentTransactions: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # USD values
    current_price_usd: Optional[float] = None
    total_value_usd: Optional[float] = None
    total_received_usd: Optional[float] = None
    total_sent_usd: Optional[float] = None
    total_gas_fees_usd: Optional[float] = None
    # Tax data (Premium/Pro feature)
    tax_data: Optional[Dict[str, Any]] = None

# Initialize services
wallet_service = WalletService()
multi_chain_service = MultiChainService()
auth_service = AuthService()
stripe_service = StripeService()
security = HTTPBearer()

# User Models
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    subscription_tier: str = "free"  # free, unlimited
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    subscription_status: Optional[str] = None  # active, canceled, past_due, etc.
    daily_usage_count: int = 0
    analysis_count: int = 0  # Total analyses ever done
    last_usage_reset: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    terms_accepted: bool = False
    terms_accepted_at: Optional[datetime] = None

class UserRegister(BaseModel):
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

class UserResponse(BaseModel):
    id: str
    email: str
    subscription_tier: str
    daily_usage_count: int
    analysis_count: int = 0
    created_at: datetime
    terms_accepted: bool = False

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str  # Stripe session_id
    amount: float
    currency: str
    status: str  # pending, paid, failed, expired
    payment_status: str  # Stripe payment_status
    subscription_tier: str
    affiliate_code: Optional[str] = None  # Affiliate code used
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: Optional[datetime] = None

# Affiliate Models
class Affiliate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    affiliate_code: str  # Unique code like "JOHN10" or username
    email: str
    name: str
    paypal_email: Optional[str] = None  # For payouts
    total_earnings: float = 0.0
    pending_earnings: float = 0.0  # Not yet paid out
    referral_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

class AffiliateReferral(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    affiliate_id: str
    affiliate_code: str
    customer_user_id: str
    customer_email: str
    amount_earned: float = 10.0  # $10 per referral
    customer_discount: float = 10.0  # $10 off for customer
    payment_id: str  # Link to payment
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    paid_out: bool = False
    paid_out_date: Optional[datetime] = None
    quarter: str  # e.g., "2026-Q1"

class AffiliateRegisterRequest(BaseModel):
    affiliate_code: str
    name: str
    paypal_email: Optional[str] = None

class UpgradeRequest(BaseModel):
    tier: str  # "premium" or "pro"

# Auth dependency
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current authenticated user from JWT token"""
    token = credentials.credentials
    payload = auth_service.decode_token(token)
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

async def check_usage_limit(user: dict = Depends(get_current_user)) -> dict:
    """Check if user has exceeded their daily usage limit"""
    # Reset daily count if it's a new day
    last_reset = user.get("last_usage_reset")
    if isinstance(last_reset, str):
        # Handle ISO string - ensure timezone awareness
        last_reset = datetime.fromisoformat(last_reset.replace('Z', '+00:00'))
    
    # Ensure timezone-awareness for comparison
    if last_reset and last_reset.tzinfo is None:
        last_reset = last_reset.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    if last_reset and (now - last_reset).days >= 1:
        # Reset usage count
        await db.users.update_one(
            {"id": user["id"]},
            {
                "$set": {
                    "daily_usage_count": 0,
                    "last_usage_reset": now.isoformat()
                }
            }
        )
        user["daily_usage_count"] = 0
    
    # Check limits based on tier - FREE gets 1 total analysis, UNLIMITED gets unlimited
    tier = user.get("subscription_tier", "free")
    
    if tier == "free":
        # Free users get 1 analysis total (not daily)
        total_analyses = user.get("analysis_count", 0)
        if total_analyses >= 1:
            raise HTTPException(
                status_code=429,
                detail="You've used your free analysis. Upgrade to Unlimited for unlimited analyses."
            )
    # Unlimited, premium, pro all get unlimited
    
    return user

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

# Authentication Routes
@api_router.post("/auth/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """Register a new user"""
    # Validate email
    if not auth_service.validate_email(user_data.email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    
    # Validate password
    is_valid, error_msg = auth_service.validate_password(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_data.email.lower()})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user = User(
        email=user_data.email.lower(),
        password_hash=auth_service.get_password_hash(user_data.password)
    )
    
    # Store in database
    doc = user.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    doc['last_usage_reset'] = doc['last_usage_reset'].isoformat()
    await db.users.insert_one(doc)
    
    # Generate token
    access_token = auth_service.create_access_token(data={"sub": user.id})
    
    # Send welcome email (async, non-blocking)
    try:
        await send_welcome_email(user.email)
    except Exception as e:
        logger.error(f"Failed to send welcome email: {e}")
        # Don't fail registration if email fails
    
    # Return response
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

@api_router.post("/auth/forgot-password")
async def forgot_password(request: PasswordResetRequest):
    """Request password reset - sends email with reset link"""
    user = await db.users.find_one({"email": request.email.lower()})
    
    # Always return success to prevent email enumeration
    if not user:
        return {"message": "If this email exists, a reset link has been sent."}
    
    # Generate secure reset token
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    # Store reset token
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
    
    # Send reset email
    try:
        await send_password_reset_email(user["email"], reset_token)
    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
    
    return {"message": "If this email exists, a reset link has been sent."}

@api_router.post("/auth/reset-password")
async def reset_password(request: PasswordResetConfirm):
    """Reset password using token from email"""
    # Find valid reset token
    reset_record = await db.password_resets.find_one({"token": request.token})
    
    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    # Check expiration
    expires_at = datetime.fromisoformat(reset_record["expires_at"])
    if datetime.now(timezone.utc) > expires_at:
        await db.password_resets.delete_one({"token": request.token})
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    # Validate new password
    is_valid, error_msg = auth_service.validate_password(request.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Update password
    new_hash = auth_service.get_password_hash(request.new_password)
    await db.users.update_one(
        {"id": reset_record["user_id"]},
        {"$set": {"password_hash": new_hash}}
    )
    
    # Delete used token
    await db.password_resets.delete_one({"token": request.token})
    
    return {"message": "Password successfully reset. You can now log in."}

@api_router.post("/auth/login", response_model=TokenResponse)
async def login(user_data: UserLogin):
    """Login user"""
    # Find user
    user = await db.users.find_one({"email": user_data.email.lower()})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Verify password
    if not auth_service.verify_password(user_data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Generate token
    access_token = auth_service.create_access_token(data={"sub": user["id"]})
    
    # Parse dates
    created_at = datetime.fromisoformat(user["created_at"]) if isinstance(user["created_at"], str) else user["created_at"]
    
    # Return response
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

@api_router.post("/auth/accept-terms")
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

@api_router.get("/auth/me")
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
    
    # Get subscription details from Stripe if exists
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

@api_router.post("/auth/downgrade")
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
        
        # Validate downgrade path
        valid_downgrades = {
            'pro': 'premium',
            'premium': 'free'
        }
        
        if current_tier not in valid_downgrades:
            raise HTTPException(status_code=400, detail="Cannot downgrade from current tier")
        
        if new_tier != valid_downgrades[current_tier]:
            raise HTTPException(status_code=400, detail="Invalid downgrade path")
        
        # Cancel Stripe subscription if downgrading to free
        if new_tier == 'free' and user.get('stripe_subscription_id'):
            try:
                import stripe as stripe_lib
                stripe_lib.api_key = os.environ.get('STRIPE_API_KEY')
                
                # Cancel subscription at period end (user keeps access until end of billing period)
                stripe_lib.Subscription.modify(
                    user['stripe_subscription_id'],
                    cancel_at_period_end=True
                )
                logger.info(f"Canceled Stripe subscription {user['stripe_subscription_id']} for user {user['id']}")
            except Exception as e:
                logger.error(f"Failed to cancel Stripe subscription: {str(e)}")
                # Continue with downgrade even if Stripe cancellation fails
        
        # Update user tier
        update_data = {
            "subscription_tier": new_tier,
            "daily_usage_count": 0
        }
        
        # Clear subscription data if downgrading to free
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

# Payment Routes
class CheckoutRequest(BaseModel):
    tier: str
    origin_url: str  # Frontend origin URL
    affiliate_code: Optional[str] = None  # Optional affiliate code for discount

def get_current_quarter():
    """Get current quarter string like '2026-Q1'"""
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    return f"{now.year}-Q{quarter}"

@api_router.post("/payments/create-upgrade")
async def create_upgrade_payment(
    checkout_request: CheckoutRequest,
    http_request: Request,
    user: dict = Depends(get_current_user)
):
    """Create Stripe subscription checkout session for upgrade"""
    try:
        # Get Stripe Price ID from environment - now just unlimited yearly
        price_id = os.environ.get('STRIPE_PRICE_ID_UNLIMITED')
        
        # Fallback to old price IDs if unlimited not set
        if not price_id:
            price_id = os.environ.get('STRIPE_PRICE_ID_PRO') or os.environ.get('STRIPE_PRICE_ID_PREMIUM')
        
        if not price_id:
            raise HTTPException(status_code=500, detail="Price ID not configured")
        
        # Check if user already has an active subscription
        current_tier = user.get('subscription_tier', 'free')
        subscription_status = user.get('subscription_status')
        
        # Prevent duplicate subscription purchases
        if current_tier in ['unlimited', 'premium', 'pro'] and subscription_status == 'active':
            raise HTTPException(
                status_code=400, 
                detail="You already have an active subscription"
            )
        
        # Validate affiliate code if provided
        affiliate = None
        coupon_id = None
        if checkout_request.affiliate_code:
            affiliate = await db.affiliates.find_one({
                "affiliate_code": checkout_request.affiliate_code.upper(),
                "is_active": True
            })
            if affiliate:
                # Don't allow self-referral
                if affiliate['user_id'] == user['id']:
                    raise HTTPException(status_code=400, detail="You cannot use your own affiliate code")
                
                # Create or get Stripe coupon for $10 off
                try:
                    import stripe as stripe_lib
                    stripe_lib.api_key = os.environ.get('STRIPE_API_KEY')
                    
                    # Try to retrieve existing coupon or create new one
                    coupon_id = "AFFILIATE10"
                    try:
                        stripe_lib.Coupon.retrieve(coupon_id)
                    except:
                        stripe_lib.Coupon.create(
                            id=coupon_id,
                            amount_off=1000,  # $10.00 in cents
                            currency="usd",
                            duration="once",
                            name="Affiliate Discount - $10 Off"
                        )
                except Exception as e:
                    logger.warning(f"Could not create/get coupon: {str(e)}")
        
        # Initialize Stripe checkout
        host_url = str(http_request.base_url)
        stripe_service.initialize_checkout(host_url)
        
        # Build success and cancel URLs from frontend origin
        success_url = f"{checkout_request.origin_url}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{checkout_request.origin_url}"
        
        # Create metadata for tracking
        metadata = {
            "user_id": user["id"],
            "tier": "unlimited",
            "email": user["email"]
        }
        
        # Add affiliate code to metadata if present
        if affiliate:
            metadata["affiliate_code"] = checkout_request.affiliate_code.upper()
            metadata["affiliate_id"] = affiliate["id"]
        
        # Create Stripe subscription checkout session with optional coupon
        import stripe as stripe_lib
        stripe_lib.api_key = os.environ.get('STRIPE_API_KEY')
        
        session_params = {
            'payment_method_types': ['card'],
            'line_items': [{
                'price': price_id,
                'quantity': 1,
            }],
            'mode': 'subscription',
            'success_url': success_url,
            'cancel_url': cancel_url,
            'metadata': metadata,
            'allow_promotion_codes': False if coupon_id else True,
            'billing_address_collection': 'auto',
        }
        
        if user.get("stripe_customer_id"):
            session_params['customer'] = user["stripe_customer_id"]
        else:
            session_params['customer_email'] = user["email"]
        
        # Apply affiliate coupon if valid
        if coupon_id and affiliate:
            session_params['discounts'] = [{'coupon': coupon_id}]
        
        session = stripe_lib.checkout.Session.create(**session_params)
        
        # Store payment transaction in database
        payment = Payment(
            user_id=user["id"],
            session_id=session.id,
            amount=100.88 if not affiliate else 90.88,  # $10 off with affiliate
            currency="usd",
            status="pending",
            payment_status="unpaid",
            subscription_tier="unlimited",
            affiliate_code=checkout_request.affiliate_code.upper() if affiliate else None
        )
        
        doc = payment.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        if doc.get('confirmed_at'):
            doc['confirmed_at'] = doc['confirmed_at'].isoformat()
        
        await db.payment_transactions.insert_one(doc)
        
        logger.info(f"Stripe subscription checkout created for user {user['id']}: {session.id}")
        
        return {
            "url": session.url,
            "session_id": session.id,
            "affiliate_applied": affiliate is not None,
            "discount": 10.0 if affiliate else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create Stripe checkout: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment creation failed: {str(e)}")

@api_router.post("/admin/test-email")
async def send_test_email(
    request: Request,
    email_type: str = "renewal",
    to_email: str = None,
    user: dict = Depends(get_current_user)
):
    """
    Send a test email for verification.
    
    email_type: "renewal", "expired", "upgraded", "welcome", "reset"
    to_email: Email address to send to (defaults to authenticated user)
    """
    user_email = to_email or user.get("email")
    
    if not user_email:
        raise HTTPException(status_code=400, detail="No email address provided")
    
    try:
        if email_type == "renewal":
            result = await send_subscription_expiring_email(user_email, days_remaining=3, tier="unlimited")
        elif email_type == "expired":
            result = await send_subscription_expired_email(user_email, tier="unlimited")
        elif email_type == "upgraded":
            result = await send_subscription_upgraded_email(user_email, tier="unlimited")
        elif email_type == "welcome":
            result = await send_welcome_email(user_email)
        elif email_type == "reset":
            result = await send_password_reset_email(user_email, reset_token="TEST-TOKEN-12345")
        else:
            raise HTTPException(status_code=400, detail=f"Unknown email type: {email_type}")
        
        return {"status": "sent", "email_type": email_type, "to": user_email, "result": result}
    
    except Exception as e:
        logger.error(f"Failed to send test email: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/payments/webhook/stripe")
@api_router.post("/webhook")  # Alias for Stripe dashboard config
async def handle_stripe_webhook(request: Request):
    """Handle Stripe webhook for subscriptions"""
    try:
        # Get request body and signature
        body = await request.body()
        signature = request.headers.get("stripe-signature", "")
        
        # Parse webhook with Stripe library
        import stripe as stripe_lib
        stripe_lib.api_key = os.environ.get('STRIPE_API_KEY')
        webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        
        try:
            event = stripe_lib.Webhook.construct_event(
                body, signature, webhook_secret
            )
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid payload")
        except stripe_lib.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)}")
            raise HTTPException(status_code=400, detail="Invalid signature")
        
        event_type = event['type']
        logger.info(f"Stripe webhook received: {event_type}")
        
        # Handle checkout.session.completed (initial subscription creation)
        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            session_id = session['id']
            customer_id = session.get('customer')
            subscription_id = session.get('subscription')
            metadata = session.get('metadata', {})
            
            user_id = metadata.get('user_id')
            tier = metadata.get('tier')
            
            if user_id and tier and subscription_id:
                # Update user with subscription info
                await db.users.update_one(
                    {"id": user_id},
                    {
                        "$set": {
                            "subscription_tier": tier,
                            "stripe_customer_id": customer_id,
                            "stripe_subscription_id": subscription_id,
                            "subscription_status": "active",
                            "daily_usage_count": 0,
                            "last_usage_reset": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                # Update payment transaction
                await db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "status": "completed",
                            "payment_status": "paid",
                            "confirmed_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                # Handle affiliate referral if present
                affiliate_code = metadata.get('affiliate_code')
                affiliate_id = metadata.get('affiliate_id')
                
                if affiliate_code and affiliate_id:
                    # Get customer email
                    customer_email = metadata.get('email', '')
                    
                    # Create referral record
                    referral = AffiliateReferral(
                        affiliate_id=affiliate_id,
                        affiliate_code=affiliate_code,
                        customer_user_id=user_id,
                        customer_email=customer_email,
                        amount_earned=10.0,
                        customer_discount=10.0,
                        payment_id=session_id,
                        quarter=get_current_quarter()
                    )
                    
                    ref_doc = referral.model_dump()
                    ref_doc['created_at'] = ref_doc['created_at'].isoformat()
                    await db.affiliate_referrals.insert_one(ref_doc)
                    
                    # Update affiliate earnings
                    await db.affiliates.update_one(
                        {"id": affiliate_id},
                        {
                            "$inc": {
                                "total_earnings": 10.0,
                                "pending_earnings": 10.0,
                                "referral_count": 1
                            }
                        }
                    )
                    
                    logger.info(f"Affiliate {affiliate_code} earned $10 for referral of user {user_id}")
                
                logger.info(f"User {user_id} subscribed to {tier} (subscription: {subscription_id})")
                
                # Send subscription upgrade confirmation email
                try:
                    user = await db.users.find_one({"id": user_id})
                    if user and user.get('email'):
                        await send_subscription_upgraded_email(user['email'], tier)
                        logger.info(f"Sent subscription upgrade email to {user['email']}")
                except Exception as email_err:
                    logger.error(f"Failed to send upgrade email: {str(email_err)}")
        
        # Handle customer.subscription.updated (subscription changes)
        elif event_type == 'customer.subscription.updated':
            subscription = event['data']['object']
            subscription_id = subscription['id']
            status = subscription['status']
            
            # Find user by subscription_id
            user = await db.users.find_one({"stripe_subscription_id": subscription_id})
            
            if user:
                update_data = {"subscription_status": status}
                
                # If subscription canceled or past_due, downgrade to free
                if status in ['canceled', 'unpaid']:
                    update_data["subscription_tier"] = "free"
                    logger.info(f"User {user['id']} subscription {status}, downgraded to free")
                
                await db.users.update_one(
                    {"id": user["id"]},
                    {"$set": update_data}
                )
        
        # Handle customer.subscription.deleted (subscription canceled)
        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            subscription_id = subscription['id']
            
            # Find user and downgrade to free
            user = await db.users.find_one({"stripe_subscription_id": subscription_id})
            
            if user:
                await db.users.update_one(
                    {"id": user["id"]},
                    {
                        "$set": {
                            "subscription_tier": "free",
                            "subscription_status": "canceled",
                            "daily_usage_count": 0
                        }
                    }
                )
                logger.info(f"User {user['id']} subscription canceled, downgraded to free")
                
                # Send subscription expired email
                try:
                    if user.get('email'):
                        old_tier = user.get('subscription_tier', 'premium')
                        await send_subscription_expired_email(user['email'], old_tier)
                        logger.info(f"Sent subscription expired email to {user['email']}")
                except Exception as email_err:
                    logger.error(f"Failed to send expired email: {str(email_err)}")
        
        # Handle invoice.upcoming - Stripe sends this ~3 days before renewal
        elif event_type == 'invoice.upcoming':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')
            
            if subscription_id:
                user = await db.users.find_one({"stripe_subscription_id": subscription_id})
                if user:
                    # Calculate days until renewal
                    next_payment_date = invoice.get('next_payment_attempt')
                    if next_payment_date:
                        days_remaining = max(1, (datetime.fromtimestamp(next_payment_date, tz=timezone.utc) - datetime.now(timezone.utc)).days)
                    else:
                        days_remaining = 3  # Default if not available
                    
                    # Send our custom expiring email
                    try:
                        tier = user.get("subscription_tier", "premium")
                        await send_subscription_expiring_email(user['email'], days_remaining, tier)
                        logger.info(f"Sent upcoming renewal email to {user['email']} - {days_remaining} days")
                    except Exception as email_err:
                        logger.error(f"Failed to send upcoming email: {str(email_err)}")
        
        # Handle invoice.payment_failed
        elif event_type == 'invoice.payment_failed':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')
            
            if subscription_id:
                user = await db.users.find_one({"stripe_subscription_id": subscription_id})
                if user:
                    await db.users.update_one(
                        {"id": user["id"]},
                        {"$set": {"subscription_status": "past_due"}}
                    )
                    logger.warning(f"Payment failed for user {user['id']}")
        
        return {"status": "success"}
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Stripe webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


# NOTE: The check-expiring-subscriptions cron endpoint has been removed.
# Subscription expiration warnings are now handled by Stripe webhooks (invoice.upcoming event)
# See the /webhook endpoint above for the implementation.


@api_router.get("/payments/status/{session_id}")
async def get_payment_status(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """Check Stripe checkout session status"""
    try:
        # Get payment from database
        payment_doc = await db.payment_transactions.find_one(
            {"session_id": session_id, "user_id": user["id"]},
            {"_id": 0}
        )
        
        if not payment_doc:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # Check with Stripe for latest status
        try:
            checkout_status = await stripe_service.get_checkout_status(session_id)
            
            # Update database if payment completed and not already processed
            if checkout_status.payment_status == "paid" and payment_doc["payment_status"] != "paid":
                # Update payment status
                await db.payment_transactions.update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "status": "completed",
                            "payment_status": "paid",
                            "confirmed_at": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                # Upgrade user subscription
                tier = payment_doc["subscription_tier"]
                await db.users.update_one(
                    {"id": user["id"]},
                    {
                        "$set": {
                            "subscription_tier": tier,
                            "daily_usage_count": 0,
                            "last_usage_reset": datetime.now(timezone.utc).isoformat()
                        }
                    }
                )
                
                logger.info(f"User {user['id']} upgraded to {tier}")
            
            return {
                "session_id": session_id,
                "status": checkout_status.status,
                "payment_status": checkout_status.payment_status,
                "amount": checkout_status.amount_total / 100,  # Convert from cents
                "currency": checkout_status.currency,
                "subscription_tier": payment_doc["subscription_tier"]
            }
        except Exception as e:
            logger.error(f"Error checking Stripe status: {str(e)}")
            # Return database status if Stripe check fails
            return payment_doc
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get payment status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get payment status")

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks

@api_router.post("/wallet/analyze", response_model=WalletAnalysisResponse)
async def analyze_wallet(request: WalletAnalysisRequest, user: dict = Depends(check_usage_limit)):
    """Analyze a crypto wallet across multiple blockchains (requires authentication)"""
    try:
        # Validate address format based on chain
        address = request.address.strip()
        chain = request.chain.lower()
        
        # Check if user has access to multi-chain (Premium/Pro feature)
        user_tier = user.get('subscription_tier', 'free')
        if chain != 'ethereum' and user_tier == 'free':
            raise HTTPException(
                status_code=403, 
                detail="Multi-chain analysis is a Premium feature. Upgrade to analyze 10+ chains including Bitcoin, Solana, Algorand, Avalanche, and Dogecoin."
            )
        
        # Basic validation
        if chain in ["ethereum", "arbitrum", "bsc", "polygon"]:
            if not address.startswith('0x') or len(address) != 42:
                raise HTTPException(status_code=400, detail=f"Invalid {chain} address format")
        elif chain == "bitcoin":
            if len(address) < 26 or len(address) > 62:
                raise HTTPException(status_code=400, detail="Invalid Bitcoin address format")
        elif chain == "solana":
            if len(address) < 32 or len(address) > 44:
                raise HTTPException(status_code=400, detail="Invalid Solana address format")
        
        # Analyze wallet using multi-chain service
        analysis_data = multi_chain_service.analyze_wallet(
            address, 
            chain=chain,
            start_date=request.start_date,
            end_date=request.end_date,
            user_tier=user.get('subscription_tier', 'free')
        )
        
        # Create response object
        analysis_response = WalletAnalysisResponse(
            address=analysis_data['address'],
            chain=analysis_data.get('chain'),
            totalEthSent=analysis_data['totalEthSent'],
            totalEthReceived=analysis_data['totalEthReceived'],
            totalGasFees=analysis_data['totalGasFees'],
            currentBalance=analysis_data.get('currentBalance', analysis_data['netEth']),
            netEth=analysis_data['netEth'],
            netFlow=analysis_data.get('netFlow', analysis_data['netEth']),
            outgoingTransactionCount=analysis_data['outgoingTransactionCount'],
            incomingTransactionCount=analysis_data['incomingTransactionCount'],
            tokensSent=analysis_data['tokensSent'],
            tokensReceived=analysis_data['tokensReceived'],
            recentTransactions=analysis_data['recentTransactions'],
            # USD values
            current_price_usd=analysis_data.get('current_price_usd'),
            total_value_usd=analysis_data.get('total_value_usd'),
            total_received_usd=analysis_data.get('total_received_usd'),
            total_sent_usd=analysis_data.get('total_sent_usd'),
            total_gas_fees_usd=analysis_data.get('total_gas_fees_usd'),
            # Tax data
            tax_data=analysis_data.get('tax_data')
        )
        
        # Store in database with user info
        doc = analysis_response.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        doc['user_id'] = user['id']
        await db.wallet_analyses.insert_one(doc)
        
        # Increment user's usage counts
        await db.users.update_one(
            {"id": user["id"]},
            {"$inc": {"daily_usage_count": 1, "analysis_count": 1}}
        )
        
        return analysis_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze wallet: {str(e)}")

@api_router.post("/wallet/analyze-all")
async def analyze_all_chains(request: WalletAnalysisRequest, user: dict = Depends(check_usage_limit)):
    """Analyze wallet across all supported chains (Unlimited feature)"""
    try:
        # Check if user has Unlimited or Pro
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro']:
            raise HTTPException(
                status_code=403, 
                detail="Scan All Chains is a Premium feature. Upgrade to analyze your MetaMask wallet across all EVM blockchains simultaneously."
            )
        
        address = request.address.strip()
        
        # Define chains to analyze
        # EVM chains can use same address
        evm_chains = ['ethereum', 'polygon', 'arbitrum', 'bsc']
        
        # Determine which chains to analyze based on address format
        chains_to_analyze = []
        
        # EVM address (0x...)
        if address.startswith('0x') and len(address) == 42:
            chains_to_analyze.extend(evm_chains)
        
        # For simplicity, we'll focus on EVM chains for multi-chain analysis
        # Bitcoin and Solana require different address formats
        
        if not chains_to_analyze:
            raise HTTPException(
                status_code=400,
                detail="Address format not recognized. Currently supporting EVM addresses (0x...) for multi-chain analysis."
            )
        
        # Analyze each chain in parallel
        import asyncio
        
        async def analyze_single_chain(chain: str):
            try:
                return {
                    'chain': chain,
                    'success': True,
                    'data': multi_chain_service.analyze_wallet(
                        address, 
                        chain=chain,
                        start_date=request.start_date,
                        end_date=request.end_date,
                        user_tier=user.get('subscription_tier', 'free')
                    )
                }
            except Exception as e:
                logger.error(f"Error analyzing {chain}: {str(e)}")
                return {
                    'chain': chain,
                    'success': False,
                    'error': str(e)
                }
        
        # Run all analyses in parallel
        results = await asyncio.gather(
            *[analyze_single_chain(chain) for chain in chains_to_analyze],
            return_exceptions=True
        )
        
        # Aggregate results
        successful_analyses = []
        failed_chains = []
        
        total_value = 0.0
        total_gas_fees = 0.0
        total_transactions = 0
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Chain analysis failed with exception: {str(result)}")
                continue
                
            if result['success']:
                data = result['data']
                successful_analyses.append({
                    'chain': result['chain'],
                    'totalSent': data['totalEthSent'],
                    'totalReceived': data['totalEthReceived'],
                    'netBalance': data['netEth'],
                    'gasFees': data['totalGasFees'],
                    'transactionCount': data['outgoingTransactionCount'] + data['incomingTransactionCount'],
                    'tokensCount': len(data.get('tokensSent', {})) + len(data.get('tokensReceived', {}))
                })
                
                # Aggregate totals (convert to USD for aggregation - simplified)
                total_value += abs(data['totalEthReceived'])
                total_gas_fees += data['totalGasFees']
                total_transactions += data['outgoingTransactionCount'] + data['incomingTransactionCount']
            else:
                failed_chains.append({
                    'chain': result['chain'],
                    'error': result.get('error', 'Unknown error')
                })
        
        if not successful_analyses:
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze any chains. Please try again."
            )
        
        # Increment user's daily usage count (count as 1 usage)
        await db.users.update_one(
            {"id": user["id"]},
            {"$inc": {"daily_usage_count": 1}}
        )
        
        return {
            'address': address,
            'chains_analyzed': len(successful_analyses),
            'total_chains': len(chains_to_analyze),
            'results': successful_analyses,
            'failed_chains': failed_chains,
            'aggregated': {
                'total_value': total_value,
                'total_gas_fees': total_gas_fees,
                'total_transactions': total_transactions
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in multi-chain analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Multi-chain analysis failed: {str(e)}")

@api_router.post("/wallet/export-paginated")
async def export_wallet_paginated(
    request: WalletAnalysisRequest, 
    page: int = 1,
    page_size: int = 1000,
    user: dict = Depends(get_current_user)
):
    """Export wallet transactions in paginated batches (Premium/Pro feature)"""
    try:
        # Check if user has Premium or Pro
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403, 
                detail="CSV Export is a Premium feature. Upgrade to download your transaction history."
            )
        
        address = request.address.strip()
        chain = request.chain.lower()
        
        # Validate chain access
        if chain != 'ethereum' and user_tier == 'free':
            raise HTTPException(status_code=403, detail="Multi-chain export requires Premium")
        
        # Get full transaction history with pagination
        analysis_data = multi_chain_service.analyze_wallet(
            address, 
            chain=chain,
            start_date=request.start_date,
            end_date=request.end_date,
            limit=page_size,
            offset=(page - 1) * page_size,
            user_tier=user.get('subscription_tier', 'free')
        )
        
        # Get total transaction count for pagination info
        total_transactions = analysis_data.get('totalTransactionCount', 0)
        total_pages = (total_transactions + page_size - 1) // page_size
        
        return {
            'address': analysis_data['address'],
            'chain': chain,
            'page': page,
            'page_size': page_size,
            'total_transactions': total_transactions,
            'total_pages': total_pages,
            'has_more': page < total_pages,
            'transactions': analysis_data['recentTransactions'],
            'summary': {
                'totalEthSent': analysis_data['totalEthSent'],
                'totalEthReceived': analysis_data['totalEthReceived'],
                'totalGasFees': analysis_data['totalGasFees'],
                'netEth': analysis_data['netEth']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export wallet: {str(e)}")

@api_router.get("/wallet/history", response_model=List[WalletAnalysisResponse])
async def get_wallet_history(limit: int = 10):
    """Get wallet analysis history"""
    try:
        analyses = await db.wallet_analyses.find({}, {"_id": 0}).sort("timestamp", -1).to_list(limit)
        
        # Convert ISO string timestamps back to datetime objects
        for analysis in analyses:
            if isinstance(analysis['timestamp'], str):
                analysis['timestamp'] = datetime.fromisoformat(analysis['timestamp'])
        
        return analyses
    except Exception as e:
        logger.error(f"Error fetching wallet history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch wallet history")

# Chains Route
@api_router.get("/chains/supported")
async def get_supported_chains():
    """Get list of supported blockchain networks"""
    try:
        chains = multi_chain_service.get_supported_chains()
        return {"chains": chains}
    except Exception as e:
        logger.error(f"Error fetching supported chains: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch supported chains")


class ChainRequest(BaseModel):
    chain_name: str
    chain_symbol: Optional[str] = None
    reason: Optional[str] = None
    sample_address: Optional[str] = None

@api_router.post("/chains/request")
async def request_chain(
    request: ChainRequest,
    user: dict = Depends(get_current_user)
):
    """
    Request a new blockchain to be added.
    Available for Unlimited users only.
    Requests are reviewed and typically added within 48 hours.
    """
    try:
        # Check subscription
        if user.get('subscription_tier') == 'free':
            raise HTTPException(
                status_code=403,
                detail="Chain requests are available for Unlimited users only. Upgrade to request new chains."
            )
        
        # Store the request
        chain_request = {
            "user_id": user["id"],
            "user_email": user.get("email", ""),
            "chain_name": request.chain_name,
            "chain_symbol": request.chain_symbol,
            "reason": request.reason,
            "sample_address": request.sample_address,
            "status": "pending",
            "created_at": datetime.now(timezone.utc)
        }
        
        await db.chain_requests.insert_one(chain_request)
        
        logger.info(f"Chain request received: {request.chain_name} from user {user.get('email')}")
        
        return {
            "message": f"Thank you! Your request for {request.chain_name} has been submitted.",
            "chain_name": request.chain_name,
            "status": "pending",
            "estimated_response": "48 hours",
            "note": "We'll notify you by email when the chain is added."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting chain request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit chain request")

@api_router.get("/chains/requests")
async def get_my_chain_requests(user: dict = Depends(get_current_user)):
    """Get user's chain requests and their status"""
    try:
        requests = await db.chain_requests.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("created_at", -1).to_list(20)
        
        return {"requests": requests}
    except Exception as e:
        logger.error(f"Error fetching chain requests: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch chain requests")



# Saved Wallets Routes
@api_router.post("/wallets/save")
async def save_wallet(
    wallet_data: SavedWalletCreate,
    user: dict = Depends(get_current_user)
):
    """Save a wallet for quick access"""
    try:
        # Check if wallet already saved
        existing = await db.saved_wallets.find_one({
            "user_id": user["id"],
            "address": wallet_data.address.lower(),
            "chain": wallet_data.chain
        })
        
        if existing:
            raise HTTPException(status_code=400, detail="Wallet already saved")
        
        # Create saved wallet
        saved_wallet = SavedWallet(
            user_id=user["id"],
            address=wallet_data.address.lower(),
            nickname=wallet_data.nickname,
            chain=wallet_data.chain
        )
        
        doc = saved_wallet.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.saved_wallets.insert_one(doc)
        
        return {"message": "Wallet saved successfully", "wallet": saved_wallet}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving wallet: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save wallet")

@api_router.get("/wallets/saved")
async def get_saved_wallets(user: dict = Depends(get_current_user)):
    """Get all saved wallets for current user"""
    try:
        wallets = await db.saved_wallets.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(100)
        
        return {"wallets": wallets}
    except Exception as e:
        logger.error(f"Error fetching saved wallets: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch saved wallets")

@api_router.delete("/wallets/saved/{wallet_id}")
async def delete_saved_wallet(
    wallet_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a saved wallet"""
    try:
        result = await db.saved_wallets.delete_one({
            "id": wallet_id,
            "user_id": user["id"]
        })
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Wallet not found")
        
        return {"message": "Wallet deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting wallet: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete wallet")

# Chain Request Route (for premium users)
@api_router.post("/chain-request")
async def request_chain(
    request_data: ChainRequest,
    user: dict = Depends(get_current_user)
):
    """Request support for a new blockchain (premium users only)"""
    try:
        if user.get("subscription_tier") == "free":
            raise HTTPException(
                status_code=403,
                detail="Chain requests are only available for premium subscribers"
            )
        
        # Store chain request
        chain_request = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "user_email": user["email"],
            "chain_name": request_data.chain_name,
            "reason": request_data.reason,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.chain_requests.insert_one(chain_request)
        
        logger.info(f"Chain request from {user['email']}: {request_data.chain_name}")
        
        return {
            "message": "Chain request submitted successfully. We'll review it and get back to you!",
            "request_id": chain_request["id"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting chain request: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit chain request")

# Tax Report Routes
class Form8949Request(BaseModel):
    address: str = ""
    chain: str = "ethereum"
    filter_type: str = "all"  # all, short-term, long-term
    data_source: str = "combined"  # wallet_only, exchange_only, combined
    tax_year: int = None

@api_router.post("/tax/export-form-8949")
async def export_form_8949(
    request: Form8949Request,
    user: dict = Depends(get_current_user)
):
    """Export IRS Form 8949 compatible CSV (Premium/Pro feature)"""
    try:
        # Check subscription tier
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Form 8949 export is a Premium feature. Upgrade to access tax reports."
            )
        
        address = request.address.strip() if request.address else None
        chain = request.chain.lower()
        data_source = request.data_source
        
        # Get chain symbol
        symbol_map = {
            'ethereum': 'ETH',
            'bitcoin': 'BTC',
            'polygon': 'MATIC',
            'arbitrum': 'ETH',
            'bsc': 'BNB',
            'solana': 'SOL'
        }
        symbol = symbol_map.get(chain, 'ETH')
        
        wallet_transactions = []
        exchange_transactions = []
        current_balance = 0
        current_price = 0
        
        # Get wallet data if needed
        if data_source in ["wallet_only", "combined"] and address:
            analysis_data = multi_chain_service.analyze_wallet(
                address=address,
                chain=chain,
                user_tier=user_tier
            )
            wallet_transactions = analysis_data.get('recentTransactions', [])
            current_balance = analysis_data.get('currentBalance', 0)
            current_price = analysis_data.get('current_price_usd', 0)
        
        # Get exchange transactions if needed
        if data_source in ["exchange_only", "combined"]:
            exchange_txs = await db.exchange_transactions.find(
                {"user_id": user["id"]},
                {"_id": 0}
            ).to_list(10000)
            exchange_transactions = exchange_txs
        
        # Calculate unified tax data
        tax_data = unified_tax_service.calculate_unified_tax_data(
            wallet_transactions=wallet_transactions,
            exchange_transactions=exchange_transactions,
            symbol=symbol,
            current_price=current_price,
            current_balance=current_balance
        )
        
        realized_gains = tax_data.get('realized_gains', [])
        
        if not realized_gains:
            raise HTTPException(
                status_code=400,
                detail="No realized gains found. Import exchange transactions or analyze a wallet with transactions first."
            )
        
        # Filter by tax year if specified
        if request.tax_year:
            realized_gains = [
                g for g in realized_gains
                if g.get('sell_date', '').startswith(str(request.tax_year))
            ]
        
        # Generate Form 8949 CSV
        csv_content = tax_report_service.generate_form_8949_csv(
            realized_gains=realized_gains,
            symbol=symbol,
            address=address or "exchange",
            filter_type=request.filter_type
        )
        
        # Return as downloadable CSV
        addr_prefix = address[:8] if address else "exchange"
        filename = f"form-8949-{addr_prefix}-{request.filter_type}-{datetime.now().strftime('%Y%m%d')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting Form 8949: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export Form 8949: {str(e)}")

@api_router.post("/tax/export-summary")
async def export_tax_summary(
    request: Form8949Request,
    user: dict = Depends(get_current_user)
):
    """Export comprehensive tax summary CSV (Premium/Pro feature)"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Tax summary export is a Premium feature."
            )
        
        address = request.address.strip()
        chain = request.chain.lower()
        
        # Get wallet analysis with tax data
        analysis_data = multi_chain_service.analyze_wallet(
            address,
            chain=chain,
            user_tier=user_tier
        )
        
        tax_data = analysis_data.get('tax_data')
        if not tax_data:
            raise HTTPException(
                status_code=400,
                detail="No tax data available."
            )
        
        symbol_map = {
            'ethereum': 'ETH',
            'bitcoin': 'BTC',
            'polygon': 'MATIC',
            'arbitrum': 'ETH',
            'bsc': 'BNB',
            'solana': 'SOL'
        }
        symbol = symbol_map.get(chain, 'ETH')
        
        csv_content = tax_report_service.generate_tax_summary_csv(
            tax_data=tax_data,
            symbol=symbol,
            address=address
        )
        
        filename = f"tax-summary-{address[:8]}-{datetime.now().strftime('%Y%m%d')}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting tax summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export tax summary: {str(e)}")

class TransactionCategoryRequest(BaseModel):
    address: str
    chain: str = "ethereum"
    categories: Dict[str, str]  # tx_hash -> category

@api_router.post("/tax/save-categories")
async def save_transaction_categories(
    request: TransactionCategoryRequest,
    user: dict = Depends(get_current_user)
):
    """Save transaction categories for tax purposes (Premium/Pro feature)"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Transaction categorization is a Premium feature."
            )
        
        # Store categories in database
        category_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "address": request.address.lower(),
            "chain": request.chain.lower(),
            "categories": request.categories,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Upsert - update if exists, insert if not
        await db.transaction_categories.update_one(
            {
                "user_id": user["id"],
                "address": request.address.lower(),
                "chain": request.chain.lower()
            },
            {"$set": category_doc},
            upsert=True
        )
        
        logger.info(f"Saved {len(request.categories)} transaction categories for user {user['id']}")
        
        return {
            "message": "Categories saved successfully",
            "count": len(request.categories)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save categories")

@api_router.get("/tax/categories/{address}")
async def get_transaction_categories(
    address: str,
    chain: str = "ethereum",
    user: dict = Depends(get_current_user)
):
    """Get saved transaction categories for a wallet"""
    try:
        categories_doc = await db.transaction_categories.find_one(
            {
                "user_id": user["id"],
                "address": address.lower(),
                "chain": chain.lower()
            },
            {"_id": 0}
        )
        
        if not categories_doc:
            return {"categories": {}}
        
        return {"categories": categories_doc.get("categories", {})}
        
    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch categories")

# Schedule D Export
class ScheduleDRequest(BaseModel):
    address: str = ""
    chain: str = "ethereum"
    tax_year: int
    format: str = "text"  # text or csv
    data_source: str = "combined"  # wallet_only, exchange_only, combined

@api_router.post("/tax/export-schedule-d")
async def export_schedule_d(
    request: ScheduleDRequest,
    user: dict = Depends(get_current_user)
):
    """Export Schedule D (Capital Gains Summary) for a specific tax year (Premium/Pro)"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Schedule D export is a Premium feature."
            )
        
        # Validate tax year
        current_year = datetime.now().year
        if request.tax_year < 2020 or request.tax_year > current_year:
            raise HTTPException(
                status_code=400,
                detail=f"Tax year must be between 2020 and {current_year}"
            )
        
        address = request.address.strip() if request.address else None
        chain = request.chain.lower()
        data_source = request.data_source
        
        symbol_map = {
            'ethereum': 'ETH',
            'bitcoin': 'BTC',
            'polygon': 'MATIC',
            'arbitrum': 'ETH',
            'bsc': 'BNB',
            'solana': 'SOL'
        }
        symbol = symbol_map.get(chain, 'ETH')
        
        wallet_transactions = []
        exchange_transactions = []
        current_balance = 0
        current_price = 0
        
        # Get wallet data if needed
        if data_source in ["wallet_only", "combined"] and address:
            analysis_data = multi_chain_service.analyze_wallet(
                address=address,
                chain=chain,
                user_tier=user_tier
            )
            wallet_transactions = analysis_data.get('recentTransactions', [])
            current_balance = analysis_data.get('currentBalance', 0)
            current_price = analysis_data.get('current_price_usd', 0)
        
        # Get exchange transactions if needed
        if data_source in ["exchange_only", "combined"]:
            exchange_txs = await db.exchange_transactions.find(
                {"user_id": user["id"]},
                {"_id": 0}
            ).to_list(10000)
            exchange_transactions = exchange_txs
        
        # Calculate unified tax data
        tax_data = unified_tax_service.calculate_unified_tax_data(
            wallet_transactions=wallet_transactions,
            exchange_transactions=exchange_transactions,
            symbol=symbol,
            current_price=current_price,
            current_balance=current_balance
        )
        
        # Filter by tax year
        realized_gains = [
            g for g in tax_data.get('realized_gains', [])
            if g.get('sell_date', '').startswith(str(request.tax_year))
        ]
        
        if not realized_gains:
            raise HTTPException(
                status_code=400,
                detail=f"No realized gains found for tax year {request.tax_year}."
            )
        
        # Generate based on format
        addr_prefix = address[:8] if address else "exchange"
        if request.format == 'csv':
            content = tax_report_service.generate_schedule_d_csv(
                realized_gains=realized_gains,
                tax_year=request.tax_year,
                symbol=symbol,
                address=address or "exchange"
            )
            media_type = "text/csv"
            filename = f"schedule-d-{addr_prefix}-{request.tax_year}.csv"
        else:
            content = tax_report_service.generate_schedule_d_summary(
                realized_gains=realized_gains,
                tax_year=request.tax_year,
                symbol=symbol,
                address=address or "exchange"
            )
            media_type = "text/plain"
            filename = f"schedule-d-{addr_prefix}-{request.tax_year}.txt"
        
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting Schedule D: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to export Schedule D: {str(e)}")

# Batch categorization
class BatchCategorizeRequest(BaseModel):
    address: str
    chain: str = "ethereum"
    rules: List[Dict[str, Any]]

@api_router.post("/tax/batch-categorize")
async def batch_categorize_transactions(
    request: BatchCategorizeRequest,
    user: dict = Depends(get_current_user)
):
    """
    Batch categorize transactions based on rules (Premium/Pro)
    
    Rules format:
    - type: 'address' | 'amount_gt' | 'amount_lt' | 'tx_type' | 'asset'
    - value: The value to match
    - category: The category to assign
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Batch categorization is a Premium feature."
            )
        
        address = request.address.strip()
        chain = request.chain.lower()
        
        # Get wallet analysis to get transactions
        analysis_data = multi_chain_service.analyze_wallet(
            address,
            chain=chain,
            user_tier=user_tier
        )
        
        transactions = analysis_data.get('recentTransactions', [])
        
        if not transactions:
            raise HTTPException(
                status_code=400,
                detail="No transactions found for this wallet."
            )
        
        # Apply batch categorization
        categories = tax_report_service.batch_categorize_transactions(
            transactions=transactions,
            rules=request.rules
        )
        
        # Save to database
        category_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "address": address.lower(),
            "chain": chain,
            "categories": categories,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.transaction_categories.update_one(
            {
                "user_id": user["id"],
                "address": address.lower(),
                "chain": chain
            },
            {"$set": category_doc},
            upsert=True
        )
        
        logger.info(f"Batch categorized {len(categories)} transactions for user {user['id']}")
        
        return {
            "message": "Transactions categorized successfully",
            "count": len(categories),
            "categories": categories
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error batch categorizing: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to batch categorize transactions")

# Auto-categorize transactions
class AutoCategorizeRequest(BaseModel):
    address: str
    chain: str = "ethereum"
    known_addresses: Optional[Dict[str, str]] = None

@api_router.post("/tax/auto-categorize")
async def auto_categorize_transactions(
    request: AutoCategorizeRequest,
    user: dict = Depends(get_current_user)
):
    """
    Auto-categorize transactions using smart detection (Premium/Pro)
    
    known_addresses: Dict of address -> label ('self', 'exchange', 'staking', etc.)
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Auto categorization is a Premium feature."
            )
        
        address = request.address.strip()
        chain = request.chain.lower()
        
        # Get wallet analysis
        analysis_data = multi_chain_service.analyze_wallet(
            address,
            chain=chain,
            user_tier=user_tier
        )
        
        transactions = analysis_data.get('recentTransactions', [])
        
        if not transactions:
            raise HTTPException(
                status_code=400,
                detail="No transactions found for this wallet."
            )
        
        # Auto categorize
        categories = tax_report_service.auto_categorize_transactions(
            transactions=transactions,
            known_addresses=request.known_addresses
        )
        
        # Save to database
        category_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "address": address.lower(),
            "chain": chain,
            "categories": categories,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await db.transaction_categories.update_one(
            {
                "user_id": user["id"],
                "address": address.lower(),
                "chain": chain
            },
            {"$set": category_doc},
            upsert=True
        )
        
        logger.info(f"Auto-categorized {len(categories)} transactions for user {user['id']}")
        
        return {
            "message": "Transactions auto-categorized successfully",
            "count": len(categories),
            "categories": categories
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error auto-categorizing: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to auto-categorize transactions")

# Get supported tax years
@api_router.get("/tax/supported-years")
async def get_supported_tax_years():
    """Get list of supported tax years for reports"""
    current_year = datetime.now().year
    return {
        "years": list(range(2020, current_year + 1)),
        "current_year": current_year
    }

# ==================== UNIFIED TAX CALCULATION ====================

from unified_tax_service import unified_tax_service

class UnifiedTaxRequest(BaseModel):
    address: Optional[str] = None  # Optional when data_source is "exchange_only"
    chain: str = "ethereum"
    data_source: str = "combined"  # "wallet_only", "exchange_only", "combined"
    asset_filter: Optional[str] = None  # Filter to specific asset (e.g., "BTC", "ETH")
    tax_year: Optional[int] = None

@api_router.post("/tax/unified")
async def get_unified_tax_data(
    request: UnifiedTaxRequest,
    user: dict = Depends(get_current_user)
):
    """
    Get unified tax data with flexible data source selection
    
    data_source options:
    - "wallet_only": Only on-chain wallet transactions
    - "exchange_only": Only imported exchange CSV transactions
    - "combined": Merge both sources for comprehensive tax calculation
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Unified tax calculation requires Unlimited subscription."
            )
        
        data_source = request.data_source
        wallet_transactions = []
        exchange_transactions = []
        current_balance = 0
        current_price = 0
        symbol = 'USD'
        address = request.address.lower() if request.address else None
        chain = request.chain
        
        # Get wallet data if needed
        if data_source in ["wallet_only", "combined"]:
            if not address:
                raise HTTPException(
                    status_code=400,
                    detail="Wallet address required for wallet_only or combined data source"
                )
            
            analysis_data = multi_chain_service.analyze_wallet(
                address=address,
                chain=chain,
                user_tier=user_tier
            )
            
            wallet_transactions = analysis_data.get('recentTransactions', [])
            current_balance = analysis_data.get('currentBalance', 0)
            current_price = analysis_data.get('current_price_usd', 0)
            symbol = {
                'ethereum': 'ETH',
                'bitcoin': 'BTC',
                'polygon': 'MATIC',
                'arbitrum': 'ETH',
                'bsc': 'BNB',
                'solana': 'SOL'
            }.get(chain, 'ETH')
        
        # Get exchange transactions if needed
        if data_source in ["exchange_only", "combined"]:
            exchange_txs = await db.exchange_transactions.find(
                {"user_id": user["id"]},
                {"_id": 0}
            ).to_list(5000)
            exchange_transactions = exchange_txs
            
            # If exchange_only, we need to determine prices from the data
            if data_source == "exchange_only" and exchange_transactions:
                # Get unique assets
                assets = set(tx.get('asset', '') for tx in exchange_transactions)
                # Use a generic symbol for mixed assets
                if len(assets) == 1:
                    symbol = list(assets)[0]
                else:
                    symbol = "MULTI"
        
        # Calculate unified tax data
        tax_data = unified_tax_service.calculate_unified_tax_data(
            wallet_transactions=wallet_transactions,
            exchange_transactions=exchange_transactions,
            symbol=symbol,
            current_price=current_price,
            current_balance=current_balance,
            asset_filter=request.asset_filter
        )
        
        # Filter by tax year if specified
        if request.tax_year:
            tax_data['realized_gains'] = [
                g for g in tax_data['realized_gains']
                if g.get('sell_date', '').startswith(str(request.tax_year))
            ]
            # Recalculate summary
            tax_data['summary']['total_realized_gain'] = sum(
                g['gain_loss'] for g in tax_data['realized_gains']
            )
            tax_data['summary']['short_term_gains'] = sum(
                g['gain_loss'] for g in tax_data['realized_gains'] 
                if g['holding_period'] == 'short-term'
            )
            tax_data['summary']['long_term_gains'] = sum(
                g['gain_loss'] for g in tax_data['realized_gains'] 
                if g['holding_period'] == 'long-term'
            )
        
        # Get asset summary
        assets_summary = unified_tax_service.get_assets_summary(
            wallet_transactions,
            exchange_transactions,
            symbol
        )
        
        return {
            "wallet_address": address,
            "chain": chain,
            "symbol": symbol,
            "current_price": current_price,
            "tax_year": request.tax_year,
            "data_source": data_source,
            "data_sources_used": {
                "wallet": len(wallet_transactions) > 0,
                "wallet_tx_count": len(wallet_transactions),
                "exchange": len(exchange_transactions) > 0,
                "exchange_tx_count": len(exchange_transactions)
            },
            "tax_data": tax_data,
            "assets_summary": assets_summary,
            "message": f"Tax data calculated using {data_source} source(s)"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating unified tax: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate unified tax data: {str(e)}")

@api_router.post("/tax/detect-transfers")
async def detect_wallet_exchange_transfers(
    request: UnifiedTaxRequest,
    user: dict = Depends(get_current_user)
):
    """
    Detect transfers between wallet and exchange.
    
    When you send crypto from a cold wallet to an exchange:
    - The wallet shows a "send" transaction
    - The exchange shows a "receive" transaction
    
    This endpoint matches them so we can use the correct holding period.
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Transfer detection requires Unlimited subscription."
            )
        
        address = request.address.lower() if request.address else None
        chain = request.chain
        
        if not address:
            raise HTTPException(status_code=400, detail="Wallet address required")
        
        # Get wallet analysis
        analysis_data = multi_chain_service.analyze_wallet(
            address=address,
            chain=chain,
            user_tier=user_tier
        )
        
        wallet_transactions = analysis_data.get('recentTransactions', [])
        symbol = {
            'ethereum': 'ETH',
            'bitcoin': 'BTC',
            'polygon': 'MATIC',
            'arbitrum': 'ETH',
            'bsc': 'BNB',
            'solana': 'SOL'
        }.get(chain, 'ETH')
        
        # Get exchange transactions
        exchange_txs = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(5000)
        
        # Normalize transactions
        normalized_wallet = []
        for tx in wallet_transactions:
            normalized_wallet.append(unified_tax_service.normalize_wallet_transaction(tx, symbol))
        
        normalized_exchange = []
        for tx in exchange_txs:
            normalized_exchange.append(unified_tax_service.normalize_exchange_transaction(tx))
        
        # Detect transfers
        detected = unified_tax_service.detect_transfers_between_sources(
            normalized_wallet, 
            normalized_exchange,
            tolerance_hours=48  # Allow 48 hour window for matching
        )
        
        return {
            "wallet_address": address,
            "chain": chain,
            "symbol": symbol,
            "transfers_detected": len(detected),
            "transfers": detected,
            "message": f"Found {len(detected)} potential transfers from wallet to exchange"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting transfers: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to detect transfers: {str(e)}")

@api_router.get("/tax/unified/assets")
async def get_unified_assets_summary(user: dict = Depends(get_current_user)):
    """
    Get summary of all assets across wallet analyses and exchange imports
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Asset summary requires Unlimited subscription."
            )
        
        # Get all exchange transactions for this user
        exchange_txs = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(5000)
        
        # Get unique assets from exchanges
        assets = {}
        for tx in exchange_txs:
            asset = tx.get('asset', 'UNKNOWN')
            if asset not in assets:
                assets[asset] = {
                    'asset': asset,
                    'exchange_txs': 0,
                    'total_bought': 0,
                    'total_sold': 0,
                    'exchanges': set()
                }
            
            assets[asset]['exchange_txs'] += 1
            assets[asset]['exchanges'].add(tx.get('exchange', 'unknown'))
            
            amount = float(tx.get('amount', 0))
            tx_type = tx.get('tx_type', '').lower()
            if tx_type in ['buy', 'receive', 'deposit', 'reward']:
                assets[asset]['total_bought'] += amount
            elif tx_type in ['sell', 'send', 'withdrawal']:
                assets[asset]['total_sold'] += amount
        
        # Convert sets to lists for JSON serialization
        for asset in assets.values():
            asset['exchanges'] = list(asset['exchanges'])
            asset['net_position'] = asset['total_bought'] - asset['total_sold']
        
        return {
            "assets": list(assets.values()),
            "total_assets": len(assets),
            "total_exchange_txs": len(exchange_txs)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting assets summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get assets summary")

# ==================== AFFILIATE ROUTES ====================

@api_router.post("/affiliate/register")
async def register_affiliate(
    request: AffiliateRegisterRequest,
    user: dict = Depends(get_current_user)
):
    """Register as an affiliate"""
    try:
        # Check if user already is an affiliate
        existing = await db.affiliates.find_one({"user_id": user["id"]})
        if existing:
            raise HTTPException(status_code=400, detail="You are already registered as an affiliate")
        
        # Check if affiliate code is taken
        code = request.affiliate_code.upper().strip()
        if len(code) < 3 or len(code) > 20:
            raise HTTPException(status_code=400, detail="Affiliate code must be 3-20 characters")
        
        code_exists = await db.affiliates.find_one({"affiliate_code": code})
        if code_exists:
            raise HTTPException(status_code=400, detail="This affiliate code is already taken")
        
        # Create affiliate
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

@api_router.get("/affiliate/me")
async def get_my_affiliate_info(user: dict = Depends(get_current_user)):
    """Get current user's affiliate information"""
    try:
        affiliate = await db.affiliates.find_one(
            {"user_id": user["id"]},
            {"_id": 0}
        )
        
        if not affiliate:
            return {"is_affiliate": False}
        
        # Get recent referrals
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

@api_router.get("/affiliate/validate/{code}")
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

@api_router.put("/affiliate/update")
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

# Admin endpoint for quarterly payout report
@api_router.get("/affiliate/admin/report")
async def get_affiliate_payout_report(
    quarter: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Get affiliate payout report for a quarter (Admin only)
    Quarter format: '2026-Q1', '2026-Q2', etc.
    """
    try:
        # Simple admin check - you may want to add proper admin role
        admin_emails = os.environ.get('ADMIN_EMAILS', '').split(',')
        if user['email'] not in admin_emails and user['email'] != 'admin@cryptobagtracker.io':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Default to current quarter
        if not quarter:
            quarter = get_current_quarter()
        
        # Get all unpaid referrals for the quarter
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
        
        # Get affiliate details
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

@api_router.post("/affiliate/admin/mark-paid")
async def mark_affiliates_paid(
    quarter: str,
    affiliate_ids: List[str],
    user: dict = Depends(get_current_user)
):
    """Mark affiliate referrals as paid (Admin only)"""
    try:
        # Admin check
        admin_emails = os.environ.get('ADMIN_EMAILS', '').split(',')
        if user['email'] not in admin_emails and user['email'] != 'admin@cryptobagtracker.io':
            raise HTTPException(status_code=403, detail="Admin access required")
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Update referrals
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
        
        # Update affiliate pending earnings
        for aff_id in affiliate_ids:
            # Calculate paid amount
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

# ==================== EXCHANGE CSV IMPORT ROUTES ====================

from csv_parser_service import csv_parser_service
from fastapi import UploadFile, File

@api_router.get("/exchanges/supported")
async def get_supported_exchanges():
    """Get list of supported exchange CSV formats with export instructions"""
    exchanges = csv_parser_service.get_supported_exchanges()
    return {"exchanges": exchanges}

@api_router.post("/exchanges/import-csv")
async def import_exchange_csv(
    file: UploadFile = File(...),
    exchange_hint: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """
    Import transactions from exchange CSV file
    
    - Auto-detects exchange format from column headers
    - Supported: Coinbase, Binance, Kraken, Gemini, Crypto.com, KuCoin
    - Optional exchange_hint to help detection
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="CSV import is an Unlimited feature. Upgrade to import exchange data."
            )
        
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(status_code=400, detail="Please upload a CSV file")
        
        # Read file content
        content = await file.read()
        try:
            content_str = content.decode('utf-8')
        except UnicodeDecodeError:
            content_str = content.decode('latin-1')
        
        # Parse CSV
        detected_exchange, transactions = csv_parser_service.parse_csv(
            content_str, 
            exchange_hint
        )
        
        # Store transactions in database
        stored_count = 0
        for tx in transactions:
            tx_doc = tx.to_dict()
            tx_doc["user_id"] = user["id"]
            tx_doc["imported_at"] = datetime.now(timezone.utc).isoformat()
            tx_doc["source"] = "csv_import"
            
            # Upsert each transaction (avoid duplicates)
            await db.exchange_transactions.update_one(
                {
                    "user_id": user["id"], 
                    "exchange": tx.exchange, 
                    "tx_id": tx.tx_id,
                    "timestamp": tx_doc["timestamp"]
                },
                {"$set": tx_doc},
                upsert=True
            )
            stored_count += 1
        
        logger.info(f"User {user['id']} imported {stored_count} transactions from {detected_exchange}")
        
        # Calculate summary
        summary = _calculate_import_summary(transactions)
        
        return {
            "message": f"Successfully imported {stored_count} transactions from {detected_exchange.value}",
            "exchange_detected": detected_exchange.value,
            "transaction_count": stored_count,
            "summary": summary
        }
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing CSV: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to import CSV: {str(e)}")

def _calculate_import_summary(transactions) -> Dict[str, Any]:
    """Calculate summary statistics from imported transactions"""
    summary = {
        "total_transactions": len(transactions),
        "by_type": {},
        "by_asset": {},
        "date_range": {"earliest": None, "latest": None}
    }
    
    for tx in transactions:
        # By type
        tx_type = tx.tx_type
        summary["by_type"][tx_type] = summary["by_type"].get(tx_type, 0) + 1
        
        # By asset
        asset = tx.asset
        if asset not in summary["by_asset"]:
            summary["by_asset"][asset] = {"count": 0, "total_amount": 0}
        summary["by_asset"][asset]["count"] += 1
        summary["by_asset"][asset]["total_amount"] += tx.amount
        
        # Date range
        if tx.timestamp:
            ts = tx.timestamp.isoformat()
            if not summary["date_range"]["earliest"] or ts < summary["date_range"]["earliest"]:
                summary["date_range"]["earliest"] = ts
            if not summary["date_range"]["latest"] or ts > summary["date_range"]["latest"]:
                summary["date_range"]["latest"] = ts
    
    return summary

@api_router.get("/exchanges/transactions")
async def get_exchange_transactions(
    exchange: Optional[str] = None,
    tx_type: Optional[str] = None,
    asset: Optional[str] = None,
    limit: int = 100,
    user: dict = Depends(get_current_user)
):
    """Get imported exchange transactions with filters"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Exchange transactions require Unlimited subscription."
            )
        
        # Build query
        query = {"user_id": user["id"]}
        
        if exchange:
            query["exchange"] = exchange.lower()
        if tx_type:
            query["tx_type"] = tx_type
        if asset:
            query["asset"] = asset.upper()
        
        transactions = await db.exchange_transactions.find(
            query,
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit).to_list(limit)
        
        # Calculate summary
        summary = {
            "total_transactions": len(transactions),
            "by_exchange": {},
            "by_type": {},
            "by_asset": {}
        }
        
        for tx in transactions:
            exc = tx.get("exchange", "unknown")
            summary["by_exchange"][exc] = summary["by_exchange"].get(exc, 0) + 1
            
            t = tx.get("tx_type", "unknown")
            summary["by_type"][t] = summary["by_type"].get(t, 0) + 1
            
            a = tx.get("asset", "unknown")
            summary["by_asset"][a] = summary["by_asset"].get(a, 0) + 1
        
        return {
            "transactions": transactions,
            "count": len(transactions),
            "summary": summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching exchange transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch transactions")

@api_router.delete("/exchanges/transactions")
async def delete_exchange_transactions(
    exchange: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Delete imported exchange transactions"""
    try:
        query = {"user_id": user["id"]}
        if exchange:
            query["exchange"] = exchange.lower()
        
        result = await db.exchange_transactions.delete_many(query)
        
        return {
            "message": f"Deleted {result.deleted_count} transactions",
            "deleted_count": result.deleted_count
        }
        
    except Exception as e:
        logger.error(f"Error deleting transactions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to delete transactions")


class CostBasisUpdate(BaseModel):
    tx_id: str
    original_purchase_date: Optional[str] = None  # ISO format date
    original_cost_basis: Optional[float] = None
    is_transfer: bool = False  # Mark as transfer from another wallet
    notes: Optional[str] = None

@api_router.put("/exchanges/transactions/{tx_id}/cost-basis")
async def update_transaction_cost_basis(
    tx_id: str,
    update: CostBasisUpdate,
    user: dict = Depends(get_current_user)
):
    """
    Update cost basis and original purchase date for a transaction.
    Use this for transfers from cold wallets where the original purchase
    date differs from the receive date.
    """
    try:
        # Find the transaction
        tx = await db.exchange_transactions.find_one({
            "user_id": user["id"],
            "tx_id": tx_id
        })
        
        if not tx:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        # Build update
        update_data = {}
        
        if update.is_transfer:
            update_data["is_transfer"] = True
            update_data["transfer_notes"] = update.notes or "Transfer from external wallet"
        
        if update.original_purchase_date:
            # Parse the date and use it as the acquisition date for tax purposes
            try:
                original_date = datetime.fromisoformat(update.original_purchase_date.replace("Z", "+00:00"))
                update_data["original_purchase_date"] = original_date
                update_data["acquisition_date_override"] = original_date
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DD)")
        
        if update.original_cost_basis is not None:
            update_data["original_cost_basis"] = update.original_cost_basis
            update_data["cost_basis_override"] = update.original_cost_basis
        
        if update.notes:
            update_data["user_notes"] = update.notes
        
        update_data["manually_adjusted"] = True
        update_data["adjusted_at"] = datetime.now(timezone.utc)
        
        # Update the transaction
        await db.exchange_transactions.update_one(
            {"user_id": user["id"], "tx_id": tx_id},
            {"$set": update_data}
        )
        
        return {
            "message": "Transaction cost basis updated successfully",
            "tx_id": tx_id,
            "updates_applied": list(update_data.keys())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating cost basis: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update transaction")

@api_router.get("/exchanges/transactions/transfers")
async def get_potential_transfers(
    user: dict = Depends(get_current_user)
):
    """
    Identify potential transfers (receives that might be from external wallets).
    Returns receive transactions that happen shortly before sells of the same asset.
    """
    try:
        # Get all transactions
        transactions = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("timestamp", 1).to_list(5000)
        
        potential_transfers = []
        receives_by_asset = {}
        
        # Group receives by asset
        for tx in transactions:
            if tx.get("tx_type") in ["receive", "deposit"]:
                asset = tx.get("asset", "")
                if asset not in receives_by_asset:
                    receives_by_asset[asset] = []
                receives_by_asset[asset].append(tx)
        
        # Find receives followed by sells within 30 days
        for tx in transactions:
            if tx.get("tx_type") in ["sell", "send"]:
                asset = tx.get("asset", "")
                sell_time = tx.get("timestamp")
                
                if asset in receives_by_asset:
                    for receive in receives_by_asset[asset]:
                        receive_time = receive.get("timestamp")
                        if receive_time and sell_time:
                            # Check if receive was within 30 days before sell
                            if isinstance(receive_time, str):
                                receive_time = datetime.fromisoformat(receive_time.replace("Z", "+00:00"))
                            if isinstance(sell_time, str):
                                sell_time = datetime.fromisoformat(sell_time.replace("Z", "+00:00"))
                            
                            days_diff = (sell_time - receive_time).days
                            if 0 <= days_diff <= 30:
                                # Check if not already marked
                                if not receive.get("is_transfer") and not receive.get("manually_adjusted"):
                                    potential_transfers.append({
                                        "receive_tx": receive,
                                        "sell_tx": tx,
                                        "days_between": days_diff,
                                        "asset": asset,
                                        "suggestion": f"This {asset} was received {days_diff} days before being sold. If transferred from your own wallet, set the original purchase date."
                                    })
        
        return {
            "potential_transfers": potential_transfers[:50],  # Limit to 50
            "count": len(potential_transfers),
            "message": "These receives may be transfers from your own wallets. Update the original purchase date if so."
        }
        
    except Exception as e:
        logger.error(f"Error finding potential transfers: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to analyze transactions")



@api_router.get("/exchanges/export-instructions/{exchange_id}")
async def get_export_instructions(exchange_id: str):
    """Get detailed CSV export instructions for a specific exchange"""
    instructions = {
        "coinbase": {
            "name": "Coinbase",
            "steps": [
                "1. Log in to Coinbase (coinbase.com)",
                "2. Click on your profile icon → Settings",
                "3. Go to 'Statements' or 'Reports'",
                "4. Click 'Generate Report'",
                "5. Select 'Transaction History'",
                "6. Choose your date range (or 'All time')",
                "7. Click 'Generate Report'",
                "8. Download the CSV file when ready"
            ],
            "notes": "We support multiple Coinbase CSV formats including classic and modern exports. Coinbase Pro has a separate export.",
            "accepted_columns": [
                "Classic: Timestamp, Transaction Type, Asset, Quantity Transacted, Spot Price, Subtotal",
                "Modern: Transaction ID, Date & time, Asset Acquired, Quantity Acquired, Asset Sold, Quantity Sold, USD Value"
            ]
        },
        "binance": {
            "name": "Binance",
            "steps": [
                "1. Log in to Binance (binance.com)",
                "2. Go to 'Orders' → 'Trade History'",
                "3. Click 'Export' in the top right",
                "4. Select 'Export Complete Trade History'",
                "5. Choose your date range",
                "6. Click 'Generate' and wait for the file",
                "7. Download the CSV when ready"
            ],
            "notes": "For deposits/withdrawals, export separately from 'Wallet' → 'Transaction History'"
        },
        "kraken": {
            "name": "Kraken",
            "steps": [
                "1. Log in to Kraken (kraken.com)",
                "2. Go to 'History' in the top menu",
                "3. Click 'Export'",
                "4. Select 'Ledgers' for all transactions or 'Trades' for trades only",
                "5. Choose your date range",
                "6. Click 'Submit' and download the CSV"
            ],
            "notes": "Ledgers export includes all activity. Trades export is just buy/sell."
        },
        "gemini": {
            "name": "Gemini",
            "steps": [
                "1. Log in to Gemini (gemini.com)",
                "2. Go to 'Account' → 'Statements'",
                "3. Click 'Download' next to Trade History",
                "4. Select your date range",
                "5. Download the CSV file"
            ],
            "notes": "ActiveTrader interface has a separate export option."
        },
        "crypto_com": {
            "name": "Crypto.com",
            "steps": [
                "1. Open Crypto.com App",
                "2. Go to 'Accounts' tab",
                "3. Tap 'Transaction History'",
                "4. Tap the export icon (top right)",
                "5. Select date range and export",
                "6. The CSV will be emailed to you"
            ],
            "notes": "Export from the app, not the exchange. Exchange has separate export."
        },
        "kucoin": {
            "name": "KuCoin",
            "steps": [
                "1. Log in to KuCoin (kucoin.com)",
                "2. Go to 'Orders' → 'Trade History'",
                "3. Click 'Export' button",
                "4. Select date range (max 3 months at a time)",
                "5. Download the CSV file"
            ],
            "notes": "KuCoin limits exports to 3 months. Export multiple files if needed."
        }
    }
    
    if exchange_id.lower() not in instructions:
        raise HTTPException(status_code=404, detail=f"Instructions not found for {exchange_id}")
    
    return instructions[exchange_id.lower()]

# ==================== EXCHANGE-ONLY TAX CALCULATION ====================

from exchange_tax_service import exchange_tax_service

class ExchangeTaxRequest(BaseModel):
    asset_filter: Optional[str] = None
    tax_year: Optional[int] = None

@api_router.post("/exchanges/tax/calculate")
async def calculate_exchange_tax(
    request: ExchangeTaxRequest = ExchangeTaxRequest(),
    user: dict = Depends(get_current_user)
):
    """
    Calculate tax data from imported exchange CSVs only.
    No wallet analysis required - works purely from your uploaded data.
    
    Returns:
        - FIFO cost basis for all assets
        - Realized capital gains/losses
        - Unrealized gains on open positions
        - Form 8949 compatible data
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Exchange tax calculation requires Unlimited subscription."
            )
        
        # Get all exchange transactions for this user
        transactions = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(10000)
        
        if not transactions:
            return {
                "message": "No exchange data found. Upload your exchange CSVs first.",
                "has_data": False,
                "tax_data": exchange_tax_service._empty_result()
            }
        
        # Calculate tax data
        tax_data = exchange_tax_service.calculate_from_transactions(
            transactions=transactions,
            asset_filter=request.asset_filter,
            tax_year=request.tax_year
        )
        
        return {
            "message": "Tax calculation complete",
            "has_data": True,
            "tax_data": tax_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating exchange tax: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to calculate tax: {str(e)}")

@api_router.get("/exchanges/tax/form-8949")
async def get_exchange_form_8949(
    tax_year: Optional[int] = None,
    holding_period: Optional[str] = None,  # 'short-term' or 'long-term'
    user: dict = Depends(get_current_user)
):
    """
    Generate Form 8949 data from exchange transactions only.
    
    Args:
        tax_year: Filter for specific tax year
        holding_period: Filter for 'short-term' or 'long-term'
    
    Returns:
        Form 8949 line items ready for tax filing
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="Form 8949 export requires Unlimited subscription."
            )
        
        # Get transactions
        transactions = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(10000)
        
        if not transactions:
            return {
                "message": "No exchange data found",
                "line_items": [],
                "totals": {}
            }
        
        # Calculate tax data
        tax_data = exchange_tax_service.calculate_from_transactions(
            transactions=transactions,
            tax_year=tax_year
        )
        
        # Generate Form 8949 data
        form_data = exchange_tax_service.generate_form_8949_data(
            realized_gains=tax_data['realized_gains'],
            holding_period_filter=holding_period
        )
        
        # Calculate totals
        totals = {
            'total_proceeds': sum(item['proceeds'] for item in form_data),
            'total_cost_basis': sum(item['cost_basis'] for item in form_data),
            'total_gain_loss': sum(item['gain_or_loss'] for item in form_data),
            'line_count': len(form_data)
        }
        
        return {
            "tax_year": tax_year or "All Years",
            "holding_period": holding_period or "All",
            "line_items": form_data,
            "totals": totals
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating Form 8949: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate Form 8949")

@api_router.get("/exchanges/tax/form-8949/csv")
async def export_exchange_form_8949_csv(
    tax_year: Optional[int] = None,
    holding_period: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    """Export Form 8949 data as CSV file"""
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier == 'free':
            raise HTTPException(
                status_code=403,
                detail="CSV export requires Unlimited subscription."
            )
        
        # Get transactions
        transactions = await db.exchange_transactions.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).to_list(10000)
        
        if not transactions:
            raise HTTPException(status_code=404, detail="No exchange data found")
        
        # Calculate and generate form data
        tax_data = exchange_tax_service.calculate_from_transactions(
            transactions=transactions,
            tax_year=tax_year
        )
        
        form_data = exchange_tax_service.generate_form_8949_data(
            realized_gains=tax_data['realized_gains'],
            holding_period_filter=holding_period
        )
        
        # Generate CSV
        import io
        import csv
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Description of Property',
            'Date Acquired',
            'Date Sold',
            'Proceeds',
            'Cost Basis',
            'Adjustment Code',
            'Adjustment Amount',
            'Gain or Loss',
            'Holding Period',
            'Exchange'
        ])
        
        # Data rows
        for item in form_data:
            writer.writerow([
                item['description'],
                item['date_acquired'],
                item['date_sold'],
                f"${item['proceeds']:.2f}",
                f"${item['cost_basis']:.2f}",
                item['adjustment_code'],
                f"${item['adjustment_amount']:.2f}",
                f"${item['gain_or_loss']:.2f}",
                item['holding_period'],
                item['exchange']
            ])
        
        # Totals row
        writer.writerow([])
        writer.writerow([
            'TOTALS',
            '',
            '',
            f"${sum(item['proceeds'] for item in form_data):.2f}",
            f"${sum(item['cost_basis'] for item in form_data):.2f}",
            '',
            '',
            f"${sum(item['gain_or_loss'] for item in form_data):.2f}",
            '',
            ''
        ])
        
        csv_content = output.getvalue()
        
        filename = f"Form_8949_Exchanges_{tax_year or 'All'}_{holding_period or 'All'}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting CSV: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export CSV")

# ============================================================================
# Chain of Custody Endpoints (Unlimited tier only)
# ============================================================================
from custody_service import custody_service

class CustodyAnalysisRequest(BaseModel):
    address: str
    chain: str = "ethereum"
    max_depth: int = 10  # 0 = unlimited
    dormancy_days: int = 365

@api_router.post("/custody/analyze")
async def analyze_chain_of_custody(
    request: CustodyAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """
    Analyze chain of custody for a wallet address.
    Traces transactions backwards to find origin points (exchanges, DEXs, dormant wallets).
    
    This is an Unlimited-tier feature for comprehensive tax cost basis analysis.
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="Chain of Custody analysis requires Unlimited subscription."
            )
        
        # Validate address
        address = request.address.strip().lower()
        if not address.startswith('0x') or len(address) != 42:
            raise HTTPException(
                status_code=400,
                detail="Invalid EVM address format. Must start with 0x and be 42 characters."
            )
        
        # Supported chains for custody analysis
        supported_chains = ['ethereum', 'polygon', 'arbitrum', 'bsc', 'base', 'optimism']
        if request.chain not in supported_chains:
            raise HTTPException(
                status_code=400,
                detail=f"Chain not supported for custody analysis. Supported: {', '.join(supported_chains)}"
            )
        
        # Run the analysis
        result = custody_service.analyze_chain_of_custody(
            address=address,
            chain=request.chain,
            max_depth=request.max_depth,
            dormancy_days=request.dormancy_days
        )
        
        # Store the analysis for the user
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

@api_router.get("/custody/history")
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

@api_router.get("/custody/known-addresses")
async def get_known_addresses():
    """Get list of known exchange and DEX addresses for reference"""
    from custody_service import KNOWN_EXCHANGE_ADDRESSES, KNOWN_DEX_ADDRESSES
    
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

# ============================================================================
# Coinbase OAuth Integration (Read-Only Access)
# ============================================================================
from coinbase_oauth_service import coinbase_oauth_service, OAUTH_SCOPES

@api_router.get("/coinbase/auth-url")
async def get_coinbase_auth_url(user: dict = Depends(get_current_user)):
    """
    Get Coinbase OAuth authorization URL.
    
    SECURITY NOTE: This only requests READ-ONLY access.
    The app CANNOT move, send, or withdraw any funds.
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="Coinbase integration requires a paid subscription."
            )
        
        auth_url, state = coinbase_oauth_service.get_authorization_url()
        
        # Store state with user ID for verification
        await db.coinbase_oauth_states.insert_one({
            "state": state,
            "user_id": user["id"],
            "created_at": datetime.now(timezone.utc)
        })
        
        return {
            "auth_url": auth_url,
            "state": state,
            "scopes": OAUTH_SCOPES,
            "security_note": "This app only requests READ-ONLY access. It cannot move, send, or withdraw any of your funds."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating Coinbase auth URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate authorization URL")

@api_router.post("/coinbase/callback")
async def coinbase_oauth_callback(
    code: str,
    state: str,
    user: dict = Depends(get_current_user)
):
    """
    Handle Coinbase OAuth callback and exchange code for tokens.
    """
    try:
        # Validate state
        state_record = await db.coinbase_oauth_states.find_one({
            "state": state,
            "user_id": user["id"]
        })
        
        if not state_record:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        # Delete used state
        await db.coinbase_oauth_states.delete_one({"state": state})
        
        # Exchange code for tokens
        tokens = await coinbase_oauth_service.exchange_code_for_tokens(code)
        
        # Store tokens securely (encrypted in production)
        await db.coinbase_connections.update_one(
            {"user_id": user["id"]},
            {
                "$set": {
                    "user_id": user["id"],
                    "access_token": tokens.access_token,
                    "refresh_token": tokens.refresh_token,
                    "expires_at": tokens.expires_at,
                    "connected_at": datetime.now(timezone.utc),
                    "scopes": OAUTH_SCOPES
                }
            },
            upsert=True
        )
        
        logger.info(f"Coinbase connected for user {user['id']}")
        
        return {
            "success": True,
            "message": "Coinbase account connected successfully",
            "expires_at": tokens.expires_at.isoformat() if tokens.expires_at else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Coinbase OAuth callback error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect Coinbase account")

@api_router.get("/coinbase/status")
async def get_coinbase_connection_status(user: dict = Depends(get_current_user)):
    """Check if user has connected their Coinbase account."""
    try:
        connection = await db.coinbase_connections.find_one(
            {"user_id": user["id"]},
            {"_id": 0, "access_token": 0, "refresh_token": 0}
        )
        
        if connection:
            return {
                "connected": True,
                "connected_at": connection.get("connected_at"),
                "expires_at": connection.get("expires_at"),
                "scopes": connection.get("scopes", [])
            }
        
        return {"connected": False}
    
    except Exception as e:
        logger.error(f"Error checking Coinbase status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check connection status")

@api_router.delete("/coinbase/disconnect")
async def disconnect_coinbase(user: dict = Depends(get_current_user)):
    """Disconnect Coinbase account and delete stored tokens."""
    try:
        result = await db.coinbase_connections.delete_one({"user_id": user["id"]})
        
        if result.deleted_count > 0:
            logger.info(f"Coinbase disconnected for user {user['id']}")
            return {"success": True, "message": "Coinbase account disconnected"}
        
        return {"success": False, "message": "No Coinbase account connected"}
    
    except Exception as e:
        logger.error(f"Error disconnecting Coinbase: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to disconnect Coinbase account")

@api_router.get("/coinbase/addresses-for-custody")
async def get_coinbase_addresses_for_custody(user: dict = Depends(get_current_user)):
    """
    Fetch all wallet addresses and transaction addresses from connected Coinbase account.
    Used for Chain of Custody analysis.
    
    Returns:
    - User's wallet addresses
    - Destination addresses from Send transactions
    - Source addresses from Receive transactions
    """
    try:
        # Get user's Coinbase connection
        connection = await db.coinbase_connections.find_one({"user_id": user["id"]})
        
        if not connection:
            raise HTTPException(
                status_code=400, 
                detail="No Coinbase account connected. Please connect your Coinbase account first."
            )
        
        access_token = connection.get("access_token")
        
        # Check if token is expired and refresh if needed
        expires_at = connection.get("expires_at")
        if expires_at and datetime.now(timezone.utc) > expires_at:
            # Refresh the token
            try:
                new_tokens = await coinbase_oauth_service.refresh_access_token(
                    connection.get("refresh_token")
                )
                access_token = new_tokens.access_token
                
                # Update stored tokens
                await db.coinbase_connections.update_one(
                    {"user_id": user["id"]},
                    {
                        "$set": {
                            "access_token": new_tokens.access_token,
                            "refresh_token": new_tokens.refresh_token,
                            "expires_at": new_tokens.expires_at
                        }
                    }
                )
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                raise HTTPException(
                    status_code=401,
                    detail="Coinbase session expired. Please reconnect your account."
                )
        
        # Fetch all addresses for custody analysis
        result = await coinbase_oauth_service.get_all_wallet_addresses_for_custody(access_token)
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Coinbase addresses: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch Coinbase data")

# ============================================================================
# Multi-Exchange Integration (Binance, Kraken, Gemini, Crypto.com, KuCoin, OKX)
# ============================================================================
from multi_exchange_service import multi_exchange_service, MultiExchangeService
from encryption_service import encryption_service

class ExchangeConnectionRequest(BaseModel):
    exchange: str  # 'binance', 'kraken', 'gemini', 'cryptocom', 'kucoin', 'okx'
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None  # Required for KuCoin and OKX

@api_router.post("/exchanges/connect-api")
async def connect_exchange_api(
    request: ExchangeConnectionRequest,
    user: dict = Depends(get_current_user)
):
    """
    Connect an exchange using API keys.
    
    SECURITY NOTE: These are READ-ONLY API keys.
    Users should create keys with:
    - Read access ONLY
    - Withdrawals DISABLED
    - Trading DISABLED (optional)
    
    API keys are encrypted before storage.
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="Exchange API integration requires a paid subscription."
            )
        
        exchange = request.exchange.lower()
        supported = ['binance', 'kraken', 'gemini', 'cryptocom', 'kucoin', 'okx', 'bybit', 'gateio', 'coinbase']
        
        if exchange not in supported:
            raise HTTPException(
                status_code=400,
                detail=f"Exchange not supported. Supported: {', '.join(supported)}"
            )
        
        # Encrypt credentials before storage
        encrypted_api_key = encryption_service.encrypt(request.api_key)
        encrypted_api_secret = encryption_service.encrypt(request.api_secret)
        encrypted_passphrase = encryption_service.encrypt(request.passphrase) if request.passphrase else None
        
        # Store encrypted credentials
        await db.exchange_connections.update_one(
            {"user_id": user["id"], "exchange": exchange},
            {
                "$set": {
                    "user_id": user["id"],
                    "exchange": exchange,
                    "api_key": encrypted_api_key,
                    "api_secret": encrypted_api_secret,
                    "passphrase": encrypted_passphrase,
                    "connected_at": datetime.now(timezone.utc),
                    "connection_type": "api_key",
                    "encrypted": True
                }
            },
            upsert=True
        )
        
        logger.info(f"{exchange.capitalize()} connected for user {user['id']}")
        
        return {
            "success": True,
            "message": f"{exchange.capitalize()} connected successfully",
            "exchange": exchange
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting exchange: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect exchange")

@api_router.get("/exchanges/api-connections")
async def get_exchange_connections(user: dict = Depends(get_current_user)):
    """Get list of connected exchanges via API keys"""
    try:
        connections = await db.exchange_connections.find(
            {"user_id": user["id"]},
            {"_id": 0, "api_key": 0, "api_secret": 0}
        ).to_list(20)
        
        return {"connections": connections}
    
    except Exception as e:
        logger.error(f"Error fetching exchange connections: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch connections")

@api_router.delete("/exchanges/disconnect-api/{exchange}")
async def disconnect_exchange_api(exchange: str, user: dict = Depends(get_current_user)):
    """Disconnect an exchange API connection"""
    try:
        result = await db.exchange_connections.delete_one({
            "user_id": user["id"],
            "exchange": exchange.lower()
        })
        
        if result.deleted_count > 0:
            return {"success": True, "message": f"{exchange.capitalize()} disconnected"}
        
        return {"success": False, "message": "Exchange not connected"}
    
    except Exception as e:
        logger.error(f"Error disconnecting exchange: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to disconnect exchange")

# Alias endpoints for frontend compatibility
@api_router.post("/exchange/connect")
async def connect_exchange_simple(
    request: ExchangeConnectionRequest,
    user: dict = Depends(get_current_user)
):
    """Alias for /exchanges/connect-api for frontend compatibility"""
    return await connect_exchange_api(request, user)

@api_router.get("/exchange/addresses/{exchange}")
async def get_exchange_addresses_simple(
    exchange: str,
    user: dict = Depends(get_current_user)
):
    """Alias for /exchanges/addresses-for-custody for frontend compatibility"""
    return await get_exchange_addresses_for_custody(exchange, user)

@api_router.delete("/exchange/disconnect/{exchange}")
async def disconnect_exchange_simple(
    exchange: str,
    user: dict = Depends(get_current_user)
):
    """Alias for /exchanges/disconnect-api for frontend compatibility"""
    return await disconnect_exchange_api(exchange, user)

@api_router.get("/exchanges/addresses-for-custody/{exchange}")
async def get_exchange_addresses_for_custody(
    exchange: str,
    user: dict = Depends(get_current_user)
):
    """
    Fetch addresses from a connected exchange for Chain of Custody analysis.
    Credentials are decrypted before use.
    """
    try:
        connection = await db.exchange_connections.find_one({
            "user_id": user["id"],
            "exchange": exchange.lower()
        })
        
        if not connection:
            raise HTTPException(
                status_code=400,
                detail=f"No {exchange} connection found. Please connect first."
            )
        
        # Decrypt credentials if encrypted
        api_key = connection['api_key']
        api_secret = connection['api_secret']
        passphrase = connection.get('passphrase')
        
        if connection.get('encrypted', False):
            api_key = encryption_service.decrypt(api_key)
            api_secret = encryption_service.decrypt(api_secret)
            if passphrase:
                passphrase = encryption_service.decrypt(passphrase)
        
        # Initialize exchange client
        service = MultiExchangeService()
        service.add_exchange(
            exchange.lower(),
            api_key,
            api_secret,
            passphrase
        )
        
        # Fetch addresses
        logger.info(f"Fetching addresses from {exchange} for user {user['id']}")
        result = await service.get_addresses_for_custody(exchange.lower())
        
        # Log results
        wallet_count = len(result.get('wallet_addresses', []))
        logger.info(f"Found {wallet_count} wallet addresses from {exchange}")
        
        if wallet_count == 0:
            logger.warning(f"No addresses found from {exchange} - user may need to generate deposit addresses in Coinbase first")
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching {exchange} addresses: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch {exchange} data: {str(e)}")


@api_router.get("/exchanges/debug-coinbase")
async def debug_coinbase_connection(user: dict = Depends(get_current_user)):
    """Debug endpoint to test Coinbase connection and see what's happening"""
    try:
        # Get the connection
        connection = await db.exchange_connections.find_one({
            "user_id": user["id"],
            "exchange": "coinbase"
        })
        
        if not connection:
            return {"error": "No Coinbase connection found", "step": "connection_lookup"}
        
        # Decrypt credentials
        api_key = connection['api_key']
        api_secret = connection['api_secret']
        
        if connection.get('encrypted', False):
            api_key = encryption_service.decrypt(api_key)
            api_secret = encryption_service.decrypt(api_secret)
        
        # Test the connection
        from multi_exchange_service import CoinbaseClient
        client = CoinbaseClient(api_key, api_secret)
        
        # Try to get accounts
        accounts = await client.get_accounts()
        account_summary = []
        for acc in accounts[:10]:
            account_summary.append({
                "id": acc.get('id', '')[:10] + "...",
                "name": acc.get('name', ''),
                "currency": acc.get('currency', {}).get('code', ''),
                "balance": acc.get('balance', {}).get('amount', '0')
            })
        
        # Try to get addresses
        addresses = await client.get_deposit_addresses()
        address_summary = []
        for addr in addresses[:10]:
            address_summary.append({
                "address": addr.address[:20] + "..." if len(addr.address) > 20 else addr.address,
                "asset": addr.asset,
                "network": addr.network
            })
        
        return {
            "status": "connected",
            "accounts_found": len(accounts),
            "accounts_sample": account_summary,
            "addresses_found": len(addresses),
            "addresses_sample": address_summary
        }
        
    except Exception as e:
        logger.error(f"Debug coinbase error: {e}", exc_info=True)
        return {"error": str(e), "step": "api_call"}



@api_router.post("/admin/cleanup-transactions")
async def cleanup_exchange_transactions(user: dict = Depends(get_current_user)):
    """
    Clean up existing exchange transactions by applying validation rules.
    This removes or fixes bad data that was imported before the validation fix.
    """
    try:
        from csv_parser_service import ExchangeTransaction
        
        # Get all user's exchange transactions
        transactions = await db.exchange_transactions.find(
            {"user_id": user["id"]}
        ).to_list(50000)
        
        if not transactions:
            return {"message": "No exchange transactions found", "cleaned": 0, "removed": 0}
        
        cleaned_count = 0
        removed_count = 0
        removed_details = []
        
        for tx in transactions:
            tx_id = tx.get('_id')
            asset = tx.get('asset', '').upper()
            original_amount = tx.get('amount', 0)
            
            # Create a temporary ExchangeTransaction to validate the amount
            from datetime import datetime
            temp_tx = ExchangeTransaction(
                exchange=tx.get('exchange', 'unknown'),
                tx_id=tx.get('tx_id', ''),
                tx_type=tx.get('tx_type', 'unknown'),
                asset=asset,
                amount=original_amount,
                price_usd=tx.get('price_usd'),
                total_usd=tx.get('total_usd'),
                fee=tx.get('fee', 0),
                fee_asset=tx.get('fee_asset', 'USD'),
                timestamp=datetime.now(),
                raw_data={}
            )
            
            validated_amount = temp_tx.amount
            
            if validated_amount == 0 and original_amount > 0:
                # Transaction should be removed (unreasonable amount)
                await db.exchange_transactions.delete_one({"_id": tx_id})
                removed_count += 1
                removed_details.append({
                    "asset": asset,
                    "original_amount": original_amount,
                    "reason": "amount exceeded maximum allowed"
                })
            elif validated_amount != original_amount:
                # Transaction amount was converted (e.g., from raw units)
                await db.exchange_transactions.update_one(
                    {"_id": tx_id},
                    {"$set": {
                        "amount": validated_amount,
                        "original_amount": original_amount,
                        "amount_cleaned": True
                    }}
                )
                cleaned_count += 1
        
        return {
            "message": "Transaction cleanup complete",
            "total_transactions": len(transactions),
            "cleaned": cleaned_count,
            "removed": removed_count,
            "removed_samples": removed_details[:10]
        }
        
    except Exception as e:
        logger.error(f"Transaction cleanup error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@api_router.delete("/admin/clear-exchange-transactions")
async def clear_exchange_transactions(user: dict = Depends(get_current_user)):
    """
    Delete ALL exchange transactions for this user.
    Use this to clear bad data and start fresh.
    """
    try:
        result = await db.exchange_transactions.delete_many({"user_id": user["id"]})
        
        return {
            "message": "Exchange transactions cleared",
            "deleted_count": result.deleted_count
        }
        
    except Exception as e:
        logger.error(f"Clear exchange transactions error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/admin/exchange-transactions-summary")
async def get_exchange_transactions_summary(user: dict = Depends(get_current_user)):
    """
    Get a summary of exchange transactions to see what's stored.
    """
    try:
        # Count total
        total = await db.exchange_transactions.count_documents({"user_id": user["id"]})
        
        # Get asset breakdown
        pipeline = [
            {"$match": {"user_id": user["id"]}},
            {"$group": {
                "_id": "$asset",
                "count": {"$sum": 1},
                "total_amount": {"$sum": "$amount"},
                "avg_price": {"$avg": "$price_usd"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 20}
        ]
        
        assets = await db.exchange_transactions.aggregate(pipeline).to_list(20)
        
        # Get samples of suspicious data (high amounts)
        suspicious = await db.exchange_transactions.find(
            {"user_id": user["id"], "amount": {"$gt": 1000000000}},
            {"_id": 0, "asset": 1, "amount": 1, "price_usd": 1, "tx_type": 1}
        ).limit(10).to_list(10)
        
        return {
            "total_transactions": total,
            "assets": [{"asset": a["_id"], "count": a["count"], "total_amount": a["total_amount"], "avg_price": a["avg_price"]} for a in assets],
            "suspicious_high_amounts": suspicious
        }
        
    except Exception as e:
        logger.error(f"Exchange summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ============================================================================
# Chain of Custody PDF Report Generation
# ============================================================================
from custody_report_generator import custody_report_generator
from fastapi.responses import StreamingResponse

@api_router.post("/custody/export-pdf")
async def export_custody_pdf(
    request: CustodyAnalysisRequest,
    user: dict = Depends(get_current_user)
):
    """
    Generate a PDF report for Chain of Custody analysis.
    
    Runs the analysis and generates a professional PDF suitable for
    auditors, tax authorities, and legal teams.
    """
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="PDF reports require Unlimited subscription."
            )
        
        # Run the custody analysis first
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
        
        # Generate PDF
        user_info = {
            "email": user.get("email"),
            "id": user.get("id")
        }
        
        pdf_bytes = custody_report_generator.generate_report(result, user_info)
        
        # Generate filename
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

@api_router.post("/custody/export-pdf-from-result")
async def export_custody_pdf_from_result(
    result: Dict[str, Any],
    user: dict = Depends(get_current_user)
):
    """
    Generate a PDF report from an existing custody analysis result.
    Use this when you already have the analysis data and don't want to re-run it.
    """
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

# ============================================================================
# Support & AI Help Endpoints
# ============================================================================
from support_agent_service import support_agent_service

class SupportMessageRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Dict]] = None

class ContactRequest(BaseModel):
    name: str
    email: str
    subject: str
    message: str

@api_router.post("/support/ai-chat")
async def ai_support_chat(
    request: SupportMessageRequest,
    user: dict = Depends(get_current_user)
):
    """
    Get AI-powered support response.
    Uses GPT-4o for intelligent cryptocurrency tax help.
    """
    try:
        result = await support_agent_service.get_response(
            user_id=user.get("id", "anonymous"),
            message=request.message,
            conversation_history=request.conversation_history
        )
        
        # Store conversation in database for history
        await db.support_conversations.update_one(
            {"user_id": user["id"], "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
            {
                "$push": {
                    "messages": {
                        "role": "user",
                        "content": request.message,
                        "timestamp": datetime.now(timezone.utc)
                    }
                },
                "$set": {"updated_at": datetime.now(timezone.utc)}
            },
            upsert=True
        )
        
        if result.get("success"):
            await db.support_conversations.update_one(
                {"user_id": user["id"], "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
                {
                    "$push": {
                        "messages": {
                            "role": "assistant",
                            "content": result["response"],
                            "timestamp": datetime.now(timezone.utc)
                        }
                    }
                }
            )
        
        return result
        
    except Exception as e:
        logger.error(f"AI support error: {str(e)}")
        return {
            "success": False,
            "response": "Unable to process your request. Please try again or email support@cryptobagtracker.io"
        }

@api_router.get("/support/suggested-questions")
async def get_suggested_questions():
    """Get suggested questions for the support chat."""
    return {
        "questions": support_agent_service.get_suggested_questions()
    }

@api_router.post("/support/contact")
async def submit_contact_form(request: ContactRequest):
    """
    Submit a contact form message.
    Stores in database for review and sends email notification.
    """
    try:
        contact_record = {
            "id": str(uuid.uuid4()),
            "name": request.name,
            "email": request.email,
            "subject": request.subject,
            "message": request.message,
            "status": "new",
            "created_at": datetime.now(timezone.utc),
            "responded_at": None
        }
        
        await db.contact_messages.insert_one(contact_record)
        
        logger.info(f"New contact form submission from {request.email}")
        
        return {
            "success": True,
            "message": "Thank you for your message! We'll get back to you within 24-48 hours.",
            "ticket_id": contact_record["id"]
        }
        
    except Exception as e:
        logger.error(f"Contact form error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to submit contact form")

@api_router.get("/support/conversation-history")
async def get_conversation_history(user: dict = Depends(get_current_user)):
    """Get user's support conversation history."""
    try:
        conversations = await db.support_conversations.find(
            {"user_id": user["id"]},
            {"_id": 0}
        ).sort("updated_at", -1).limit(10).to_list(10)
        
        return {"conversations": conversations}
        
    except Exception as e:
        logger.error(f"Error fetching conversation history: {str(e)}")
        return {"conversations": []}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()