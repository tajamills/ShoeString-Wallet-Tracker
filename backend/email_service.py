# Email Service using Resend
# Handles transactional emails: welcome, password reset

import os
import asyncio
import logging
import resend
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize Resend
resend.api_key = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "noreply@cryptobagtracker.io")
APP_NAME = "Crypto Bag Tracker"
APP_URL = os.environ.get("APP_URL", "https://cryptobagtracker.io")


async def send_email(to_email: str, subject: str, html_content: str) -> dict:
    """Send an email using Resend (async, non-blocking)"""
    if not resend.api_key:
        logger.warning("RESEND_API_KEY not configured, skipping email")
        return {"status": "skipped", "message": "Email not configured"}
    
    params = {
        "from": f"{APP_NAME} <{SENDER_EMAIL}>",
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }
    
    try:
        # Run sync SDK in thread to keep FastAPI non-blocking
        email = await asyncio.to_thread(resend.Emails.send, params)
        logger.info(f"Email sent to {to_email}: {subject}")
        return {"status": "success", "email_id": email.get("id")}
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {str(e)}")
        return {"status": "error", "message": str(e)}


async def send_welcome_email(to_email: str) -> dict:
    """Send welcome email to new user"""
    subject = f"Welcome to {APP_NAME}!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #1a1a2e; color: #ffffff;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; text-align: center;">
            <h1 style="margin: 0; color: white;">Welcome to {APP_NAME}!</h1>
        </div>
        
        <div style="padding: 30px; background-color: #16213e; border-radius: 10px; margin-top: 20px;">
            <p style="color: #e0e0e0; font-size: 16px;">Hi there,</p>
            
            <p style="color: #e0e0e0; font-size: 16px;">
                Thanks for signing up! You're now ready to track your crypto portfolio and generate tax reports.
            </p>
            
            <h3 style="color: #667eea;">Getting Started:</h3>
            <ol style="color: #e0e0e0; font-size: 14px;">
                <li>Add your wallet address or upload a CSV</li>
                <li>View your transaction history and chain of custody</li>
                <li>See your gains and losses</li>
                <li>Export your Form 8949 for tax filing</li>
            </ol>
            
            <div style="text-align: center; margin-top: 30px;">
                <a href="{APP_URL}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Get Started
                </a>
            </div>
            
            <p style="color: #888; font-size: 12px; margin-top: 30px; text-align: center;">
                Questions? Reply to this email or contact support@cryptobagtracker.com
            </p>
        </div>
        
        <p style="color: #666; font-size: 11px; text-align: center; margin-top: 20px;">
            {APP_NAME} | 1557 Buford Dr #492773, Lawrenceville, GA 30043
        </p>
    </body>
    </html>
    """
    
    return await send_email(to_email, subject, html_content)


async def send_password_reset_email(to_email: str, reset_token: str) -> dict:
    """Send password reset email with token link"""
    subject = f"Reset Your {APP_NAME} Password"
    reset_url = f"{APP_URL}/reset-password?token={reset_token}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #1a1a2e; color: #ffffff;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; border-radius: 10px; text-align: center;">
            <h1 style="margin: 0; color: white;">Password Reset</h1>
        </div>
        
        <div style="padding: 30px; background-color: #16213e; border-radius: 10px; margin-top: 20px;">
            <p style="color: #e0e0e0; font-size: 16px;">Hi,</p>
            
            <p style="color: #e0e0e0; font-size: 16px;">
                We received a request to reset your password. Click the button below to create a new password:
            </p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_url}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Reset Password
                </a>
            </div>
            
            <p style="color: #888; font-size: 14px;">
                This link expires in 24 hours. If you didn't request this, you can safely ignore this email.
            </p>
            
            <p style="color: #666; font-size: 12px; margin-top: 20px;">
                Or copy this link: <br>
                <span style="color: #667eea; word-break: break-all;">{reset_url}</span>
            </p>
        </div>
        
        <p style="color: #666; font-size: 11px; text-align: center; margin-top: 20px;">
            {APP_NAME} | 1557 Buford Dr #492773, Lawrenceville, GA 30043
        </p>
    </body>
    </html>
    """
    
    return await send_email(to_email, subject, html_content)



