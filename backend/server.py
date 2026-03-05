from fastapi import FastAPI, APIRouter, HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Dict, Any, Optional
import uuid
from datetime import datetime, timezone, timedelta
from wallet_service import WalletService
from auth_service import AuthService
from stripe_service import StripeService
from multi_chain_service import MultiChainService
from tax_report_service import tax_report_service
from fastapi.responses import Response


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

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
        last_reset = datetime.fromisoformat(last_reset)
    
    now = datetime.now(timezone.utc)
    if (now - last_reset).days >= 1:
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

@api_router.post("/payments/webhook/stripe")
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
                detail="Multi-chain analysis is a Premium feature. Upgrade to analyze Bitcoin, Polygon, Arbitrum, BSC, and Solana wallets."
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
        # Check if user has Unlimited
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro']:
            raise HTTPException(
                status_code=403, 
                detail="Analyze All Chains is an Unlimited feature. Upgrade to analyze across all blockchains simultaneously."
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
    address: str
    chain: str = "ethereum"
    filter_type: str = "all"  # all, short-term, long-term

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
        
        address = request.address.strip()
        chain = request.chain.lower()
        
        # Get wallet analysis with tax data
        analysis_data = multi_chain_service.analyze_wallet(
            address,
            chain=chain,
            user_tier=user_tier
        )
        
        # Check if tax data exists
        tax_data = analysis_data.get('tax_data')
        if not tax_data or not tax_data.get('realized_gains'):
            raise HTTPException(
                status_code=400,
                detail="No tax data available. Analyze the wallet first to generate tax information."
            )
        
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
        
        # Generate Form 8949 CSV
        csv_content = tax_report_service.generate_form_8949_csv(
            realized_gains=tax_data['realized_gains'],
            symbol=symbol,
            address=address,
            filter_type=request.filter_type
        )
        
        # Return as downloadable CSV
        filename = f"form-8949-{address[:8]}-{request.filter_type}-{datetime.now().strftime('%Y%m%d')}.csv"
        
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
    address: str
    chain: str = "ethereum"
    tax_year: int
    format: str = "text"  # text or csv

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
                detail="No tax data available for this wallet."
            )
        
        realized_gains = tax_data.get('realized_gains', [])
        
        symbol_map = {
            'ethereum': 'ETH',
            'bitcoin': 'BTC',
            'polygon': 'MATIC',
            'arbitrum': 'ETH',
            'bsc': 'BNB',
            'solana': 'SOL'
        }
        symbol = symbol_map.get(chain, 'ETH')
        
        # Generate based on format
        if request.format == 'csv':
            content = tax_report_service.generate_schedule_d_csv(
                realized_gains=realized_gains,
                tax_year=request.tax_year,
                symbol=symbol,
                address=address
            )
            media_type = "text/csv"
            filename = f"schedule-d-{address[:8]}-{request.tax_year}.csv"
        else:
            content = tax_report_service.generate_schedule_d_summary(
                realized_gains=realized_gains,
                tax_year=request.tax_year,
                symbol=symbol,
                address=address
            )
            media_type = "text/plain"
            filename = f"schedule-d-{address[:8]}-{request.tax_year}.txt"
        
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