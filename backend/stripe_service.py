import os
import stripe
from typing import Dict, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class CheckoutSessionResponse:
    url: str
    session_id: str

@dataclass
class CheckoutStatusResponse:
    status: str
    payment_status: str
    customer_email: Optional[str] = None

class StripeService:
    def __init__(self):
        self.api_key = os.environ.get('STRIPE_API_KEY')
        self.webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        if self.api_key:
            stripe.api_key = self.api_key
    
    def initialize_checkout(self, host_url: str):
        """Initialize Stripe checkout with webhook URL"""
        webhook_url = f"{host_url}api/payments/webhook/stripe"
        logger.info(f"Stripe webhook URL: {webhook_url}")
        return self
    
    async def create_checkout_session(
        self,
        price_id: str,
        customer_email: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict[str, str],
        customer_id: str = None,
        allow_promotion_codes: bool = True
    ) -> CheckoutSessionResponse:
        """Create a Stripe subscription checkout session"""
        try:
            stripe.api_key = self.api_key
            
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
                'allow_promotion_codes': allow_promotion_codes,
                'billing_address_collection': 'auto',
            }
            
            if customer_id:
                session_params['customer'] = customer_id
            else:
                session_params['customer_email'] = customer_email
            
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(f"Created Stripe subscription session: {session.id}")
            
            return CheckoutSessionResponse(
                url=session.url,
                session_id=session.id
            )
            
        except Exception as e:
            logger.error(f"Failed to create Stripe checkout session: {str(e)}")
            raise Exception(f"Stripe checkout session creation failed: {str(e)}")
    
    async def get_checkout_status(self, session_id: str) -> CheckoutStatusResponse:
        """Get the status of a Stripe checkout session"""
        try:
            stripe.api_key = self.api_key
            session = stripe.checkout.Session.retrieve(session_id)
            
            return CheckoutStatusResponse(
                status=session.status,
                payment_status=session.payment_status,
                customer_email=session.customer_details.email if session.customer_details else None
            )
        except Exception as e:
            logger.error(f"Failed to get Stripe checkout status: {str(e)}")
            raise Exception(f"Failed to get checkout status: {str(e)}")
    
    async def handle_webhook(self, body: bytes, signature: str):
        """Handle Stripe webhook"""
        try:
            event = stripe.Webhook.construct_event(
                body, signature, self.webhook_secret
            )
            return event
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Webhook signature verification failed: {str(e)}")
            raise Exception(f"Webhook signature verification failed: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to handle Stripe webhook: {str(e)}")
            raise Exception(f"Webhook handling failed: {str(e)}")
