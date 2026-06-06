"""
Alert Monitor Service - Background task to check prices and trigger alerts
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict
import os

logger = logging.getLogger(__name__)

# Check interval in seconds
CHECK_INTERVAL = int(os.environ.get("ALERT_CHECK_INTERVAL", "60"))


class AlertMonitor:
    """Background service to monitor prices and trigger alerts"""
    
    def __init__(self, db, alert_service):
        self.db = db
        self.alert_service = alert_service
        self.running = False
        self._task = None
    
    async def start(self):
        """Start the alert monitoring background task"""
        if self.running:
            return
        
        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Alert monitor started")
    
    async def stop(self):
        """Stop the alert monitoring"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Alert monitor stopped")
    
    async def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                await self._check_alerts()
            except Exception as e:
                logger.error(f"Error in alert monitor loop: {e}")
            
            await asyncio.sleep(CHECK_INTERVAL)
    
    async def _check_alerts(self):
        """Check all active alerts against current prices"""
        # Get all active alerts
        alerts = await self.db.alerts.find(
            {"status": "active"},
            {"_id": 0}
        ).to_list(1000)
        
        if not alerts:
            return
        
        # Group alerts by symbol to minimize API calls
        symbols = {}
        for alert in alerts:
            key = (alert["asset_symbol"], alert["asset_type"])
            if key not in symbols:
                symbols[key] = []
            symbols[key].append(alert)
        
        # Check each symbol
        for (symbol, asset_type), symbol_alerts in symbols.items():
            try:
                price_data = await self.alert_service.get_price(symbol, asset_type)
                if not price_data:
                    continue
                
                current_price = price_data.get("price", 0)
                change_24h = price_data.get("change_24h", 0)
                
                for alert in symbol_alerts:
                    await self._evaluate_alert(alert, current_price, change_24h)
                    
            except Exception as e:
                logger.error(f"Error checking price for {symbol}: {e}")
    
    async def _evaluate_alert(self, alert: Dict, current_price: float, change_24h: float):
        """Evaluate if an alert should be triggered"""
        alert_type = alert["alert_type"]
        target = alert["target_value"]
        triggered = False
        
        if alert_type == "price_above" and current_price >= target:
            triggered = True
        elif alert_type == "price_below" and current_price <= target:
            triggered = True
        elif alert_type == "percent_change_up" and change_24h >= target:
            triggered = True
        elif alert_type == "percent_change_down" and change_24h <= -target:
            triggered = True
        
        # Update last checked
        await self.db.alerts.update_one(
            {"alert_id": alert["alert_id"]},
            {"$set": {
                "current_price": current_price,
                "last_checked": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        if triggered:
            # Check cooldown - don't spam, only notify once per hour
            last_triggered = alert.get("last_triggered_at")
            if last_triggered:
                if isinstance(last_triggered, str):
                    last_triggered = datetime.fromisoformat(last_triggered.replace("Z", "+00:00"))
                if isinstance(last_triggered, datetime):
                    if last_triggered.tzinfo is None:
                        last_triggered = last_triggered.replace(tzinfo=timezone.utc)
                    time_since = (datetime.now(timezone.utc) - last_triggered).total_seconds()
                    if time_since < 3600:  # 1 hour cooldown
                        return
            
            await self._trigger_alert(alert, current_price)
    
    async def _trigger_alert(self, alert: Dict, current_price: float):
        """Trigger an alert - send notifications"""
        alert_id = alert["alert_id"]
        user_id = alert["user_id"]
        
        logger.info(f"Triggering alert {alert_id} for {alert['asset_symbol']}")
        
        # Get user info for notifications
        user = await self.db.users.find_one(
            {"id": user_id},
            {"_id": 0, "email": 1, "telegram_chat_id": 1}
        )
        
        if not user:
            logger.warning(f"User {user_id} not found for alert {alert_id}")
            return
        
        # Send Telegram notification if connected
        telegram_chat_id = user.get("telegram_chat_id")
        if telegram_chat_id:
            from services.telegram_service import send_alert_telegram
            await send_alert_telegram(
                chat_id=telegram_chat_id,
                asset_symbol=alert["asset_symbol"],
                alert_type=alert["alert_type"],
                target_value=alert["target_value"],
                current_price=current_price,
                note=alert.get("note")
            )
        
        # Send Zapier webhook for email/SMS
        notification_method = alert.get("notification_method", "email")
        if notification_method in ["email", "sms", "both"]:
            from services.notification_service import notification_service
            await notification_service.send_alert(
                notification_method=notification_method,
                email=user.get("email") or alert.get("user_email"),
                phone=alert.get("phone_number"),
                asset_symbol=alert["asset_symbol"],
                alert_type=alert["alert_type"],
                target_value=alert["target_value"],
                current_price=current_price,
                note=alert.get("note")
            )
        
        # Update alert - keep active, add cooldown to prevent spam
        # Only send notification once per hour for same condition
        await self.db.alerts.update_one(
            {"alert_id": alert_id},
            {"$set": {
                "last_triggered_at": datetime.now(timezone.utc).isoformat(),
                "last_triggered_price": current_price
            },
            "$inc": {"trigger_count": 1}}
        )


# Global instance - initialized in server.py
alert_monitor = None
