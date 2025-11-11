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
    start_date: Optional[str] = None  # Format: YYYY-MM-DD
    end_date: Optional[str] = None    # Format: YYYY-MM-DD

class WalletAnalysisResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str
    totalEthSent: float
    totalEthReceived: float
    totalGasFees: float
    netEth: float
    outgoingTransactionCount: int
    incomingTransactionCount: int
    tokensSent: Dict[str, float]
    tokensReceived: Dict[str, float]
    recentTransactions: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# Initialize services
wallet_service = WalletService()
auth_service = AuthService()
nowpayments_service = NOWPaymentsService()
security = HTTPBearer()

# User Models
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    subscription_tier: str = "free"  # free, premium, pro
    daily_usage_count: int = 0
    last_usage_reset: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    payment_id: str  # NOWPayments payment_id
    order_id: str
    amount_usd: float
    amount_crypto: float
    crypto_address: str
    crypto_currency: str  # usdc, btc, etc.
    status: str  # waiting, confirming, confirmed, failed, expired
    subscription_tier: str
    payment_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: Optional[datetime] = None

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
    
    # Check limits based on tier
    tier = user.get("subscription_tier", "free")
    daily_limit = {
        "free": 1,
        "premium": 999999,  # Unlimited
        "pro": 999999  # Unlimited
    }.get(tier, 1)
    
    if user.get("daily_usage_count", 0) >= daily_limit:
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit reached. Upgrade to Premium for unlimited analyses."
        )
    
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
        created_at=user.created_at
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
        created_at=created_at
    )
    
    return TokenResponse(access_token=access_token, user=user_response)

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(user: dict = Depends(get_current_user)):
    """Get current user info"""
    created_at = datetime.fromisoformat(user["created_at"]) if isinstance(user["created_at"], str) else user["created_at"]
    
    return UserResponse(
        id=user["id"],
        email=user["email"],
        subscription_tier=user["subscription_tier"],
        daily_usage_count=user["daily_usage_count"],
        created_at=created_at
    )

# Payment Routes
@api_router.post("/payments/create-upgrade")
async def create_upgrade_payment(
    request: UpgradeRequest,
    user: dict = Depends(get_current_user)
):
    """Create USDC payment for subscription upgrade"""
    try:
        # Determine price based on tier (increased to meet NOWPayments minimum)
        tier_prices = {
            "premium": 99.00,
            "pro": 199.00
        }
        
        if request.tier not in tier_prices:
            raise HTTPException(status_code=400, detail="Invalid subscription tier")
        
        price_usd = tier_prices[request.tier]
        
        # Create unique order ID
        order_id = f"upgrade_{user['id']}_{request.tier}_{int(datetime.now(timezone.utc).timestamp())}"
        
        # Create payment with NOWPayments using USDC
        payment_data = await nowpayments_service.create_payment(
            price_amount=price_usd,
            price_currency="usd",
            pay_currency="usdcbsc",  # USDC on Binance Smart Chain (lowest fees)
            order_id=order_id,
            order_description=f"Upgrade to {request.tier.upper()} subscription",
            ipn_callback_url=f"{os.environ.get('BACKEND_URL', 'http://localhost:8001')}/api/payments/webhook",
            success_url=f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/payment-success",
            cancel_url=f"{os.environ.get('FRONTEND_URL', 'http://localhost:3000')}/payment-cancelled"
        )
        
        # Store payment in database
        payment = Payment(
            user_id=user["id"],
            payment_id=payment_data["payment_id"],
            order_id=order_id,
            amount_usd=price_usd,
            amount_crypto=float(payment_data["pay_amount"]),
            crypto_address=payment_data["pay_address"],
            crypto_currency="usdcbsc",
            status=payment_data["payment_status"],
            subscription_tier=request.tier,
            payment_url=payment_data.get("payment_url", "")
        )
        
        doc = payment.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        if doc.get('confirmed_at'):
            doc['confirmed_at'] = doc['confirmed_at'].isoformat()
        
        await db.payments.insert_one(doc)
        
        logger.info(f"Payment created for user {user['id']}: {payment_data['payment_id']}")
        
        return {
            "payment_id": payment_data["payment_id"],
            "crypto_address": payment_data["pay_address"],
            "crypto_amount": payment_data["pay_amount"],
            "crypto_currency": "USDC",
            "usd_amount": price_usd,
            "status": payment_data["payment_status"],
            "payment_url": payment_data.get("payment_url", ""),
            "order_id": order_id
        }
        
    except Exception as e:
        logger.error(f"Failed to create payment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Payment creation failed: {str(e)}")

