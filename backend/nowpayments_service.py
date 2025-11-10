import os
import httpx
import hmac
import hashlib
import json
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class NOWPaymentsService:
    def __init__(self):
        self.api_key = os.environ.get('NOWPAYMENTS_API_KEY')
        self.ipn_secret = os.environ.get('NOWPAYMENTS_IPN_SECRET', '')
        self.base_url = "https://api.nowpayments.io/v1"
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
    
    async def get_available_currencies(self) -> list:
        """Get list of available cryptocurrencies"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/currencies",
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                return data.get('currencies', [])
        except Exception as e:
            logger.error(f"Failed to get currencies: {str(e)}")
            return []
    
    async def get_minimum_payment_amount(self, currency: str = "btc") -> float:
        """Get minimum payment amount for BTC"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/min-amount",
                    params={"currency_from": "usd", "currency_to": currency},
                    headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                return float(data.get('min_amount', 0))
        except Exception as e:
            logger.error(f"Failed to get min amount: {str(e)}")
            return 0.0
    
    async def create_payment(
        self,
        price_amount: float,
        price_currency: str,
        pay_currency: str,
        order_id: str,
        order_description: str,
        ipn_callback_url: str,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a payment in NOWPayments.
        For BTC payments with USD pricing.
        """
        try:
            payload = {
                "price_amount": price_amount,
                "price_currency": price_currency,
                "pay_currency": pay_currency,
                "order_id": order_id,
                "order_description": order_description,
                "ipn_callback_url": ipn_callback_url,
                "success_url": success_url,
                "cancel_url": cancel_url
            }
            
            # Remove None values
            payload = {k: v for k, v in payload.items() if v is not None}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/payment",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"Created payment {data.get('payment_id')} for order {order_id}")
                
                return {
                    "payment_id": data.get("payment_id"),
                    "payment_status": data.get("payment_status"),
                    "pay_address": data.get("pay_address"),
                    "pay_amount": data.get("pay_amount"),
                    "pay_currency": data.get("pay_currency"),
                    "price_amount": data.get("price_amount"),
                    "price_currency": data.get("price_currency"),
                    "order_id": data.get("order_id"),
                    "payment_url": data.get("invoice_url"),
                    "created_at": data.get("created_at")
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error creating payment: {e.response.text}")
            raise Exception(f"Payment creation failed: {e.response.text}")
        except Exception as e:
            logger.error(f"Failed to create payment: {str(e)}")
            raise Exception(f"Payment creation failed: {str(e)}")
    
    async def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Check payment status"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/payment/{payment_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Failed to get payment status: {str(e)}")
            raise Exception(f"Failed to get payment status: {str(e)}")
    
    def verify_ipn_signature(self, request_body: str, signature: str) -> bool:
        """
        Verify IPN (Instant Payment Notification) signature.
        NOWPayments uses HMAC-SHA512 for signature verification.
        """
        try:
            if not self.ipn_secret:
                logger.warning("IPN secret not configured, skipping verification")
                return True  # Skip verification if no secret configured
            
            # Sort JSON keys alphabetically
            sorted_json = json.dumps(json.loads(request_body), sort_keys=True, separators=(',', ':'))
            
            expected_sig = hmac.new(
                self.ipn_secret.encode('utf-8'),
                sorted_json.encode('utf-8'),
                hashlib.sha512
            ).hexdigest()
            
            return hmac.compare_digest(expected_sig, signature)
            
        except Exception as e:
            logger.error(f"IPN signature verification failed: {str(e)}")
            return False
    
    async def create_recurring_payment(
        self,
        price_amount: float,
        price_currency: str,
        pay_currency: str,
        customer_email: str,
        order_description: str,
        period: str = "monthly"  # monthly, weekly, daily
    ) -> Dict[str, Any]:
        """
        Create a recurring payment subscription.
        Note: Requires NOWPayments Recurring Payments API access.
        """
        try:
            payload = {
                "price_amount": price_amount,
                "price_currency": price_currency,
                "pay_currency": pay_currency,
                "customer_email": customer_email,
                "order_description": order_description,
                "period": period,
                "is_recurring": True
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/recurring-payment",
                    json=payload,
                    headers=self.headers,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                logger.info(f"Created recurring payment {data.get('id')}")
                return data
                
        except Exception as e:
            logger.error(f"Failed to create recurring payment: {str(e)}")
            raise Exception(f"Recurring payment creation failed: {str(e)}")
