"""
Notification Service - Sends alerts via Zapier webhook
"""
import os
import logging
import httpx
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ZAPIER_WEBHOOK_URL = os.environ.get("ZAPIER_WEBHOOK_URL", "")


class NotificationService:
    """Service for sending notifications via Zapier webhook"""
    
    def __init__(self):
        self.webhook_url = ZAPIER_WEBHOOK_URL
        self.configured = bool(self.webhook_url)
        
        if self.configured:
            logger.info("Zapier webhook configured")
        else:
            logger.warning("ZAPIER_WEBHOOK_URL not set - notifications disabled")
    
    async def send_alert(
        self,
        notification_method: str,
        email: Optional[str],
        phone: Optional[str],
        asset_symbol: str,
        alert_type: str,
        target_value: float,
        current_price: float,
        note: Optional[str] = None,
        user_name: Optional[str] = None
    ) -> dict:
        """
        Send alert notification via Zapier webhook
        
        Zapier will handle routing to email/SMS/Slack/etc based on your Zap configuration
        """
        results = {
            "webhook_sent": False,
            "errors": []
        }
        
        if not self.configured:
            results["errors"].append("Zapier webhook not configured")
            return results
        
        # Format alert type for display
        alert_type_display = {
            "price_above": "Price Above Target",
            "price_below": "Price Below Target", 
            "percent_change_up": "Price Up by Target %",
            "percent_change_down": "Price Down by Target %"
        }.get(alert_type, alert_type)
        
        # Format values
        if "percent" in alert_type:
            target_display = f"{target_value}%"
        else:
            target_display = f"${target_value:,.2f}"
        
        current_display = f"${current_price:,.2f}"
        
        # Build payload for Zapier
        payload = {
            # User info
            "user_email": email,
            "user_phone": phone,
            "user_name": user_name or "Crypto Bag Tracker User",
            "notification_method": notification_method,  # email, sms, or both
            
            # Alert details
            "asset_symbol": asset_symbol,
            "alert_type": alert_type,
            "alert_type_display": alert_type_display,
            "target_value": target_value,
            "target_display": target_display,
            "current_price": current_price,
            "current_display": current_display,
            "note": note or "",
            
            # Metadata
            "triggered_at": datetime.now(timezone.utc).isoformat(),
            "app_name": "Crypto Bag Tracker",
            "app_url": "https://proceeds-validator.preview.emergentagent.com",
            
            # Pre-formatted message for easy use in Zapier
            "email_subject": f"🔔 Price Alert: {asset_symbol} - {alert_type_display}",
            "message_short": f"🔔 {asset_symbol} Alert: {alert_type_display}! Target: {target_display}, Current: {current_display}",
            "message_full": f"Your price alert for {asset_symbol} has been triggered!\n\nAlert Type: {alert_type_display}\nTarget: {target_display}\nCurrent Price: {current_display}\n{f'Note: {note}' if note else ''}\n\n- Crypto Bag Tracker"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload
                )
                
                if response.status_code in [200, 201, 202]:
                    results["webhook_sent"] = True
                    logger.info(f"Alert notification sent via Zapier for {asset_symbol} to {email}")
                else:
                    results["errors"].append(f"Zapier returned status {response.status_code}")
                    logger.error(f"Zapier webhook failed: {response.status_code} - {response.text}")
                    
        except Exception as e:
            results["errors"].append(str(e))
            logger.error(f"Failed to send Zapier webhook: {e}")
        
        return results
    
    def get_status(self) -> dict:
        """Get the configuration status of notification service"""
        return {
            "zapier_configured": self.configured,
            "webhook_url_set": bool(self.webhook_url)
        }


# Singleton instance
notification_service = NotificationService()
