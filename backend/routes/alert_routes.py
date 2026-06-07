"""
Alert Routes - API endpoints for price alerts
"""
from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import uuid
import logging
import os
import stripe

from .dependencies import db, get_current_user
from models.alert_models import (
    CreateAlertRequest, 
    UpdateAlertRequest, 
    AlertResponse,
    AlertStatus,
    ALERT_TIERS,
    STRIPE_ALERT_PRICE_ID,
    STRIPE_ALERT_PRODUCT_ID
)
from services.alert_service import alert_service
from services.telegram_service import get_bot_info, send_telegram_message

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.environ.get("STRIPE_API_KEY", "")

# Trial period in days
FREE_TRIAL_DAYS = 7


async def get_user_subscription(user_id: str) -> dict:
    """Get user's alert subscription status"""
    subscription = await db.alert_subscriptions.find_one(
        {"user_id": user_id},
        {"_id": 0}
    )
    
    if not subscription:
        return {
            "status": "none",
            "tier": "free",
            "trial_used": False,
            "trial_ends_at": None,
            "subscription_ends_at": None
        }
    
    # Check if trial has expired
    if subscription.get("status") == "trialing":
        trial_ends = subscription.get("trial_ends_at")
        if trial_ends:
            # Ensure trial_ends is timezone-aware
            if isinstance(trial_ends, datetime):
                if trial_ends.tzinfo is None:
                    trial_ends = trial_ends.replace(tzinfo=timezone.utc)
            elif isinstance(trial_ends, str):
                trial_ends = datetime.fromisoformat(trial_ends.replace("Z", "+00:00"))
            
            if datetime.now(timezone.utc) > trial_ends:
                # Trial expired
                await db.alert_subscriptions.update_one(
                    {"user_id": user_id},
                    {"$set": {"status": "expired", "tier": "expired"}}
                )
                subscription["status"] = "expired"
                subscription["tier"] = "expired"
    
    return subscription


def get_user_tier(user: dict) -> str:
    """Get user's alert subscription tier"""
    return user.get("alert_tier", "free")


def get_max_alerts(tier: str) -> int:
    """Get maximum alerts allowed for a tier"""
    tier_info = ALERT_TIERS.get(tier, ALERT_TIERS["free"])
    return tier_info.max_alerts


async def check_subscription_access(user_id: str) -> tuple:
    """Check if user has access to create alerts. Returns (has_access, subscription_info)"""
    subscription = await get_user_subscription(user_id)
    status = subscription.get("status", "none")
    
    if status in ["trialing", "active"]:
        return True, subscription
    
    return False, subscription


@router.get("/tiers")
async def get_alert_tiers(user: dict = Depends(get_current_user)):
    """Get available alert subscription tiers and current user status"""
    subscription = await get_user_subscription(user["id"])
    
    return {
        "tiers": {k: v.dict() for k, v in ALERT_TIERS.items()},
        "current_status": subscription.get("status", "none"),
        "current_tier": subscription.get("tier", "free"),
        "trial_used": subscription.get("trial_used", False),
        "trial_ends_at": subscription.get("trial_ends_at"),
        "subscription_ends_at": subscription.get("subscription_ends_at"),
        "stripe_price_id": STRIPE_ALERT_PRICE_ID
    }


@router.post("/start-trial")
async def start_free_trial(user: dict = Depends(get_current_user)):
    """Start a 7-day free trial for alerts"""
    user_id = user["id"]
    
    # Check if user already has a subscription or used trial
    existing = await db.alert_subscriptions.find_one({"user_id": user_id})
    
    if existing:
        if existing.get("trial_used"):
            raise HTTPException(
                status_code=400,
                detail="You have already used your free trial. Please subscribe to continue."
            )
        if existing.get("status") in ["active", "trialing"]:
            raise HTTPException(
                status_code=400,
                detail="You already have an active subscription or trial."
            )
    
    # Start trial
    trial_ends = datetime.now(timezone.utc) + timedelta(days=FREE_TRIAL_DAYS)
    
    await db.alert_subscriptions.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "status": "trialing",
            "tier": "unlimited",
            "trial_used": True,
            "trial_started_at": datetime.now(timezone.utc),
            "trial_ends_at": trial_ends,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc)
        }},
        upsert=True
    )
    
    logger.info(f"Started free trial for user {user_id}, ends {trial_ends}")
    
    return {
        "success": True,
        "message": f"Your {FREE_TRIAL_DAYS}-day free trial has started!",
        "trial_ends_at": trial_ends.isoformat(),
        "status": "trialing",
        "tier": "unlimited"
    }


