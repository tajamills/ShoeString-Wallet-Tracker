"""
Notification Service - Handles email and SMS notifications for alerts
"""
import os
import logging
from typing import Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# SendGrid setup
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "alerts@cryptobagtracker.com")

# Twilio setup  
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER", "")


class NotificationService:
    """Service for sending email and SMS notifications"""
    
    def __init__(self):
        self.sendgrid_configured = bool(SENDGRID_API_KEY)
        self.twilio_configured = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER)
        
        if self.sendgrid_configured:
            try:
                from sendgrid import SendGridAPIClient
                self.sg_client = SendGridAPIClient(SENDGRID_API_KEY)
                logger.info("SendGrid configured successfully")
            except ImportError:
                logger.warning("SendGrid library not installed. Run: pip install sendgrid")
                self.sendgrid_configured = False
        
        if self.twilio_configured:
            try:
                from twilio.rest import Client
                self.twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                logger.info("Twilio configured successfully")
            except ImportError:
                logger.warning("Twilio library not installed. Run: pip install twilio")
                self.twilio_configured = False
    
    def send_email_alert(
        self, 
        to_email: str, 
        asset_symbol: str, 
        alert_type: str,
        target_value: float,
        current_price: float,
        note: Optional[str] = None
    ) -> bool:
        """
        Send an email alert notification
        
        Returns True if sent successfully, False otherwise
        """
        if not self.sendgrid_configured:
            logger.warning(f"SendGrid not configured - skipping email to {to_email}")
            return False
        
        try:
            from sendgrid.helpers.mail import Mail
            
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
            
            subject = f"🔔 Price Alert: {asset_symbol} - {alert_type_display}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background: #1a1a2e; }}
                    .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background: linear-gradient(135deg, #7c3aed 0%, #a855f7 100%); padding: 30px; border-radius: 12px 12px 0 0; text-align: center; }}
                    .header h1 {{ color: white; margin: 0; font-size: 24px; }}
                    .content {{ background: #16213e; padding: 30px; border-radius: 0 0 12px 12px; color: #e2e8f0; }}
                    .alert-box {{ background: #1e3a5f; border-left: 4px solid #7c3aed; padding: 20px; margin: 20px 0; border-radius: 4px; }}
                    .price-row {{ display: flex; justify-content: space-between; margin: 10px 0; }}
                    .label {{ color: #94a3b8; }}
                    .value {{ color: white; font-weight: bold; }}
                    .cta {{ background: #7c3aed; color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; margin-top: 20px; }}
                    .footer {{ text-align: center; padding: 20px; color: #64748b; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>🔔 Price Alert Triggered</h1>
                    </div>
                    <div class="content">
                        <div class="alert-box">
                            <h2 style="margin-top: 0; color: #a855f7;">{asset_symbol}</h2>
                            <div class="price-row">
                                <span class="label">Alert Type:</span>
                                <span class="value">{alert_type_display}</span>
                            </div>
                            <div class="price-row">
                                <span class="label">Target:</span>
                                <span class="value">{target_display}</span>
                            </div>
                            <div class="price-row">
                                <span class="label">Current Price:</span>
                                <span class="value" style="color: #22c55e;">{current_display}</span>
                            </div>
                            {f'<div class="price-row"><span class="label">Note:</span><span class="value">{note}</span></div>' if note else ''}
                        </div>
                        <p>Your price alert for <strong>{asset_symbol}</strong> has been triggered!</p>
                        <center>
                            <a href="https://proceeds-validator.preview.emergentagent.com" class="cta">View Dashboard</a>
                        </center>
                    </div>
                    <div class="footer">
                        <p>Crypto Bag Tracker - Never Miss a Move</p>
                        <p>You received this because you set up a price alert.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            message = Mail(
                from_email=SENDER_EMAIL,
                to_emails=to_email,
                subject=subject,
                html_content=html_content
            )
            
            response = self.sg_client.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email alert sent to {to_email} for {asset_symbol}")
                return True
            else:
                logger.error(f"SendGrid returned status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
            return False
    
    def send_sms_alert(
        self,
        to_phone: str,
        asset_symbol: str,
        alert_type: str,
        target_value: float,
        current_price: float
    ) -> bool:
        """
        Send an SMS alert notification
        
        to_phone should be in E.164 format (e.g., +14155552671)
        Returns True if sent successfully, False otherwise
        """
        if not self.twilio_configured:
            logger.warning(f"Twilio not configured - skipping SMS to {to_phone}")
            return False
        
        try:
            # Format alert type
            alert_type_short = {
                "price_above": "above",
                "price_below": "below",
                "percent_change_up": "up",
                "percent_change_down": "down"
            }.get(alert_type, alert_type)
            
            # Format values
            if "percent" in alert_type:
                target_display = f"{target_value}%"
            else:
                target_display = f"${target_value:,.0f}"
            
            current_display = f"${current_price:,.2f}"
            
            message_body = f"🔔 {asset_symbol} Alert: Price {alert_type_short} {target_display}! Current: {current_display} - CryptoBagTracker"
            
            message = self.twilio_client.messages.create(
                body=message_body,
                from_=TWILIO_PHONE_NUMBER,
                to=to_phone
            )
            
            logger.info(f"SMS alert sent to {to_phone} for {asset_symbol}, SID: {message.sid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS alert: {e}")
            return False
    
    def send_alert(
        self,
        notification_method: str,
        email: Optional[str],
        phone: Optional[str],
        asset_symbol: str,
        alert_type: str,
        target_value: float,
        current_price: float,
        note: Optional[str] = None
    ) -> dict:
        """
        Send alert via specified notification method(s)
        
        notification_method: 'email', 'sms', or 'both'
        Returns dict with results for each channel
        """
        results = {
            "email_sent": False,
            "sms_sent": False,
            "errors": []
        }
        
        if notification_method in ["email", "both"] and email:
            try:
                results["email_sent"] = self.send_email_alert(
                    to_email=email,
                    asset_symbol=asset_symbol,
                    alert_type=alert_type,
                    target_value=target_value,
                    current_price=current_price,
                    note=note
                )
            except Exception as e:
                results["errors"].append(f"Email error: {str(e)}")
        
        if notification_method in ["sms", "both"] and phone:
            try:
                results["sms_sent"] = self.send_sms_alert(
                    to_phone=phone,
                    asset_symbol=asset_symbol,
                    alert_type=alert_type,
                    target_value=target_value,
                    current_price=current_price
                )
            except Exception as e:
                results["errors"].append(f"SMS error: {str(e)}")
        
        return results
    
    def get_status(self) -> dict:
        """Get the configuration status of notification channels"""
        return {
            "email_configured": self.sendgrid_configured,
            "sms_configured": self.twilio_configured,
            "sender_email": SENDER_EMAIL if self.sendgrid_configured else None
        }


# Singleton instance
notification_service = NotificationService()
