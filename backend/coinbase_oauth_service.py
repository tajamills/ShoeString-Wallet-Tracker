"""
Coinbase OAuth Service
Handles OAuth authentication and data fetching from Coinbase.
READ-ONLY access - cannot move or withdraw funds.
"""
import os
import secrets
import logging
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# OAuth Configuration
COINBASE_AUTH_URL = "https://login.coinbase.com/oauth2/auth"
COINBASE_TOKEN_URL = "https://login.coinbase.com/oauth2/token"
COINBASE_API_URL = "https://api.coinbase.com"

# READ-ONLY SCOPES ONLY - Cannot move funds
OAUTH_SCOPES = [
    "wallet:accounts:read",      # View account balances
    "wallet:transactions:read",  # View transaction history
    "wallet:addresses:read",     # View wallet addresses
]


class CoinbaseToken(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    expires_at: Optional[datetime] = None


class CoinbaseAccount(BaseModel):
    id: str
    name: str
    currency: str
    balance: float


class CoinbaseTransaction(BaseModel):
    id: str
    type: str  # send, receive, buy, sell, etc.
    amount: float
    currency: str
    created_at: str
    status: str
    # These are the key fields for Chain of Custody
    to_address: Optional[str] = None
    from_address: Optional[str] = None
    network_hash: Optional[str] = None  # Blockchain transaction hash


class CoinbaseAddress(BaseModel):
    id: str
    address: str
    name: Optional[str] = None
    network: str
    created_at: str


class CoinbaseOAuthService:
    """
    Coinbase OAuth Service - READ ONLY ACCESS
    
    Security Note:
    - Only requests read-only scopes
    - Cannot send, withdraw, or move any funds
    - User can revoke access at any time from Coinbase settings
    """
    
    def __init__(self):
        self.client_id = os.environ.get('COINBASE_CLIENT_ID', '')
        self.client_secret = os.environ.get('COINBASE_CLIENT_SECRET', '')
        self.redirect_uri = os.environ.get('COINBASE_REDIRECT_URI', '')
        
        # Store for OAuth state (in production, use Redis or database)
        self.state_store: Dict[str, Dict] = {}
    
    def get_authorization_url(self) -> tuple[str, str]:
        """
        Generate Coinbase OAuth authorization URL.
        Returns the URL and state parameter.
        """
        # Generate secure random state parameter to prevent CSRF
        state = secrets.token_urlsafe(32)
        self.state_store[state] = {
            "created_at": datetime.utcnow(),
            "used": False
        }
        
        # Build authorization URL with READ-ONLY scopes
        scope_string = " ".join(OAUTH_SCOPES)
        auth_url = (
            f"{COINBASE_AUTH_URL}"
            f"?response_type=code"
            f"&client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&state={state}"
            f"&scope={scope_string}"
        )
        
        return auth_url, state
    
    def validate_state(self, state: str) -> bool:
        """Validate OAuth state parameter to prevent CSRF attacks."""
        if state not in self.state_store:
            return False
        
        state_data = self.state_store[state]
        
        # Check if already used
        if state_data["used"]:
            return False
        
        # Check if expired (10 minute window)
        if datetime.utcnow() - state_data["created_at"] > timedelta(minutes=10):
            return False
        
        # Mark as used
        state_data["used"] = True
        return True
    
    async def exchange_code_for_tokens(self, code: str) -> CoinbaseToken:
        """
        Exchange authorization code for access and refresh tokens.
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                COINBASE_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed: {response.text}")
                raise Exception(f"Token exchange failed: {response.status_code}")
            
            token_data = response.json()
            return CoinbaseToken(
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data["expires_in"],
                token_type=token_data["token_type"],
                expires_at=datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
            )
    
    async def refresh_access_token(self, refresh_token: str) -> CoinbaseToken:
        """Refresh expired access token using refresh token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                COINBASE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Token refresh failed: {response.text}")
                raise Exception(f"Token refresh failed: {response.status_code}")
            
            token_data = response.json()
            return CoinbaseToken(
                access_token=token_data["access_token"],
                refresh_token=token_data.get("refresh_token", refresh_token),
                expires_in=token_data["expires_in"],
                token_type=token_data["token_type"],
                expires_at=datetime.utcnow() + timedelta(seconds=token_data["expires_in"])
            )
    
    async def get_accounts(self, access_token: str) -> List[CoinbaseAccount]:
        """
        Fetch all user accounts (wallets) from Coinbase.
        Requires wallet:accounts:read scope.
        """
        accounts = []
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COINBASE_API_URL}/v2/accounts",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch accounts: {response.text}")
                raise Exception(f"Failed to fetch accounts: {response.status_code}")
            
            data = response.json()
            
            for account in data.get("data", []):
                accounts.append(CoinbaseAccount(
                    id=account["id"],
                    name=account["name"],
                    currency=account["currency"]["code"],
                    balance=float(account["balance"]["amount"])
                ))
        
        return accounts
    
    async def get_transactions(
        self, 
        access_token: str, 
        account_id: str,
        limit: int = 100
    ) -> List[CoinbaseTransaction]:
        """
        Fetch transactions for a specific account.
        Requires wallet:transactions:read scope.
        
        This returns the TO and FROM addresses needed for Chain of Custody.
        """
        transactions = []
        
        async with httpx.AsyncClient() as client:
            # Fetch transactions with expanded network details
            response = await client.get(
                f"{COINBASE_API_URL}/v2/accounts/{account_id}/transactions",
                params={"limit": min(limit, 100), "expand": "all"},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch transactions: {response.text}")
                raise Exception(f"Failed to fetch transactions: {response.status_code}")
            
            data = response.json()
            
            for tx in data.get("data", []):
                # Extract addresses from the network field
                network = tx.get("network", {})
                to_addr = None
                from_addr = None
                network_hash = None
                
                if network:
                    # For sends, the 'to' field contains the destination
                    if tx.get("type") == "send":
                        to_resource = tx.get("to", {})
                        if isinstance(to_resource, dict):
                            to_addr = to_resource.get("address")
                    
                    # For receives, the 'from' field contains the source
                    if tx.get("type") == "receive":
                        from_resource = tx.get("from", {})
                        if isinstance(from_resource, dict):
                            from_addr = from_resource.get("address")
                    
                    # Get blockchain transaction hash
                    network_hash = network.get("hash")
                
                transactions.append(CoinbaseTransaction(
                    id=tx["id"],
                    type=tx["type"],
                    amount=float(tx["amount"]["amount"]),
                    currency=tx["amount"]["currency"],
                    created_at=tx["created_at"],
                    status=tx["status"],
                    to_address=to_addr,
                    from_address=from_addr,
                    network_hash=network_hash
                ))
        
        return transactions
    
    async def get_addresses(
        self, 
        access_token: str, 
        account_id: str
    ) -> List[CoinbaseAddress]:
        """
        Fetch cryptocurrency addresses for a specific account.
        Requires wallet:addresses:read scope.
        """
        addresses = []
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{COINBASE_API_URL}/v2/accounts/{account_id}/addresses",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30.0
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch addresses: {response.text}")
                raise Exception(f"Failed to fetch addresses: {response.status_code}")
            
            data = response.json()
            
            for addr in data.get("data", []):
                addresses.append(CoinbaseAddress(
                    id=addr["id"],
                    address=addr["address"],
                    name=addr.get("name"),
                    network=addr.get("network", "unknown"),
                    created_at=addr.get("created_at", "")
                ))
        
        return addresses
    
    async def get_all_wallet_addresses_for_custody(
        self, 
        access_token: str
    ) -> Dict[str, Any]:
        """
        Fetch all wallet addresses and transaction addresses for Chain of Custody.
        
        Returns:
        - All account wallet addresses
        - All destination addresses from Send transactions
        - All source addresses from Receive transactions
        """
        result = {
            "wallet_addresses": [],      # User's own addresses
            "send_destinations": [],     # Where user sent crypto TO
            "receive_sources": [],       # Where user received crypto FROM
            "all_addresses": set()       # Combined unique addresses for analysis
        }
        
        try:
            # Get all accounts
            accounts = await self.get_accounts(access_token)
            
            for account in accounts:
                # Get addresses for this account
                try:
                    addresses = await self.get_addresses(access_token, account.id)
                    for addr in addresses:
                        result["wallet_addresses"].append({
                            "address": addr.address,
                            "currency": account.currency,
                            "account_name": account.name,
                            "network": addr.network
                        })
                        result["all_addresses"].add(addr.address)
                except Exception as e:
                    logger.warning(f"Could not fetch addresses for account {account.id}: {e}")
                
                # Get transactions for this account
                try:
                    transactions = await self.get_transactions(access_token, account.id)
                    
                    for tx in transactions:
                        if tx.type == "send" and tx.to_address:
                            result["send_destinations"].append({
                                "address": tx.to_address,
                                "amount": abs(tx.amount),
                                "currency": tx.currency,
                                "date": tx.created_at,
                                "tx_hash": tx.network_hash,
                                "tx_id": tx.id
                            })
                            result["all_addresses"].add(tx.to_address)
                        
                        elif tx.type == "receive" and tx.from_address:
                            result["receive_sources"].append({
                                "address": tx.from_address,
                                "amount": abs(tx.amount),
                                "currency": tx.currency,
                                "date": tx.created_at,
                                "tx_hash": tx.network_hash,
                                "tx_id": tx.id
                            })
                            result["all_addresses"].add(tx.from_address)
                
                except Exception as e:
                    logger.warning(f"Could not fetch transactions for account {account.id}: {e}")
            
            # Convert set to list for JSON serialization
            result["all_addresses"] = list(result["all_addresses"])
            
            return result
            
        except Exception as e:
            logger.error(f"Error fetching wallet addresses for custody: {e}")
            raise


# Global service instance
coinbase_oauth_service = CoinbaseOAuthService()