@router.post("/create-checkout")
async def create_checkout_session(user: dict = Depends(get_current_user)):
    """Create a Stripe checkout session for alert subscription"""
    user_id = user["id"]
    user_email = user.get("email", "")
    
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Payment system not configured")
    
    try:
        # Check if already subscribed
        subscription = await get_user_subscription(user_id)
        if subscription.get("status") == "active":
            raise HTTPException(status_code=400, detail="You already have an active subscription")
        
        # Determine if user gets free trial with subscription
        trial_days = FREE_TRIAL_DAYS if not subscription.get("trial_used") else 0
        
        # Create Stripe checkout session
        frontend_url = os.environ.get("FRONTEND_URL", "https://proceeds-validator.preview.emergentagent.com")
        
        session_params = {
            "mode": "subscription",
            "payment_method_types": ["card"],
            "line_items": [{
                "price": STRIPE_ALERT_PRICE_ID,
                "quantity": 1
            }],
            "success_url": f"{frontend_url}?alert_payment=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{frontend_url}?alert_payment=canceled",
            "customer_email": user_email,
            "client_reference_id": user_id,
            "metadata": {
                "user_id": user_id,
                "product_type": "alert_subscription"
            }
        }
        
        # Add trial period if user hasn't used it
        if trial_days > 0:
            session_params["subscription_data"] = {
                "trial_period_days": trial_days,
                "metadata": {"user_id": user_id}
            }
        
        session = stripe.checkout.Session.create(**session_params)
        
        logger.info(f"Created Stripe checkout session for user {user_id}: {session.id}")
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "trial_days": trial_days
        }
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=500, detail=f"Payment error: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/stripe")
async def handle_alert_stripe_webhook(request: Request):
    """Handle Stripe webhook events for alert subscriptions"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    
    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        else:
            # For testing without webhook signature verification
            import json
            event = json.loads(payload)
            event = stripe.Event.construct_from(event, stripe.api_key)
        
        event_type = event["type"]
        data = event["data"]["object"]
        
        logger.info(f"Alert webhook received: {event_type}")
        
        if event_type == "checkout.session.completed":
            user_id = data.get("client_reference_id") or data.get("metadata", {}).get("user_id")
            subscription_id = data.get("subscription")
            
            if user_id and subscription_id:
                await db.alert_subscriptions.update_one(
                    {"user_id": user_id},
                    {"$set": {
                        "status": "active",
                        "tier": "unlimited",
                        "stripe_subscription_id": subscription_id,
                        "stripe_customer_id": data.get("customer"),
                        "updated_at": datetime.now(timezone.utc)
                    }},
                    upsert=True
                )
                logger.info(f"Activated alert subscription for user {user_id}")
        
        elif event_type == "customer.subscription.updated":
            subscription_id = data.get("id")
            status = data.get("status")
            
            # Map Stripe status to our status
            status_map = {
                "trialing": "trialing",
                "active": "active",
                "past_due": "past_due",
                "canceled": "canceled",
                "unpaid": "expired"
            }
            
            our_status = status_map.get(status, status)
            
            await db.alert_subscriptions.update_one(
                {"stripe_subscription_id": subscription_id},
                {"$set": {
                    "status": our_status,
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            logger.info(f"Updated subscription {subscription_id} to status {our_status}")
        
        elif event_type == "customer.subscription.deleted":
            subscription_id = data.get("id")
            
            await db.alert_subscriptions.update_one(
                {"stripe_subscription_id": subscription_id},
                {"$set": {
                    "status": "canceled",
                    "tier": "expired",
                    "updated_at": datetime.now(timezone.utc)
                }}
            )
            logger.info(f"Canceled subscription {subscription_id}")
        
        return {"received": True}
        
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/subscription")
async def get_subscription_status(user: dict = Depends(get_current_user)):
    """Get current user's subscription status"""
    subscription = await get_user_subscription(user["id"])
    
    # Calculate days remaining for trial
    days_remaining = None
    if subscription.get("status") == "trialing" and subscription.get("trial_ends_at"):
        trial_ends = subscription["trial_ends_at"]
        if isinstance(trial_ends, datetime):
            if trial_ends.tzinfo is None:
                trial_ends = trial_ends.replace(tzinfo=timezone.utc)
        elif isinstance(trial_ends, str):
            trial_ends = datetime.fromisoformat(trial_ends.replace("Z", "+00:00"))
        days_remaining = max(0, (trial_ends - datetime.now(timezone.utc)).days)
    
    return {
        "status": subscription.get("status", "none"),
        "tier": subscription.get("tier", "free"),
        "trial_used": subscription.get("trial_used", False),
        "trial_ends_at": subscription.get("trial_ends_at"),
        "days_remaining": days_remaining,
        "subscription_ends_at": subscription.get("subscription_ends_at"),
        "can_create_alerts": subscription.get("status") in ["trialing", "active"]
    }


