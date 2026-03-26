"""Shared Pydantic models for route modules"""
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid


# Status Check Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


# Wallet Models
class WalletAnalysisRequest(BaseModel):
    address: str
    chain: str = "ethereum"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class SavedWallet(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    address: str
    nickname: str
    chain: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SavedWalletCreate(BaseModel):
    address: str
    nickname: str
    chain: str = "ethereum"


class WalletAnalysisResponse(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str
    chain: Optional[str] = None
    totalEthSent: float
    totalEthReceived: float
    totalGasFees: float
    currentBalance: float
    netEth: float
    netFlow: float
    outgoingTransactionCount: int
    incomingTransactionCount: int
    tokensSent: Dict[str, float]
    tokensReceived: Dict[str, float]
    recentTransactions: List[Dict[str, Any]]
    total_transaction_count: Optional[int] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    current_price_usd: Optional[float] = None
    total_value_usd: Optional[float] = None
    total_received_usd: Optional[float] = None
    total_sent_usd: Optional[float] = None
    total_gas_fees_usd: Optional[float] = None
    tax_data: Optional[Dict[str, Any]] = None
    exchange_deposit_warning: Optional[Dict[str, Any]] = None


# User Models
class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    subscription_tier: str = "free"
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    subscription_status: Optional[str] = None
    daily_usage_count: int = 0
    analysis_count: int = 0
    last_usage_reset: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    terms_accepted: bool = False
    terms_accepted_at: Optional[datetime] = None


class UserRegister(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class UserResponse(BaseModel):
    id: str
    email: str
    subscription_tier: str
    daily_usage_count: int
    analysis_count: int = 0
    created_at: datetime
    terms_accepted: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Payment Models
class Payment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    amount: float
    currency: str
    status: str
    payment_status: str
    subscription_tier: str
    affiliate_code: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confirmed_at: Optional[datetime] = None


class CheckoutRequest(BaseModel):
    tier: str
    origin_url: str
    affiliate_code: Optional[str] = None


class UpgradeRequest(BaseModel):
    tier: str


# Affiliate Models
class Affiliate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    affiliate_code: str
    email: str
    name: str
    paypal_email: Optional[str] = None
    total_earnings: float = 0.0
    pending_earnings: float = 0.0
    referral_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True


class AffiliateReferral(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    affiliate_id: str
    affiliate_code: str
    customer_user_id: str
    customer_email: str
    amount_earned: float = 10.0
    customer_discount: float = 10.0
    payment_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    paid_out: bool = False
    paid_out_date: Optional[datetime] = None
    quarter: str


class AffiliateRegisterRequest(BaseModel):
    affiliate_code: str
    name: str
    paypal_email: Optional[str] = None


# Tax Models
class Form8949Request(BaseModel):
    address: str = ""
    chain: str = "ethereum"
    filter_type: str = "all"
    data_source: str = "combined"
    tax_year: int = None


class BatchCategoryRequest(BaseModel):
    address: str
    chain: str = "ethereum"
    categories: Dict[str, str]


class AutoCategorizeRequest(BaseModel):
    address: str
    chain: str = "ethereum"
    known_addresses: Optional[Dict[str, str]] = None


class UnifiedTaxRequest(BaseModel):
    address: Optional[str] = None
    chain: str = "ethereum"
    data_source: str = "combined"
    asset_filter: Optional[str] = None
    tax_year: Optional[int] = None
    as_of_date: Optional[str] = None  # YYYY-MM-DD format for historical valuation


class ExchangeTaxRequest(BaseModel):
    asset_filter: Optional[str] = None
    tax_year: Optional[int] = None
    as_of_date: Optional[str] = None  # YYYY-MM-DD format for historical valuation


# Chain Request Models
class ChainRequest(BaseModel):
    chain_name: str
    chain_symbol: Optional[str] = None
    reason: Optional[str] = None
    sample_address: Optional[str] = None


# Custody Models
class CustodyAnalysisRequest(BaseModel):
    address: str
    chain: str = "ethereum"
    max_depth: int = 10
    dormancy_days: int = 365


# Exchange Models
class ExchangeConnectionRequest(BaseModel):
    exchange: str
    api_key: str
    api_secret: str
    passphrase: Optional[str] = None


class CostBasisUpdate(BaseModel):
    tx_id: str
    original_purchase_date: Optional[str] = None
    original_cost_basis: Optional[float] = None
    is_transfer: bool = False
    notes: Optional[str] = None


# Support Models
class SupportMessageRequest(BaseModel):
    message: str
    conversation_history: Optional[List[Dict]] = None


class ContactRequest(BaseModel):
    name: str
    email: str
    subject: str
    message: str
