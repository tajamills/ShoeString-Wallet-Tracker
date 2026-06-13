"""
Push Notification Routes for CryptoBagTracker
Handles Web Push subscription management and sending notifications
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from datetime import datetime, timezone
import os
import json
from pywebpush import webpush, WebPushException

from routes.dependencies import get_current_user

router = APIRouter()

# VAPID configuration
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_EMAIL = os.environ.get('VAPID_EMAIL', 'mailto:info@cryptobagtracker.io')

class PushSubscription(BaseModel):
    endpoint: str
    keys: Dict[str, str]
    expirationTime: Optional[int] = None

class PushSubscriptionRequest(BaseModel):
    subscription: PushSubscription

class TestPushRequest(BaseModel):
    title: Optional[str] = "Test Alert"
    body: Optional[str] = "This is a test push notification from CryptoBagTracker!"


def get_db():
    """Get the MongoDB database instance"""
    from motor.motor_asyncio import AsyncIOMotorClient
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    db_name = os.environ.get('DB_NAME', 'test_database')
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name]


@router.get("/vapid-public-key")
async def get_vapid_public_key():
    """Get the VAPID public key for push subscription"""
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=500, detail="Push notifications not configured")
    return {"publicKey": VAPID_PUBLIC_KEY}


@router.post("/subscribe")
async def subscribe_push(
    request: PushSubscriptionRequest,
    user: dict = Depends(get_current_user)
):
    """Subscribe to push notifications"""
    db = get_db()
    user_id = user.get("id") or user.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    subscription_data = {
        "user_id": user_id,
        "endpoint": request.subscription.endpoint,
        "keys": request.subscription.keys,
        "expiration_time": request.subscription.expirationTime,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "is_active": True
    }
    
    # Upsert subscription (update if endpoint exists, insert if new)
    await db.push_subscriptions.update_one(
        {"user_id": user_id, "endpoint": request.subscription.endpoint},
        {"$set": subscription_data},
        upsert=True
    )
    
    return {"success": True, "message": "Push notifications enabled"}


@router.delete("/unsubscribe")
async def unsubscribe_push(
    user: dict = Depends(get_current_user)
):
    """Unsubscribe from push notifications"""
    db = get_db()
    user_id = user.get("id") or user.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # Mark all subscriptions for this user as inactive
    result = await db.push_subscriptions.update_many(
        {"user_id": user_id},
        {"$set": {"is_active": False, "updated_at": datetime.now(timezone.utc)}}
    )
    
    return {"success": True, "message": "Push notifications disabled", "count": result.modified_count}


@router.get("/status")
async def get_push_status(
    user: dict = Depends(get_current_user)
):
    """Get push notification subscription status"""
    db = get_db()
    user_id = user.get("id") or user.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    subscription = await db.push_subscriptions.find_one(
        {"user_id": user_id, "is_active": True},
        {"_id": 0}
    )
    
    count = await db.push_subscriptions.count_documents({"user_id": user_id, "is_active": True})
    
    return {
        "subscribed": subscription is not None,
        "subscription_count": count
    }


@router.post("/test")
async def send_test_push(
    request: TestPushRequest,
    user: dict = Depends(get_current_user)
):
    """Send a test push notification"""
    db = get_db()
    user_id = user.get("id") or user.get("user_id")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="User not authenticated")
    
    # Get active subscriptions for this user
    subscriptions = await db.push_subscriptions.find(
        {"user_id": user_id, "is_active": True},
        {"_id": 0}
    ).to_list(length=100)
    
    if not subscriptions:
        raise HTTPException(status_code=400, detail="No active push subscriptions found. Enable push notifications first.")
    
    # Send to all active subscriptions
    sent_count = 0
    failed_count = 0
    
    for sub in subscriptions:
        try:
            send_push_notification(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": sub["keys"]
                },
                title=request.title,
                body=request.body
            )
            sent_count += 1
        except Exception as e:
            print(f"Failed to send push: {e}")
            failed_count += 1
            # If subscription is invalid, mark it as inactive
            if "410" in str(e) or "404" in str(e):
                await db.push_subscriptions.update_one(
                    {"endpoint": sub["endpoint"]},
                    {"$set": {"is_active": False}}
                )
    
    if sent_count == 0:
        raise HTTPException(status_code=500, detail="Failed to send push notification")
    
    return {
        "success": True,
        "sent": sent_count,
        "failed": failed_count,
        "message": f"Test notification sent to {sent_count} device(s)"
    }


def send_push_notification(subscription_info: dict, title: str, body: str, data: dict = None):
    """Send a push notification to a subscription"""
    if not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        raise Exception("VAPID keys not configured")
    
    payload = json.dumps({
        "title": title,
        "body": body,
        "icon": "/favicon.png",
        "badge": "/favicon.png",
        "tag": "price-alert",
        "data": data or {}
    })
    
    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_EMAIL}
        )
        return True
    except WebPushException as e:
        print(f"WebPush error: {e}")
        raise e


async def send_push_to_user(db, user_id: str, title: str, body: str, data: dict = None):
    """Helper function to send push notification to all of a user's devices"""
    subscriptions = await db.push_subscriptions.find(
        {"user_id": user_id, "is_active": True},
        {"_id": 0}
    ).to_list(length=100)
    
    sent_count = 0
    for sub in subscriptions:
        try:
            send_push_notification(
                subscription_info={
                    "endpoint": sub["endpoint"],
                    "keys": sub["keys"]
                },
                title=title,
                body=body,
                data=data
            )
            sent_count += 1
        except Exception as e:
            print(f"Failed to send push to user {user_id}: {e}")
            # Mark invalid subscriptions as inactive
            if "410" in str(e) or "404" in str(e):
                await db.push_subscriptions.update_one(
                    {"endpoint": sub["endpoint"]},
                    {"$set": {"is_active": False}}
                )
    
    return sent_count