@router.get("/search")
async def search_assets(
    q: str = Query(..., min_length=1, description="Search query"),
    asset_type: Optional[str] = Query(None, description="Filter by asset type (crypto/stock)"),
    user: dict = Depends(get_current_user)
):
    """Search for assets to create alerts for"""
    try:
        results = await alert_service.search_assets(q, asset_type)
        return {"results": results, "query": q}
    except Exception as e:
        logger.error(f"Error searching assets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/price/{asset_type}/{symbol}")
async def get_asset_price(
    asset_type: str,
    symbol: str,
    user: dict = Depends(get_current_user)
):
    """Get current price for an asset (authenticated)"""
    if asset_type not in ["crypto", "stock"]:
        raise HTTPException(status_code=400, detail="Invalid asset type. Use 'crypto' or 'stock'")
    
    try:
        price_data = await alert_service.get_price(symbol, asset_type)
        if not price_data:
            raise HTTPException(status_code=404, detail=f"Could not fetch price for {symbol}")
        return price_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching price: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/public/price/{symbol}")
async def get_public_price(symbol: str):
    """Get current price for a crypto asset (public, no auth required)"""
    try:
        price_data = await alert_service.get_price(symbol.upper(), "crypto")
        if not price_data:
            return {"symbol": symbol.upper(), "price": None, "change_24h": None}
        return price_data
    except Exception as e:
        logger.error(f"Error fetching public price: {e}")
        return {"symbol": symbol.upper(), "price": None, "change_24h": None}


@router.get("/public/supported-coins")
async def get_supported_coins_public():
    """Get list of all supported cryptocurrencies (public endpoint)"""
    try:
        supported = []
        iso20022_coins = {"XRP", "XLM", "ALGO", "XDC", "IOTA", "HBAR", "QNT", "ADA", "XTZ"}
        
        crypto_map = {
            "XRP": ("Ripple", True), "XLM": ("Stellar", True), "ALGO": ("Algorand", True),
            "XDC": ("XDC Network", True), "IOTA": ("IOTA", True), "HBAR": ("Hedera", True),
            "QNT": ("Quant", True), "ADA": ("Cardano", True), "XTZ": ("Tezos", True),
            "BTC": ("Bitcoin", False), "ETH": ("Ethereum", False), "BNB": ("BNB", False),
            "SOL": ("Solana", False), "DOGE": ("Dogecoin", False), "TRX": ("Tron", False),
            "TON": ("Toncoin", False), "DOT": ("Polkadot", False), "MATIC": ("Polygon", False),
            "LINK": ("Chainlink", False), "AVAX": ("Avalanche", False), "SHIB": ("Shiba Inu", False),
            "LTC": ("Litecoin", False), "BCH": ("Bitcoin Cash", False), "UNI": ("Uniswap", False),
            "ATOM": ("Cosmos", False), "NEAR": ("NEAR Protocol", False), "APT": ("Aptos", False),
            "FIL": ("Filecoin", False), "ICP": ("Internet Computer", False), "VET": ("VeChain", False),
            "INJ": ("Injective", False), "OP": ("Optimism", False), "ARB": ("Arbitrum", False),
            "SUI": ("Sui", False), "SEI": ("Sei", False), "TIA": ("Celestia", False),
            "FTM": ("Fantom", False), "AAVE": ("Aave", False), "MKR": ("Maker", False),
            "GRT": ("The Graph", False), "THETA": ("Theta", False), "RENDER": ("Render", False),
            "SAND": ("The Sandbox", False), "MANA": ("Decentraland", False), "AXS": ("Axie Infinity", False),
            "PEPE": ("Pepe", False), "WIF": ("dogwifhat", False), "BONK": ("Bonk", False),
            "FLOKI": ("Floki", False), "ORDI": ("Ordinals", False),
        }
        
        for symbol, (name, is_iso) in crypto_map.items():
            supported.append({
                "symbol": symbol,
                "name": name,
                "is_iso20022": is_iso
            })
        
        supported.sort(key=lambda x: (not x["is_iso20022"], x["symbol"]))
        
        return {
            "total": len(supported),
            "iso20022_count": len(iso20022_coins),
            "coins": supported
        }
    except Exception as e:
        logger.error(f"Error fetching supported coins: {e}")
        return {"total": 0, "coins": []}


