"""
Multi-Exchange Integration Service
Supports Binance, Kraken, and Gemini with READ-ONLY API access.
For tax tracking and Chain of Custody analysis.
"""
import os
import hmac
import hashlib
import time
import base64
import urllib.parse
import logging
import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ExchangeCredentials(BaseModel):
    api_key: str
    api_secret: str
    exchange: str  # 'binance', 'kraken', 'gemini'


class ExchangeTransaction(BaseModel):
    id: str
    exchange: str
    type: str  # 'trade', 'deposit', 'withdrawal'
    side: Optional[str] = None  # 'buy', 'sell' for trades
    asset: str
    amount: float
    price: Optional[float] = None
    fee: Optional[float] = None
    fee_asset: Optional[str] = None
    timestamp: str
    tx_hash: Optional[str] = None
    address: Optional[str] = None


class ExchangeAddress(BaseModel):
    address: str
    asset: str
    exchange: str
    network: Optional[str] = None


class BinanceClient:
    """Binance API Client - READ ONLY"""
    
    BASE_URL = "https://api.binance.com"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _sign_request(self, params: Dict) -> Dict:
        """Sign request with HMAC SHA256"""
        params['timestamp'] = int(time.time() * 1000)
        query_string = urllib.parse.urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        params['signature'] = signature
        return params
    
    async def _request(self, endpoint: str, params: Dict = None) -> Any:
        """Make authenticated request"""
        params = params or {}
        params = self._sign_request(params)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}{endpoint}",
                params=params,
                headers={"X-MBX-APIKEY": self.api_key},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_deposits(self, start_time: int = None) -> List[ExchangeTransaction]:
        """Get deposit history"""
        params = {}
        if start_time:
            params['startTime'] = start_time
        
        data = await self._request("/sapi/v1/capital/deposit/hisrec", params)
        
        return [
            ExchangeTransaction(
                id=d.get('txId', str(d.get('insertTime', ''))),
                exchange='binance',
                type='deposit',
                asset=d['coin'],
                amount=float(d['amount']),
                timestamp=datetime.fromtimestamp(d['insertTime'] / 1000).isoformat(),
                tx_hash=d.get('txId'),
                address=d.get('address')
            )
            for d in data
        ]
    
    async def get_withdrawals(self, start_time: int = None) -> List[ExchangeTransaction]:
        """Get withdrawal history"""
        params = {}
        if start_time:
            params['startTime'] = start_time
        
        data = await self._request("/sapi/v1/capital/withdraw/history", params)
        
        return [
            ExchangeTransaction(
                id=w.get('id', str(w.get('applyTime', ''))),
                exchange='binance',
                type='withdrawal',
                asset=w['coin'],
                amount=float(w['amount']),
                fee=float(w.get('transactionFee', 0)),
                timestamp=datetime.fromtimestamp(w['applyTime'] / 1000).isoformat() if isinstance(w.get('applyTime'), int) else w.get('applyTime', ''),
                tx_hash=w.get('txId'),
                address=w.get('address')
            )
            for w in data
        ]
    
    async def get_deposit_addresses(self) -> List[ExchangeAddress]:
        """Get deposit addresses for all coins with balance"""
        # First get account balances
        account = await self._request("/api/v3/account")
        addresses = []
        
        for balance in account.get('balances', []):
            if float(balance['free']) > 0 or float(balance['locked']) > 0:
                try:
                    addr_data = await self._request(
                        "/sapi/v1/capital/deposit/address",
                        {"coin": balance['asset']}
                    )
                    if addr_data.get('address'):
                        addresses.append(ExchangeAddress(
                            address=addr_data['address'],
                            asset=balance['asset'],
                            exchange='binance',
                            network=addr_data.get('network')
                        ))
                except Exception:
                    pass
        
        return addresses


