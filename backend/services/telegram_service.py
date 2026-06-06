"""
Telegram Bot Service - Send alerts via Telegram
"""
import os
import httpx
import logging

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


async def send_telegram_message(chat_id: str, message: str) -> bool:
    """Send a message to a Telegram user"""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not configured")
        return False
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{TELEGRAM_API}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
            )
            
            if response.status_code == 200:
                logger.info(f"Telegram message sent to {chat_id}")
                return True
            else:
                logger.error(f"Telegram API error: {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False


async def send_alert_telegram(
    chat_id: str,
    asset_symbol: str,
    alert_type: str,
    target_value: float,
    current_price: float,
    note: str = None
) -> bool:
    """Send a formatted price alert via Telegram"""
    
    # Format alert type
    alert_emoji = {
        "price_above": "📈",
        "price_below": "📉",
        "percent_change_up": "🚀",
        "percent_change_down": "💥"
    }.get(alert_type, "🔔")
    
    alert_type_display = {
        "price_above": "Price Above",
        "price_below": "Price Below",
        "percent_change_up": "Up by %",
        "percent_change_down": "Down by %"
    }.get(alert_type, alert_type)
    
    # Format values
    if "percent" in alert_type:
        target_display = f"{target_value}%"
    else:
        target_display = f"${target_value:,.2f}"
    
    current_display = f"${current_price:,.2f}"
    
    message = f"""
{alert_emoji} <b>Price Alert Triggered!</b>

<b>{asset_symbol}</b>
━━━━━━━━━━━━━━━
📊 Alert: {alert_type_display}
🎯 Target: {target_display}
💰 Current: {current_display}
{f"📝 Note: {note}" if note else ""}
━━━━━━━━━━━━━━━
<i>Crypto Bag Tracker</i>
"""
    
    return await send_telegram_message(chat_id, message.strip())


async def get_bot_info() -> dict:
    """Get bot information to verify token works"""
    if not TELEGRAM_BOT_TOKEN:
        return {"error": "Bot token not configured"}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{TELEGRAM_API}/getMe")
            if response.status_code == 200:
                return response.json().get("result", {})
            return {"error": response.text}
    except Exception as e:
        return {"error": str(e)}