@router.post("")
async def create_alert(
    request: CreateAlertRequest,
    user: dict = Depends(get_current_user)
):
    """Create a new price alert"""
    try:
        user_id = user["id"]
        
        # Check subscription status
        has_access, subscription = await check_subscription_access(user_id)
        
        if not has_access:
            status = subscription.get("status", "none")
            if status == "expired":
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "trial_expired",
                        "message": "Your free trial has expired. Subscribe to continue creating alerts.",
                        "action": "subscribe"
                    }
                )
            else:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "no_subscription",
                        "message": "Start your free trial or subscribe to create alerts.",
                        "action": "start_trial"
                    }
                )
        
        # Get current price
        price_data = await alert_service.get_price(
            request.asset_symbol, 
            request.asset_type.value
        )
        current_price = price_data.get("price", 0) if price_data else 0
        
        # Create alert document
        alert_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        # Get user email for notifications
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
        user_email = user_doc.get("email") if user_doc else None
        
        alert_doc = {
            "alert_id": alert_id,
            "user_id": user_id,
            "user_email": user_email,
            "asset_symbol": request.asset_symbol.upper(),
            "asset_type": request.asset_type.value,
            "alert_type": request.alert_type.value,
            "target_value": request.target_value,
            "current_price": current_price,
            "notification_method": request.notification_method.value,
            "phone_number": request.phone_number,
            "status": AlertStatus.ACTIVE.value,
            "note": request.note,
            "created_at": now,
            "updated_at": now,
            "triggered_at": None,
            "last_checked": now,
            "trigger_count": 0
        }
        
        await db.alerts.insert_one(alert_doc)
        
        # Count total alerts for response
        total_alerts = await db.alerts.count_documents({
            "user_id": user_id,
            "status": {"$in": ["active", "paused"]}
        })
        
        logger.info(f"Created alert {alert_id} for user {user_id}: {request.asset_symbol} {request.alert_type.value} {request.target_value}")
        
        return {
            "success": True,
            "alert": {
                "id": alert_id,
                "asset_symbol": request.asset_symbol.upper(),
                "asset_type": request.asset_type.value,
                "alert_type": request.alert_type.value,
                "target_value": request.target_value,
                "current_price": current_price,
                "notification_method": request.notification_method.value,
                "status": AlertStatus.ACTIVE.value,
                "created_at": now
            },
            "total_alerts": total_alerts,
            "subscription_status": subscription.get("status"),
            "alerts_remaining": "unlimited"  # Unlimited during trial/subscription
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
async def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status"),
    asset_type: Optional[str] = Query(None, description="Filter by asset type"),
    user: dict = Depends(get_current_user)
):
    """Get all alerts for the current user"""
    try:
        user_id = user["id"]
        
        query = {"user_id": user_id}
        if status:
            query["status"] = status
        if asset_type:
            query["asset_type"] = asset_type
        
        alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
        
        # Get current prices for active alerts
        for alert in alerts:
            if alert.get("status") == "active":
                price_data = await alert_service.get_price(
                    alert["asset_symbol"], 
                    alert["asset_type"]
                )
                if price_data:
                    alert["current_price"] = price_data.get("price", 0)
                    alert["change_24h"] = price_data.get("change_24h", 0)
        
        # Get subscription info
        subscription = await get_user_subscription(user_id)
        active_count = len([a for a in alerts if a.get("status") in ["active", "paused"]])
        
        # Calculate days remaining for trial
        days_remaining = None
        if subscription.get("status") == "trialing" and subscription.get("trial_ends_at"):
            trial_ends = subscription["trial_ends_at"]
            if isinstance(trial_ends, datetime):
                if trial_ends.tzinfo is None:
                    trial_ends = trial_ends.replace(tzinfo=timezone.utc)
            elif isinstance(trial_ends, str):
                trial_ends = datetime.fromisoformat(trial_ends.replace("Z", "+00:00"))
            days_remaining = max(0, (trial_ends - datetime.now(timezone.utc)).days)
        
        return {
            "alerts": alerts,
            "count": len(alerts),
            "active_count": active_count,
            "subscription": {
                "status": subscription.get("status", "none"),
                "tier": subscription.get("tier", "free"),
                "trial_ends_at": subscription.get("trial_ends_at"),
                "days_remaining": days_remaining,
                "can_create": subscription.get("status") in ["trialing", "active"]
            },
            "alerts_remaining": "unlimited"
        }
        
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{alert_id}")
async def get_alert(
    alert_id: str,
    user: dict = Depends(get_current_user)
):
    """Get a specific alert"""
    try:
        alert = await db.alerts.find_one(
            {"alert_id": alert_id, "user_id": user["id"]},
            {"_id": 0}
        )
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Get current price
        price_data = await alert_service.get_price(
            alert["asset_symbol"], 
            alert["asset_type"]
        )
        if price_data:
            alert["current_price"] = price_data.get("price", 0)
            alert["change_24h"] = price_data.get("change_24h", 0)
        
        return alert
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{alert_id}")
async def update_alert(
    alert_id: str,
    request: UpdateAlertRequest,
    user: dict = Depends(get_current_user)
):
    """Update an alert"""
    try:
        # Find existing alert
        alert = await db.alerts.find_one(
            {"alert_id": alert_id, "user_id": user["id"]}
        )
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        # Build update document
        update_doc = {"updated_at": datetime.now(timezone.utc).isoformat()}
        
        if request.target_value is not None:
            update_doc["target_value"] = request.target_value
        if request.notification_method is not None:
            update_doc["notification_method"] = request.notification_method.value
        if request.status is not None:
            update_doc["status"] = request.status.value
        if request.note is not None:
            update_doc["note"] = request.note
        
        await db.alerts.update_one(
            {"alert_id": alert_id, "user_id": user["id"]},
            {"$set": update_doc}
        )
        
        return {"success": True, "message": "Alert updated", "alert_id": alert_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete an alert"""
    try:
        result = await db.alerts.delete_one(
            {"alert_id": alert_id, "user_id": user["id"]}
        )
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        return {"success": True, "message": "Alert deleted", "alert_id": alert_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{alert_id}/toggle")
async def toggle_alert(
    alert_id: str,
    user: dict = Depends(get_current_user)
):
    """Toggle alert between active and paused"""
    try:
        alert = await db.alerts.find_one(
            {"alert_id": alert_id, "user_id": user["id"]}
        )
        
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        
        current_status = alert.get("status", "active")
        new_status = "paused" if current_status == "active" else "active"
        
        await db.alerts.update_one(
            {"alert_id": alert_id, "user_id": user["id"]},
            {"$set": {
                "status": new_status,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        return {
            "success": True, 
            "alert_id": alert_id,
            "previous_status": current_status,
            "new_status": new_status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_alert_stats(
    user: dict = Depends(get_current_user)
):
    """Get alert statistics for the user"""
    try:
        user_id = user["id"]
        
        # Get counts by status
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        
        status_counts = {}
        async for doc in db.alerts.aggregate(pipeline):
            status_counts[doc["_id"]] = doc["count"]
        
        # Get tier info
        tier = get_user_tier(user)
        tier_info = ALERT_TIERS.get(tier, ALERT_TIERS["free"])
        max_alerts = tier_info.max_alerts
        active_count = status_counts.get("active", 0) + status_counts.get("paused", 0)
        
        return {
            "tier": tier,
            "tier_name": tier_info.name,
            "max_alerts": max_alerts,
            "active_alerts": status_counts.get("active", 0),
            "paused_alerts": status_counts.get("paused", 0),
            "triggered_alerts": status_counts.get("triggered", 0),
            "total_alerts": sum(status_counts.values()),
            "alerts_remaining": max_alerts - active_count if max_alerts != -1 else "unlimited",
            "can_create": max_alerts == -1 or active_count < max_alerts
        }
        
    except Exception as e:
        logger.error(f"Error getting alert stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# ============== TELEGRAM INTEGRATION ==============

TELEGRAM_BOT_USERNAME = "cryptobagtrackerbot"

@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Handle incoming Telegram updates"""
    try:
        update = await request.json()
        from services.telegram_service import handle_telegram_update
        await handle_telegram_update(update)
        return {"ok": True}
    except Exception as e:
        logger.error(f"Telegram webhook error: {e}")
        return {"ok": False}


@router.get("/telegram/bot-info")
async def get_telegram_bot_info():
    """Get Telegram bot information"""
    bot_info = await get_bot_info()
    if "error" in bot_info:
        raise HTTPException(status_code=500, detail=bot_info["error"])
    
    return {
        "bot_username": bot_info.get("username"),
        "bot_name": bot_info.get("first_name"),
        "connect_url": f"https://t.me/{bot_info.get('username')}?start=connect"
    }


@router.post("/telegram/connect")
async def connect_telegram(
    chat_id: str,
    user: dict = Depends(get_current_user)
):
    """Save user's Telegram chat ID for notifications"""
    user_id = user["id"]
    
    # Verify chat_id by sending a test message
    success = await send_telegram_message(
        chat_id,
        "✅ <b>Connected!</b>\n\nYou'll now receive price alerts here.\n\n<i>Crypto Bag Tracker</i>"
    )
    
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not send message to this chat ID. Make sure you've started a chat with the bot first."
        )
    
    # Save chat_id to user profile
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"telegram_chat_id": chat_id, "telegram_connected_at": datetime.now(timezone.utc)}}
    )
    
    logger.info(f"User {user_id} connected Telegram chat {chat_id}")
    
    return {
        "success": True,
        "message": "Telegram connected! You'll receive alerts here."
    }