class KrakenClient:
    """Kraken API Client - READ ONLY"""
    
    BASE_URL = "https://api.kraken.com"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = base64.b64decode(api_secret)
    
    def _sign_request(self, endpoint: str, data: Dict) -> str:
        """Sign request with HMAC SHA512"""
        nonce = str(int(time.time() * 1000))
        data['nonce'] = nonce
        
        postdata = urllib.parse.urlencode(data)
        encoded = (nonce + postdata).encode()
        message = endpoint.encode() + hashlib.sha256(encoded).digest()
        
        signature = hmac.new(self.api_secret, message, hashlib.sha512)
        return base64.b64encode(signature.digest()).decode()
    
    async def _request(self, endpoint: str, data: Dict = None) -> Any:
        """Make authenticated request"""
        data = data or {}
        signature = self._sign_request(endpoint, data)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}{endpoint}",
                data=data,
                headers={
                    "API-Key": self.api_key,
                    "API-Sign": signature
                },
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get('error'):
                raise Exception(f"Kraken API Error: {result['error']}")
            
            return result.get('result', {})
    
    async def get_deposits(self) -> List[ExchangeTransaction]:
        """Get deposit history"""
        data = await self._request("/0/private/DepositStatus", {"method": "all"})
        
        transactions = []
        for d in data if isinstance(data, list) else []:
            transactions.append(ExchangeTransaction(
                id=d.get('refid', ''),
                exchange='kraken',
                type='deposit',
                asset=d.get('asset', ''),
                amount=float(d.get('amount', 0)),
                fee=float(d.get('fee', 0)),
                timestamp=datetime.fromtimestamp(d.get('time', 0)).isoformat(),
                tx_hash=d.get('txid'),
                address=d.get('info')
            ))
        
        return transactions
    
    async def get_withdrawals(self) -> List[ExchangeTransaction]:
        """Get withdrawal history"""
        data = await self._request("/0/private/WithdrawStatus", {"method": "all"})
        
        transactions = []
        for w in data if isinstance(data, list) else []:
            transactions.append(ExchangeTransaction(
                id=w.get('refid', ''),
                exchange='kraken',
                type='withdrawal',
                asset=w.get('asset', ''),
                amount=float(w.get('amount', 0)),
                fee=float(w.get('fee', 0)),
                timestamp=datetime.fromtimestamp(w.get('time', 0)).isoformat(),
                tx_hash=w.get('txid'),
                address=w.get('info')
            ))
        
        return transactions
    
    async def get_deposit_addresses(self) -> List[ExchangeAddress]:
        """Get deposit addresses"""
        try:
            data = await self._request("/0/private/DepositMethods")
            addresses = []
            
            for method in data if isinstance(data, list) else []:
                try:
                    addr_data = await self._request(
                        "/0/private/DepositAddresses",
                        {"asset": method.get('asset'), "method": method.get('method')}
                    )
                    for addr in addr_data if isinstance(addr_data, list) else []:
                        addresses.append(ExchangeAddress(
                            address=addr.get('address', ''),
                            asset=method.get('asset', ''),
                            exchange='kraken',
                            network=method.get('method')
                        ))
                except Exception:
                    pass
            
            return addresses
        except Exception:
            return []


class GeminiClient:
    """Gemini API Client - READ ONLY"""
    
    BASE_URL = "https://api.gemini.com"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret.encode()
    
    def _sign_request(self, payload: Dict) -> tuple:
        """Sign request with HMAC SHA384"""
        payload['nonce'] = str(int(time.time() * 1000))
        
        encoded_payload = base64.b64encode(
            str(payload).replace("'", '"').encode()
        )
        signature = hmac.new(
            self.api_secret,
            encoded_payload,
            hashlib.sha384
        ).hexdigest()
        
        return encoded_payload.decode(), signature
    
    async def _request(self, endpoint: str, payload: Dict = None) -> Any:
        """Make authenticated request"""
        payload = payload or {}
        payload['request'] = endpoint
        
        encoded_payload, signature = self._sign_request(payload)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}{endpoint}",
                headers={
                    "Content-Type": "text/plain",
                    "X-GEMINI-APIKEY": self.api_key,
                    "X-GEMINI-PAYLOAD": encoded_payload,
                    "X-GEMINI-SIGNATURE": signature
                },
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_transfers(self) -> List[ExchangeTransaction]:
        """Get transfer history (deposits and withdrawals)"""
        data = await self._request("/v1/transfers")
        
        transactions = []
        for t in data if isinstance(data, list) else []:
            transactions.append(ExchangeTransaction(
                id=t.get('eid', ''),
                exchange='gemini',
                type='deposit' if t.get('type') == 'Deposit' else 'withdrawal',
                asset=t.get('currency', ''),
                amount=float(t.get('amount', 0)),
                fee=float(t.get('feeAmount', 0)) if t.get('feeAmount') else None,
                timestamp=datetime.fromtimestamp(t.get('timestampms', 0) / 1000).isoformat(),
                tx_hash=t.get('txHash'),
                address=t.get('destination') or t.get('source')
            ))
        
        return transactions
    
    async def get_deposit_addresses(self) -> List[ExchangeAddress]:
        """Get deposit addresses"""
        try:
            # Gemini requires specifying currency
            currencies = ['BTC', 'ETH', 'LTC', 'BCH']
            addresses = []
            
            for currency in currencies:
                try:
                    data = await self._request(
                        f"/v1/deposit/{currency.lower()}/newAddress"
                    )
                    if data.get('address'):
                        addresses.append(ExchangeAddress(
                            address=data['address'],
                            asset=currency,
                            exchange='gemini'
                        ))
                except Exception:
                    pass
            
            return addresses
        except Exception:
            return []


