"""Payment routes - Stripe checkout, webhooks, status"""
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone
import logging
import os

from .dependencies import db, get_current_user, get_current_quarter
from .models import (
    Payment, CheckoutRequest, Affiliate, AffiliateReferral
)
from stripe_service import StripeService
from email_service import (
    send_subscription_upgraded_email, send_subscription_expired_email,
    send_subscription_expiring_email, send_welcome_email, send_password_reset_email
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["Payments"])

stripe_service = StripeService()


@router.post("/create-upgrade")
async def create_upgrade_payment(
    checkout_request: CheckoutRequest,
    http_request: Request,
    user: dict = Depends(get_current_user)
):
    """Create Stripe subscription checkout session for upgrade"""
    try:
        price_id = os.environ.get('STRIPE_PRICE_ID_UNLIMITED')
        
        if not price_id:
            price_id = os.environ.get('STRIPE_PRICE_ID_PRO') or os.environ.get('STRIPE_PRICE_ID_PREMIUM')
        
        if not price_id:
            raise HTTPException(status_code=500, detail="Price ID not configured")
        
        current_tier = user.get('subscription_tier', 'free')
        subscription_status = user.get('subscription_status')
        
        if current_tier in ['unlimited', 'premium', 'pro'] and subscription_status == 'active':
            raise HTTPException(
                status_code=400, 
                detail="You already have an active subscription"
            )
        
        affiliate = None
        coupon_id = None
        if checkout_request.affiliate_code:
            affiliate = await db.affiliates.find_one({
                "affiliate_code": checkout_request.affiliate_code.upper(),
                "is_active": True
            })
            if affiliate:
                if affiliate['user_id'] == user['id']:
                    raise HTTPException(status_code=400, detail="You cannot use your own affiliate code")
                
                try:
                    import stripe as stripe_lib
                    stripe_lib.api_key = os.environ.get('STRIPE_API_KEY')
                    
                    coupon_id = "AFFILIATE10"
                    try:
                        stripe_lib.Coupon.retrieve(coupon_id)
                    except:
                        stripe_lib.Coupon.create(
                            id=coupon_id,
                            amount_off=1000,
                            currency="usd",
                            duration="once",
                            name="Affiliate Discount - $10 Off"
                        )
                except Exception as e:
                    logger.warning(f"Could not create/get coupon: {str(e)}")
        
        host_url = str(http_request.base_url)
        stripe_service.initialize_checkout(host_url)
        
        success_url = f"{checkout_request.origin_url}?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{checkout_request.origin_url}"
        
        metadata = {
            "user_id": user["id"],
            "tier": "unlimited",
            "email": user["email"]
        }
        
        if affiliate:
            metadata["affiliate_code"] = checkout_request.affiliate_code.upper()
            metadata["affiliate_id"] = affiliate["id"]
        
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
        
        if coupon_id and affiliate:
            session_params['discounts'] = [{'coupon': coupon_id}]
        
        session = stripe_lib.checkout.Session.create(**session_params)
        
        payment = Payment(
            user_id=user["id"],
            session_id=session.id,
            amount=100.88 if not affiliate else 90.88,
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


@router.post("/webhook/stripe")
async def handle_stripe_webhook(request: Request):
    """Handle Stripe webhook for subscriptions"""
    try:
        body = await request.body()
        signature = request.headers.get("stripe-signature", "")
        
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
        
        if event_type == 'checkout.session.completed':
            session = event['data']['object']
            session_id = session['id']
            customer_id = session.get('customer')
            subscription_id = session.get('subscription')
            metadata = session.get('metadata', {})
            
            user_id = metadata.get('user_id')
            tier = metadata.get('tier')
            
            if user_id and tier and subscription_id:
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
                
                affiliate_code = metadata.get('affiliate_code')
                affiliate_id = metadata.get('affiliate_id')
                
                if affiliate_code and affiliate_id:
                    customer_email = metadata.get('email', '')
                    
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
                
                try:
                    user = await db.users.find_one({"id": user_id})
                    if user and user.get('email'):
                        await send_subscription_upgraded_email(user['email'], tier)
                        logger.info(f"Sent subscription upgrade email to {user['email']}")
                except Exception as email_err:
                    logger.error(f"Failed to send upgrade email: {str(email_err)}")
        
        elif event_type == 'customer.subscription.updated':
            subscription = event['data']['object']
            subscription_id = subscription['id']
            status = subscription['status']
            
            user = await db.users.find_one({"stripe_subscription_id": subscription_id})
            
            if user:
                update_data = {"subscription_status": status}
                
                if status in ['canceled', 'unpaid']:
                    update_data["subscription_tier"] = "free"
                    logger.info(f"User {user['id']} subscription {status}, downgraded to free")
                
                await db.users.update_one(
                    {"id": user["id"]},
                    {"$set": update_data}
                )
        
        elif event_type == 'customer.subscription.deleted':
            subscription = event['data']['object']
            subscription_id = subscription['id']
            
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
                
                try:
                    if user.get('email'):
                        old_tier = user.get('subscription_tier', 'premium')
                        await send_subscription_expired_email(user['email'], old_tier)
                        logger.info(f"Sent subscription expired email to {user['email']}")
                except Exception as email_err:
                    logger.error(f"Failed to send expired email: {str(email_err)}")
        
        elif event_type == 'invoice.upcoming':
            invoice = event['data']['object']
            subscription_id = invoice.get('subscription')
            
            if subscription_id:
                user = await db.users.find_one({"stripe_subscription_id": subscription_id})
                if user:
                    next_payment_date = invoice.get('next_payment_attempt')
                    if next_payment_date:
                        days_remaining = max(1, (datetime.fromtimestamp(next_payment_date, tz=timezone.utc) - datetime.now(timezone.utc)).days)
                    else:
                        days_remaining = 3
                    
                    try:
                        tier = user.get("subscription_tier", "premium")
                        await send_subscription_expiring_email(user['email'], days_remaining, tier)
                        logger.info(f"Sent upcoming renewal email to {user['email']} - {days_remaining} days")
                    except Exception as email_err:
                        logger.error(f"Failed to send upcoming email: {str(email_err)}")
        
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
        
    except Exception as e:
        logger.error(f"Stripe webhook processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.get("/status/{session_id}")
async def get_payment_status(
    session_id: str,
    user: dict = Depends(get_current_user)
):
    """Check Stripe checkout session status"""
    try:
        payment_doc = await db.payment_transactions.find_one(
            {"session_id": session_id, "user_id": user["id"]},
            {"_id": 0}
        )
        
        if not payment_doc:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        try:
            checkout_status = await stripe_service.get_checkout_status(session_id)
            
            if checkout_status.payment_status == "paid" and payment_doc["payment_status"] != "paid":
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
                "amount": checkout_status.amount_total / 100,
                "currency": checkout_status.currency,
                "subscription_tier": payment_doc["subscription_tier"]
            }
        except Exception as e:
            logger.error(f"Error checking Stripe status: {str(e)}")
            return payment_doc
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get payment status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get payment status")


@router.post("/test-email")
async def send_test_email(
    request: Request,
    email_type: str = "renewal",
    to_email: str = None,
    user: dict = Depends(get_current_user)
):
    """Send a test email for verification (admin endpoint)"""
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