@router.delete("/telegram/disconnect")
async def disconnect_telegram(user: dict = Depends(get_current_user)):
    """Disconnect Telegram notifications"""
    user_id = user["id"]
    
    await db.users.update_one(
        {"id": user_id},
        {"$unset": {"telegram_chat_id": "", "telegram_connected_at": ""}}
    )
    
    return {"success": True, "message": "Telegram disconnected"}


@router.get("/telegram/status")
async def get_telegram_status(user: dict = Depends(get_current_user)):
    """Check if user has Telegram connected"""
    user_id = user["id"]
    
    user_doc = await db.users.find_one(
        {"id": user_id},
        {"_id": 0, "telegram_chat_id": 1, "telegram_connected_at": 1}
    )
    
    if user_doc and user_doc.get("telegram_chat_id"):
        return {
            "connected": True,
            "chat_id": user_doc["telegram_chat_id"],
            "connected_at": user_doc.get("telegram_connected_at")
        }
    
    return {"connected": False}


@router.post("/telegram/test")
async def test_telegram_alert(user: dict = Depends(get_current_user)):
    """Send a test alert to user's Telegram"""
    user_id = user["id"]
    
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "telegram_chat_id": 1})
    
    if not user_doc or not user_doc.get("telegram_chat_id"):
        raise HTTPException(status_code=400, detail="Telegram not connected")
    
    from services.telegram_service import send_alert_telegram
    
    success = await send_alert_telegram(
        chat_id=user_doc["telegram_chat_id"],
        asset_symbol="BTC",
        alert_type="price_above",
        target_value=100000,
        current_price=101500,
        note="This is a test alert"
    )
    
    if success:
        return {"success": True, "message": "Test alert sent!"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send test alert")



# ============== COIN REQUEST ENDPOINTS ==============

@router.post("/coin-request")
async def submit_coin_request(
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """Submit a request for a new cryptocurrency to be added"""
    try:
        data = await request.json()
        symbol = data.get("symbol", "").upper().strip()
        name = data.get("name", "").strip()
        reason = data.get("reason", "").strip()
        
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required")
        
        # Store the request in the database
        coin_request = {
            "user_id": current_user["user_id"],
            "user_email": current_user.get("email", ""),
            "symbol": symbol,
            "name": name,
            "reason": reason,
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
            "votes": 1
        }
        
        # Check if this coin was already requested
        existing = await db.coin_requests.find_one({"symbol": symbol})
        if existing:
            # Increment vote count
            await db.coin_requests.update_one(
                {"symbol": symbol},
                {
                    "$inc": {"votes": 1},
                    "$addToSet": {"voters": current_user["user_id"]}
                }
            )
            return {"success": True, "message": f"Vote added for {symbol}! Total votes: {existing.get('votes', 0) + 1}"}
        
        coin_request["voters"] = [current_user["user_id"]]
        await db.coin_requests.insert_one(coin_request)
        
        return {"success": True, "message": f"Request submitted for {symbol}. We'll review it soon!"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting coin request: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit request")


@router.get("/coin-requests")
async def get_coin_requests(current_user: dict = Depends(get_current_user)):
    """Get list of requested coins (top by votes)"""
    try:
        requests = await db.coin_requests.find(
            {"status": "pending"}
        ).sort("votes", -1).limit(20).to_list(length=20)
        
        return {
            "requests": [
                {
                    "symbol": r["symbol"],
                    "name": r.get("name", ""),
                    "votes": r.get("votes", 0),
                    "status": r.get("status", "pending")
                }
                for r in requests
            ]
        }
    except Exception as e:
        logger.error(f"Error fetching coin requests: {e}")
        return {"requests": []}


@router.get("/supported-coins")
async def get_supported_coins():
    """Get list of all supported cryptocurrencies (public endpoint)"""
    try:
        # Get the crypto ID map from alert service
        supported = []
        iso20022_coins = {"XRP", "XLM", "ALGO", "XDC", "IOTA", "HBAR", "QNT", "ADA", "XTZ"}
        
        crypto_map = {
            "XRP": ("Ripple", True), "XLM": ("Stellar", True), "ALGO": ("Algorand", True),
            "XDC": ("XDC Network", True), "IOTA": ("IOTA", True), "HBAR": ("Hedera", True),
            "QNT": ("Quant", True), "ADA": ("Cardano", True), "XTZ": ("Tezos", True),
            "BTC": ("Bitcoin", False), "ETH": ("Ethereum", False), "BNB": ("BNB", False),
            "SOL": ("Solana", False), "DOGE": ("Dogecoin", False), "TRX": ("Tron", False),
            "TON": ("Toncoin", False), "DOT": ("Polkadot", False), "MATIC": ("Polygon", False),
            "LINK": ("Chainlink", False), "AVAX": ("Avalanche", False), "SHIB": ("Shiba Inu", False),
            "LTC": ("Litecoin", False), "BCH": ("Bitcoin Cash", False), "UNI": ("Uniswap", False),
            "ATOM": ("Cosmos", False), "NEAR": ("NEAR Protocol", False), "APT": ("Aptos", False),
            "FIL": ("Filecoin", False), "ICP": ("Internet Computer", False), "VET": ("VeChain", False),
            "INJ": ("Injective", False), "OP": ("Optimism", False), "ARB": ("Arbitrum", False),
            "SUI": ("Sui", False), "SEI": ("Sei", False), "TIA": ("Celestia", False),
            "FTM": ("Fantom", False), "AAVE": ("Aave", False), "MKR": ("Maker", False),
            "GRT": ("The Graph", False), "THETA": ("Theta", False), "RENDER": ("Render", False),
            "SAND": ("The Sandbox", False), "MANA": ("Decentraland", False), "AXS": ("Axie Infinity", False),
            "PEPE": ("Pepe", False), "WIF": ("dogwifhat", False), "BONK": ("Bonk", False),
            "FLOKI": ("Floki", False), "ORDI": ("Ordinals", False),
        }
        
        for symbol, (name, is_iso) in crypto_map.items():
            supported.append({
                "symbol": symbol,
                "name": name,
                "is_iso20022": is_iso
            })
        
        # Sort: ISO 20022 first, then alphabetically
        supported.sort(key=lambda x: (not x["is_iso20022"], x["symbol"]))
        
        return {
            "total": len(supported),
            "iso20022_count": len(iso20022_coins),
            "coins": supported
        }
    except Exception as e:
        logger.error(f"Error fetching supported coins: {e}")
        return {"total": 0, "coins": []}