async def send_subscription_expiring_email(to_email: str, days_remaining: int, tier: str) -> dict:
    """Send subscription expiration warning email"""
    subject = f"Your {APP_NAME} {tier.title()} subscription expires in {days_remaining} day{'s' if days_remaining != 1 else ''}"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #1a1a2e; color: #ffffff;">
        <div style="background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); padding: 30px; border-radius: 10px; text-align: center;">
            <h1 style="margin: 0; color: white;">Subscription Expiring Soon</h1>
        </div>
        
        <div style="padding: 30px; background-color: #16213e; border-radius: 10px; margin-top: 20px;">
            <p style="color: #e0e0e0; font-size: 16px;">Hi,</p>
            
            <p style="color: #e0e0e0; font-size: 16px;">
                Your <strong>{tier.title()}</strong> subscription to {APP_NAME} will expire in <strong>{days_remaining} day{'s' if days_remaining != 1 else ''}</strong>.
            </p>
            
            <p style="color: #e0e0e0; font-size: 16px;">
                To continue enjoying unlimited wallet analysis, tax reports, and chain of custody features, please renew your subscription.
            </p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{APP_URL}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Renew Now
                </a>
            </div>
            
            <p style="color: #888; font-size: 14px;">
                If you don't renew, your account will revert to the Free tier with limited features.
            </p>
        </div>
        
        <p style="color: #666; font-size: 11px; text-align: center; margin-top: 20px;">
            {APP_NAME} | 1557 Buford Dr #492773, Lawrenceville, GA 30043
        </p>
    </body>
    </html>
    """
    
    return await send_email(to_email, subject, html_content)


async def send_subscription_expired_email(to_email: str, tier: str) -> dict:
    """Send subscription expired notification email"""
    subject = f"Your {APP_NAME} {tier.title()} subscription has expired"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #1a1a2e; color: #ffffff;">
        <div style="background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); padding: 30px; border-radius: 10px; text-align: center;">
            <h1 style="margin: 0; color: white;">Subscription Expired</h1>
        </div>
        
        <div style="padding: 30px; background-color: #16213e; border-radius: 10px; margin-top: 20px;">
            <p style="color: #e0e0e0; font-size: 16px;">Hi,</p>
            
            <p style="color: #e0e0e0; font-size: 16px;">
                Your <strong>{tier.title()}</strong> subscription to {APP_NAME} has expired. Your account has been reverted to the Free tier.
            </p>
            
            <p style="color: #e0e0e0; font-size: 16px;">
                You can still use {APP_NAME} with limited features, or resubscribe to unlock:
            </p>
            
            <ul style="color: #e0e0e0; font-size: 14px;">
                <li>Unlimited wallet analysis</li>
                <li>Full tax report generation</li>
                <li>Chain of custody tracking</li>
                <li>CSV imports and exports</li>
            </ul>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{APP_URL}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Resubscribe Now
                </a>
            </div>
        </div>
        
        <p style="color: #666; font-size: 11px; text-align: center; margin-top: 20px;">
            {APP_NAME} | 1557 Buford Dr #492773, Lawrenceville, GA 30043
        </p>
    </body>
    </html>
    """
    
    return await send_email(to_email, subject, html_content)


async def send_subscription_upgraded_email(to_email: str, tier: str) -> dict:
    """Send subscription upgrade confirmation email"""
    subject = f"Welcome to {APP_NAME} {tier.title()}!"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #1a1a2e; color: #ffffff;">
        <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; border-radius: 10px; text-align: center;">
            <h1 style="margin: 0; color: white;">Subscription Activated!</h1>
        </div>
        
        <div style="padding: 30px; background-color: #16213e; border-radius: 10px; margin-top: 20px;">
            <p style="color: #e0e0e0; font-size: 16px;">Hi,</p>
            
            <p style="color: #e0e0e0; font-size: 16px;">
                Thank you for upgrading to <strong>{APP_NAME} {tier.title()}</strong>! Your subscription is now active.
            </p>
            
            <p style="color: #e0e0e0; font-size: 16px;">
                You now have access to:
            </p>
            
            <ul style="color: #e0e0e0; font-size: 14px;">
                <li>Unlimited wallet analysis across all supported chains</li>
                <li>Full Form 8949 tax report generation</li>
                <li>Chain of custody tracking and documentation</li>
                <li>CSV imports from exchanges</li>
                <li>Priority support</li>
            </ul>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{APP_URL}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Start Tracking
                </a>
            </div>
            
            <p style="color: #888; font-size: 14px;">
                Questions? Reply to this email or use the Help feature in the app.
            </p>
        </div>
        
        <p style="color: #666; font-size: 11px; text-align: center; margin-top: 20px;">
            {APP_NAME} | 1557 Buford Dr #492773, Lawrenceville, GA 30043
        </p>
    </body>
    </html>
    """
    
    return await send_email(to_email, subject, html_content)
