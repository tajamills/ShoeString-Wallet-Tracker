"""Shared dependencies and utilities for route modules"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path
import os
import logging

# Load environment variables
ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

from auth_service import AuthService

logger = logging.getLogger(__name__)

# MongoDB connection (lazy initialization)
_client = None
_db = None

def get_db():
    global _client, _db
    if _db is None:
        mongo_url = os.environ['MONGO_URL']
        _client = AsyncIOMotorClient(mongo_url)
        _db = _client[os.environ['DB_NAME']]
    return _db

# Create property-like access for db
class DBProxy:
    def __getattr__(self, name):
        return getattr(get_db(), name)

db = DBProxy()

# Security
security = HTTPBearer()
auth_service = AuthService()


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
    last_reset = user.get("last_usage_reset")
    if isinstance(last_reset, str):
        last_reset = datetime.fromisoformat(last_reset.replace('Z', '+00:00'))
    
    if last_reset and last_reset.tzinfo is None:
        last_reset = last_reset.replace(tzinfo=timezone.utc)
    
    now = datetime.now(timezone.utc)
    if last_reset and (now - last_reset).days >= 1:
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
    
    tier = user.get("subscription_tier", "free")
    
    if tier == "free":
        total_analyses = user.get("analysis_count", 0)
        if total_analyses >= 1:
            raise HTTPException(
                status_code=429,
                detail="You've used your free analysis. Upgrade to Unlimited for unlimited analyses."
            )
    
    return user


def require_paid_tier(user: dict) -> None:
    """Raise 403 if user is on free tier"""
    if user.get('subscription_tier', 'free') == 'free':
        raise HTTPException(
            status_code=403,
            detail="This feature requires a paid subscription."
        )


def require_unlimited_tier(user: dict) -> None:
    """Raise 403 if user doesn't have unlimited tier"""
    if user.get('subscription_tier', 'free') not in ['unlimited', 'pro', 'premium']:
        raise HTTPException(
            status_code=403,
            detail="This feature requires an Unlimited subscription."
        )


def get_current_quarter():
    """Get current quarter string like '2026-Q1'"""
    now = datetime.now()
    quarter = (now.month - 1) // 3 + 1
    return f"{now.year}-Q{quarter}"
