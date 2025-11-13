import os
import stripe
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class StripeService:
    def __init__(self):
        self.api_key = os.environ.get('STRIPE_API_KEY')
        self.webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        self.stripe_checkout = None
    
    def initialize_checkout(self, host_url: str):
        """Initialize Stripe checkout with webhook URL and secret"""
        webhook_url = f"{host_url}api/payments/webhook/stripe"
        self.stripe_checkout = StripeCheckout(
            api_key=self.api_key,
            webhook_secret=self.webhook_secret,
            webhook_url=webhook_url
        )
        return self.stripe_checkout
    
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
            # Set the API key for this request
            stripe.api_key = self.api_key
            
            # Build session parameters
            session_params = {
                'payment_method_types': ['card'],
                'line_items': [{
                    'price': price_id,
                    'quantity': 1,
                }],
                'mode': 'subscription',  # Changed from 'payment' to 'subscription'
                'success_url': success_url,
                'cancel_url': cancel_url,
                'metadata': metadata,
                'allow_promotion_codes': allow_promotion_codes,
                'billing_address_collection': 'auto',
            }
            
            # Use existing customer or create new one
            if customer_id:
                session_params['customer'] = customer_id
            else:
                session_params['customer_email'] = customer_email
            
            # Create checkout session
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(f"Created Stripe subscription session: {session.id}")
            
            # Return in expected format
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
            status = await self.stripe_checkout.get_checkout_status(session_id)
            return status
        except Exception as e:
            logger.error(f"Failed to get Stripe checkout status: {str(e)}")
            raise Exception(f"Failed to get checkout status: {str(e)}")
    
    async def handle_webhook(self, body: bytes, signature: str):
        """Handle Stripe webhook"""
        try:
            webhook_response = await self.stripe_checkout.handle_webhook(body, signature)
            return webhook_response
        except Exception as e:
            logger.error(f"Failed to handle Stripe webhook: {str(e)}")
            raise Exception(f"Webhook handling failed: {str(e)}")
