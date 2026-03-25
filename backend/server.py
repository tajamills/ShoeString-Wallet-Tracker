"""
Crypto Bag Tracker API Server
Refactored to use modular route files for better maintainability.
"""
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict
from typing import List
from datetime import datetime, timezone
import os
import logging
import uuid
import sentry_sdk
from pathlib import Path

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Initialize Sentry for error monitoring
SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        traces_sample_rate=0.2,
        environment=os.environ.get("ENVIRONMENT", "production"),
        send_default_pii=False,
    )
    logging.info("Sentry initialized for error monitoring")

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create the main app
app = FastAPI(
    title="Crypto Bag Tracker API",
    description="API for analyzing cryptocurrency wallet transactions and generating tax reports",
    version="2.0.0"
)

# Create main API router with /api prefix
api_router = APIRouter(prefix="/api")


# Status Check Models (kept in main file for simplicity)
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


# Root and Status endpoints
@api_router.get("/")
async def root():
    return {"message": "Crypto Bag Tracker API v2.0", "status": "healthy"}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks


# Import and include route modules
from routes.auth import router as auth_router
from routes.payments import router as payments_router
from routes.wallets import router as wallets_router
from routes.tax import router as tax_router
from routes.affiliates import router as affiliates_router
from routes.exchanges import router as exchanges_router
from routes.custody import router as custody_router
from routes.support import router as support_router

# Include all route modules
api_router.include_router(auth_router)
api_router.include_router(payments_router)
api_router.include_router(wallets_router)
api_router.include_router(tax_router)
api_router.include_router(affiliates_router)
api_router.include_router(exchanges_router)
api_router.include_router(custody_router)
api_router.include_router(support_router)

# Alias routes for backwards compatibility
@api_router.post("/webhook")
async def webhook_alias(request: Request):
    """Alias for Stripe webhook - redirects to /payments/webhook/stripe"""
    from routes.payments import handle_stripe_webhook
    return await handle_stripe_webhook(request)


@api_router.post("/admin/test-email")
async def admin_test_email_alias(request: Request):
    """Alias for admin test email endpoint"""
    from routes.payments import send_test_email
    from routes.dependencies import get_current_user, security
    from fastapi.security import HTTPAuthorizationCredentials
    
    # Get auth header
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(credentials)
        return await send_test_email(request, user=user)
    raise HTTPException(status_code=401, detail="Not authenticated")


# Legacy alias routes for frontend compatibility
@api_router.post("/exchange/connect")
async def exchange_connect_alias(request: Request):
    """Alias for /exchanges/connect-api"""
    from routes.exchanges import connect_exchange_api
    from routes.dependencies import get_current_user, security
    from routes.models import ExchangeConnectionRequest
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(credentials)
        body = await request.json()
        req = ExchangeConnectionRequest(**body)
        return await connect_exchange_api(req, user)
    raise HTTPException(status_code=401, detail="Not authenticated")


@api_router.delete("/exchange/disconnect/{exchange}")
async def exchange_disconnect_alias(exchange: str, request: Request):
    """Alias for /exchanges/disconnect-api/{exchange}"""
    from routes.exchanges import disconnect_exchange_api
    from routes.dependencies import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(credentials)
        return await disconnect_exchange_api(exchange, user)
    raise HTTPException(status_code=401, detail="Not authenticated")


@api_router.get("/exchange/addresses/{exchange}")
async def exchange_addresses_alias(exchange: str, request: Request):
    """Alias for /exchanges/addresses-for-custody/{exchange}"""
    from routes.exchanges import get_exchange_addresses_for_custody
    from routes.dependencies import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(credentials)
        return await get_exchange_addresses_for_custody(exchange, user)
    raise HTTPException(status_code=401, detail="Not authenticated")


# Admin routes for transaction cleanup (kept in main file)
@api_router.post("/admin/cleanup-transactions")
async def cleanup_exchange_transactions(request: Request):
    """Clean up existing exchange transactions by applying validation rules"""
    from routes.dependencies import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header[7:]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(credentials)
    
    try:
        from csv_parser_service import ExchangeTransaction
        
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
                await db.exchange_transactions.delete_one({"_id": tx_id})
                removed_count += 1
                removed_details.append({
                    "asset": asset,
                    "original_amount": original_amount,
                    "reason": "amount exceeded maximum allowed"
                })
            elif validated_amount != original_amount:
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
async def clear_exchange_transactions(request: Request):
    """Delete ALL exchange transactions for this user"""
    from routes.dependencies import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header[7:]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(credentials)
    
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
async def get_exchange_transactions_summary(request: Request):
    """Get a summary of exchange transactions"""
    from routes.dependencies import get_current_user
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header[7:]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(credentials)
    
    try:
        total = await db.exchange_transactions.count_documents({"user_id": user["id"]})
        
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


# Coinbase OAuth routes (kept for backwards compatibility)
from coinbase_oauth_service import coinbase_oauth_service, OAUTH_SCOPES
from routes.dependencies import get_current_user

@api_router.get("/coinbase/auth-url")
async def get_coinbase_auth_url(request: Request):
    """Get Coinbase OAuth authorization URL"""
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header[7:]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(credentials)
    
    try:
        user_tier = user.get('subscription_tier', 'free')
        if user_tier not in ['unlimited', 'pro', 'premium']:
            raise HTTPException(
                status_code=403,
                detail="Coinbase integration requires a paid subscription."
            )
        
        auth_url, state = coinbase_oauth_service.get_authorization_url()
        
        await db.coinbase_oauth_states.insert_one({
            "state": state,
            "user_id": user["id"],
            "created_at": datetime.now(timezone.utc)
        })
        
        return {
            "auth_url": auth_url,
            "state": state,
            "scopes": OAUTH_SCOPES,
            "security_note": "This app only requests READ-ONLY access."
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating Coinbase auth URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate authorization URL")


@api_router.post("/coinbase/callback")
async def coinbase_oauth_callback(code: str, state: str, request: Request):
    """Handle Coinbase OAuth callback"""
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header[7:]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(credentials)
    
    try:
        state_record = await db.coinbase_oauth_states.find_one({
            "state": state,
            "user_id": user["id"]
        })
        
        if not state_record:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        await db.coinbase_oauth_states.delete_one({"state": state})
        
        tokens = await coinbase_oauth_service.exchange_code_for_tokens(code)
        
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
async def get_coinbase_connection_status(request: Request):
    """Check if user has connected their Coinbase account"""
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header[7:]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(credentials)
    
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
async def disconnect_coinbase(request: Request):
    """Disconnect Coinbase account and delete stored tokens"""
    from fastapi.security import HTTPAuthorizationCredentials
    
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = auth_header[7:]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = await get_current_user(credentials)
    
    try:
        result = await db.coinbase_connections.delete_one({"user_id": user["id"]})
        
        if result.deleted_count > 0:
            logger.info(f"Coinbase disconnected for user {user['id']}")
            return {"success": True, "message": "Coinbase account disconnected"}
        
        return {"success": False, "message": "No Coinbase account connected"}
    
    except Exception as e:
        logger.error(f"Error disconnecting Coinbase: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to disconnect Coinbase account")


# Include the main router
app.include_router(api_router)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for downloads
static_dir = ROOT_DIR / "static" / "downloads"
if static_dir.exists():
    app.mount("/downloads", StaticFiles(directory=str(static_dir)), name="downloads")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
