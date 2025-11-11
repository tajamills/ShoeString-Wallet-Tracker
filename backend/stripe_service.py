import os
from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionResponse, CheckoutStatusResponse, CheckoutSessionRequest
from typing import Dict
import logging

logger = logging.getLogger(__name__)

class StripeService:
    def __init__(self):
        self.api_key = os.environ.get('STRIPE_API_KEY')
        self.stripe_checkout = None
    
    def initialize_checkout(self, host_url: str):
        """Initialize Stripe checkout with webhook URL"""
        webhook_url = f"{host_url}api/payments/webhook/stripe"
        self.stripe_checkout = StripeCheckout(api_key=self.api_key, webhook_url=webhook_url)
        return self.stripe_checkout
    
    async def create_checkout_session(
        self,
        amount: float,
        currency: str,
        success_url: str,
        cancel_url: str,
        metadata: Dict[str, str]
    ) -> CheckoutSessionResponse:
        """Create a Stripe checkout session"""
        try:
            checkout_request = CheckoutSessionRequest(
                amount=amount,
                currency=currency,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata
            )
            
            session = await self.stripe_checkout.create_checkout_session(checkout_request)
            logger.info(f"Created Stripe checkout session: {session.session_id}")
            return session
            
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
