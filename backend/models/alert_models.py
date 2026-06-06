"""Alert models for crypto/stock price alerts"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class AlertType(str, Enum):
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    PERCENT_CHANGE_UP = "percent_change_up"
    PERCENT_CHANGE_DOWN = "percent_change_down"


class AssetType(str, Enum):
    CRYPTO = "crypto"
    # STOCK = "stock"  # Coming soon - needs API key


class SubscriptionStatus(str, Enum):
    TRIALING = "trialing"
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    EXPIRED = "expired"


class NotificationMethod(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    BOTH = "both"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    TRIGGERED = "triggered"
    PAUSED = "paused"
    EXPIRED = "expired"


class CreateAlertRequest(BaseModel):
    """Request model for creating a new alert"""
    asset_symbol: str = Field(..., description="Asset symbol (e.g., BTC, AAPL)")
    asset_type: AssetType = Field(..., description="Type of asset (crypto or stock)")
    alert_type: AlertType = Field(..., description="Type of alert trigger")
    target_value: float = Field(..., description="Target price or percentage")
    notification_method: NotificationMethod = Field(default=NotificationMethod.EMAIL)
    phone_number: Optional[str] = Field(None, description="Phone number for SMS notifications (E.164 format)")
    note: Optional[str] = Field(None, description="Optional note for the alert")


class AlertResponse(BaseModel):
    """Response model for an alert"""
    id: str
    user_id: str
    asset_symbol: str
    asset_type: AssetType
    alert_type: AlertType
    target_value: float
    current_price: Optional[float] = None
    notification_method: NotificationMethod
    status: AlertStatus
    note: Optional[str] = None
    created_at: str
    triggered_at: Optional[str] = None
    last_checked: Optional[str] = None


class UpdateAlertRequest(BaseModel):
    """Request model for updating an alert"""
    target_value: Optional[float] = None
    notification_method: Optional[NotificationMethod] = None
    status: Optional[AlertStatus] = None
    note: Optional[str] = None


class AlertTier(BaseModel):
    """Subscription tier for alerts"""
    name: str
    max_alerts: int  # -1 for unlimited
    price_monthly: float
    price_yearly: float
    features: List[str]


# Alert subscription tiers - Single tier with 7-day free trial
ALERT_TIERS = {
    "free": AlertTier(
        name="Free Trial",
        max_alerts=-1,  # Unlimited during trial
        price_monthly=0,
        price_yearly=0,
        features=["7-day free trial", "Unlimited alerts during trial", "Email + SMS notifications", "Crypto alerts", "Price & % change alerts"]
    ),
    "unlimited": AlertTier(
        name="Unlimited",
        max_alerts=-1,  # Unlimited
        price_monthly=18.88,
        price_yearly=199.00,
        features=["Unlimited alerts", "Email + SMS notifications", "Crypto alerts", "Price & % change alerts", "Priority support"]
    )
}

# Stripe product/price IDs
STRIPE_ALERT_PRODUCT_ID = "prod_UecNCOQUgkIyrk"
STRIPE_ALERT_PRICE_ID = "price_1TfJ8WAXuTzNcQX7GPkmVilU"