@api_router.post("/payments/webhook")
async def handle_nowpayments_webhook(request: Request):
    """Handle NOWPayments IPN (Instant Payment Notification) webhook"""
    try:
        # Get request body and signature
        body = await request.body()
        signature = request.headers.get("x-nowpayments-sig", "")
        
        # Verify signature
        if signature and not nowpayments_service.verify_ipn_signature(body.decode(), signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse webhook data
        data = json.loads(body)
        
        payment_id = data.get("payment_id")
        payment_status = data.get("payment_status")
        order_id = data.get("order_id")
        
        logger.info(f"Webhook received for payment {payment_id}: status={payment_status}")
        
        # Find payment in database
        payment_doc = await db.payments.find_one({"payment_id": payment_id})
        
        if not payment_doc:
            logger.error(f"Payment not found: {payment_id}")
            return {"status": "error", "message": "Payment not found"}
        
        # Update payment status
        update_data = {"status": payment_status}
        
        # If payment is confirmed, upgrade user subscription
        if payment_status in ["confirmed", "finished"]:
            update_data["confirmed_at"] = datetime.now(timezone.utc).isoformat()
            
            # Upgrade user subscription
            user_id = payment_doc["user_id"]
            subscription_tier = payment_doc["subscription_tier"]
            
            await db.users.update_one(
                {"id": user_id},
                {
                    "$set": {
                        "subscription_tier": subscription_tier,
                        "daily_usage_count": 0,
                        "last_usage_reset": datetime.now(timezone.utc).isoformat()
                    }
                }
            )
            
            logger.info(f"User {user_id} upgraded to {subscription_tier}")
        
        # Update payment document
        await db.payments.update_one(
            {"payment_id": payment_id},
            {"$set": update_data}
        )
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")

@api_router.get("/payments/status/{payment_id}")
async def get_payment_status(
    payment_id: str,
    user: dict = Depends(get_current_user)
):
    """Check payment status"""
    try:
        # Get from database
        payment_doc = await db.payments.find_one(
            {"payment_id": payment_id, "user_id": user["id"]},
            {"_id": 0}
        )
        
        if not payment_doc:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # Also check with NOWPayments API for latest status
        try:
            live_status = await nowpayments_service.get_payment_status(payment_id)
            payment_doc["live_status"] = live_status.get("payment_status")
        except:
            pass
        
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
    """Analyze a crypto wallet and calculate statistics (requires authentication)"""
    try:
        # Validate address format (basic check)
        address = request.address.strip()
        if not address.startswith('0x') or len(address) != 42:
            raise HTTPException(status_code=400, detail="Invalid Ethereum address format")
        
        # Analyze wallet using wallet service
        analysis_data = wallet_service.analyze_wallet(
            address, 
            start_date=request.start_date,
            end_date=request.end_date
        )
        
        # Create response object
        analysis_response = WalletAnalysisResponse(
            address=analysis_data['address'],
            totalEthSent=analysis_data['totalEthSent'],
            totalEthReceived=analysis_data['totalEthReceived'],
            totalGasFees=analysis_data['totalGasFees'],
            netEth=analysis_data['netEth'],
            outgoingTransactionCount=analysis_data['outgoingTransactionCount'],
            incomingTransactionCount=analysis_data['incomingTransactionCount'],
            tokensSent=analysis_data['tokensSent'],
            tokensReceived=analysis_data['tokensReceived'],
            recentTransactions=analysis_data['recentTransactions']
        )
        
        # Store in database with user info
        doc = analysis_response.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        doc['user_id'] = user['id']
        await db.wallet_analyses.insert_one(doc)
        
        # Increment user's daily usage count
        await db.users.update_one(
            {"id": user["id"]},
            {"$inc": {"daily_usage_count": 1}}
        )
        
        return analysis_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing wallet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze wallet: {str(e)}")

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