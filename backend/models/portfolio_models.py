"""
Portfolio Models - CoinTracker Parity
Data models for cost basis tracking, lot management, and portfolio aggregation
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class TransactionType(str, Enum):
    """Transaction classification types"""
    BUY = "buy"
    SELL = "sell"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    TRADE = "trade"  # Crypto-to-crypto
    INCOME = "income"  # Staking, airdrops, mining
    GIFT_RECEIVED = "gift_received"
    GIFT_SENT = "gift_sent"
    LOST = "lost"
    FEE = "fee"
    UNKNOWN = "unknown"


class CostBasisMethod(str, Enum):
    """Cost basis calculation methods"""
    FIFO = "fifo"  # First In, First Out
    LIFO = "lifo"  # Last In, First Out
    HIFO = "hifo"  # Highest In, First Out (tax optimization)
    SPECIFIC = "specific"  # User-selected lots


class TaxLot(BaseModel):
    """Individual tax lot representing a purchase/acquisition"""
    lot_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    asset_symbol: str  # e.g., "ETH", "BTC"
    chain: str  # e.g., "ethereum", "bitcoin"
    
    # Acquisition details
    acquisition_date: datetime
    acquisition_type: TransactionType  # buy, income, transfer_in, etc.
    acquisition_tx_hash: Optional[str] = None
    quantity: float  # Original quantity acquired
    remaining_quantity: float  # Remaining after partial sales
    cost_basis_usd: float  # Total cost in USD at time of acquisition
    cost_per_unit_usd: float  # Cost per unit
    
    # Source info
    source_wallet: str  # Wallet address where acquired
    source_exchange: Optional[str] = None  # If from exchange
    
    # Disposal tracking
    is_fully_disposed: bool = False
    disposals: List[Dict[str, Any]] = []  # List of partial disposals
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LinkedWallet(BaseModel):
    """A wallet linked to user's portfolio"""
    wallet_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    address: str
    chain: str
    nickname: Optional[str] = None
    
    # Linking info
    is_primary: bool = False
    wallet_group: Optional[str] = None  # Group related wallets (e.g., "My MetaMask")
    
    # Sync status
    last_synced_at: Optional[datetime] = None
    last_synced_block: Optional[int] = None
    sync_status: str = "pending"  # pending, syncing, synced, error
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PortfolioTransaction(BaseModel):
    """Normalized transaction for portfolio tracking"""
    tx_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    
    # Transaction identifiers
    tx_hash: str
    chain: str
    block_number: Optional[int] = None
    timestamp: datetime
    
    # Classification
    tx_type: TransactionType
    is_internal_transfer: bool = False  # Transfer between user's own wallets
    
    # Asset details
    asset_symbol: str
    asset_contract: Optional[str] = None  # For tokens
    quantity: float
    
    # USD values at time of transaction
    price_usd: Optional[float] = None
    value_usd: Optional[float] = None
    fee_usd: Optional[float] = None
    
    # Addresses
    from_address: str
    to_address: str
    from_wallet_id: Optional[str] = None  # If from user's linked wallet
    to_wallet_id: Optional[str] = None  # If to user's linked wallet
    
    # Tax lot linkage
    cost_basis_lot_ids: List[str] = []  # Tax lots used for this transaction
    realized_gain_usd: Optional[float] = None  # For disposals
    
    # User adjustments
    user_classification: Optional[TransactionType] = None  # Manual override
    user_notes: Optional[str] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class TokenHolding(BaseModel):
    """Current token holding for a wallet"""
    holding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    wallet_id: str
    wallet_address: str
    chain: str
    
    # Token info
    asset_symbol: str
    asset_name: Optional[str] = None
    contract_address: Optional[str] = None  # None for native tokens
    decimals: int = 18
    
    # Balance
    balance: float
    balance_raw: str  # Raw balance string for precision
    
    # Valuation
    price_usd: Optional[float] = None
    value_usd: Optional[float] = None
    
    # Cost basis summary
    total_cost_basis_usd: Optional[float] = None
    unrealized_gain_usd: Optional[float] = None
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class PortfolioSummary(BaseModel):
    """Aggregated portfolio summary across all wallets"""
    user_id: str
    
    # Total values
    total_value_usd: float = 0.0
    total_cost_basis_usd: float = 0.0
    total_unrealized_gain_usd: float = 0.0
    total_realized_gain_usd: float = 0.0
    
    # Holdings by asset
    holdings: List[Dict[str, Any]] = []  # Aggregated by asset
    
    # By wallet
    wallets: List[Dict[str, Any]] = []  # Summary per wallet
    
    # Tracking
    last_synced_at: Optional[datetime] = None
    cost_basis_method: CostBasisMethod = CostBasisMethod.FIFO


# Request/Response models for API

class LinkWalletRequest(BaseModel):
    """Request to link a new wallet"""
    address: str
    chain: str
    nickname: Optional[str] = None
    wallet_group: Optional[str] = None


class ClassifyTransactionRequest(BaseModel):
    """Request to manually classify a transaction"""
    tx_id: str
    tx_type: TransactionType
    notes: Optional[str] = None


class PortfolioSettingsUpdate(BaseModel):
    """Update portfolio settings"""
    cost_basis_method: Optional[CostBasisMethod] = None
    default_currency: Optional[str] = "USD"