class MultiExchangeService:
    """
    Unified service for multiple exchange integrations.
    All access is READ-ONLY - cannot move or withdraw funds.
    """
    
    SUPPORTED_EXCHANGES = ['binance', 'kraken', 'gemini', 'coinbase']
    
    def __init__(self):
        self.clients: Dict[str, Any] = {}
    
    def add_exchange(self, exchange: str, api_key: str, api_secret: str) -> bool:
        """Add an exchange connection"""
        exchange = exchange.lower()
        
        if exchange == 'binance':
            self.clients[exchange] = BinanceClient(api_key, api_secret)
        elif exchange == 'kraken':
            self.clients[exchange] = KrakenClient(api_key, api_secret)
        elif exchange == 'gemini':
            self.clients[exchange] = GeminiClient(api_key, api_secret)
        else:
            return False
        
        return True
    
    def remove_exchange(self, exchange: str) -> bool:
        """Remove an exchange connection"""
        exchange = exchange.lower()
        if exchange in self.clients:
            del self.clients[exchange]
            return True
        return False
    
    async def get_all_transactions(self, exchange: str = None) -> List[ExchangeTransaction]:
        """Get all transactions from connected exchanges"""
        transactions = []
        
        clients_to_query = (
            {exchange: self.clients[exchange]} if exchange and exchange in self.clients
            else self.clients
        )
        
        for ex_name, client in clients_to_query.items():
            try:
                if ex_name == 'gemini':
                    txs = await client.get_transfers()
                else:
                    deposits = await client.get_deposits()
                    withdrawals = await client.get_withdrawals()
                    txs = deposits + withdrawals
                
                transactions.extend(txs)
            except Exception as e:
                logger.error(f"Error fetching from {ex_name}: {e}")
        
        return sorted(transactions, key=lambda x: x.timestamp, reverse=True)
    
    async def get_all_addresses(self, exchange: str = None) -> List[ExchangeAddress]:
        """Get all deposit addresses from connected exchanges"""
        addresses = []
        
        clients_to_query = (
            {exchange: self.clients[exchange]} if exchange and exchange in self.clients
            else self.clients
        )
        
        for ex_name, client in clients_to_query.items():
            try:
                addrs = await client.get_deposit_addresses()
                addresses.extend(addrs)
            except Exception as e:
                logger.error(f"Error fetching addresses from {ex_name}: {e}")
        
        return addresses
    
    async def get_addresses_for_custody(self, exchange: str = None) -> Dict[str, Any]:
        """
        Get all addresses suitable for Chain of Custody analysis.
        Includes deposit addresses and transaction addresses.
        """
        result = {
            "wallet_addresses": [],
            "send_destinations": [],
            "receive_sources": [],
            "all_addresses": set()
        }
        
        # Get deposit addresses (user's own addresses)
        addresses = await self.get_all_addresses(exchange)
        for addr in addresses:
            result["wallet_addresses"].append({
                "address": addr.address,
                "asset": addr.asset,
                "exchange": addr.exchange,
                "network": addr.network
            })
            result["all_addresses"].add(addr.address)
        
        # Get transaction addresses
        transactions = await self.get_all_transactions(exchange)
        for tx in transactions:
            if tx.address:
                if tx.type == 'withdrawal':
                    result["send_destinations"].append({
                        "address": tx.address,
                        "amount": tx.amount,
                        "asset": tx.asset,
                        "date": tx.timestamp,
                        "tx_hash": tx.tx_hash,
                        "exchange": tx.exchange
                    })
                elif tx.type == 'deposit':
                    result["receive_sources"].append({
                        "address": tx.address,
                        "amount": tx.amount,
                        "asset": tx.asset,
                        "date": tx.timestamp,
                        "tx_hash": tx.tx_hash,
                        "exchange": tx.exchange
                    })
                result["all_addresses"].add(tx.address)
        
        result["all_addresses"] = list(result["all_addresses"])
        return result


# Global service instance
multi_exchange_service = MultiExchangeService()
