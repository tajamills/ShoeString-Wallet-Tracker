"""
Multi-Exchange Integration Service
Supports Binance, Kraken, Gemini, Crypto.com, KuCoin, and OKX with READ-ONLY API access.
For tax tracking and Chain of Custody analysis.
"""
import os
import hmac
import hashlib
import time
import base64
import json
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


class CoinbaseClient:
    """Coinbase API Client - READ ONLY (uses API Key, not OAuth)"""
    
    BASE_URL = "https://api.coinbase.com"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _sign_request(self, method: str, path: str, body: str = "") -> Dict[str, str]:
        """Sign request with HMAC SHA256 for Coinbase API"""
        timestamp = str(int(time.time()))
        message = timestamp + method.upper() + path + body
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "CB-VERSION": "2023-01-01",
            "Content-Type": "application/json"
        }
    
    async def _request(self, method: str, endpoint: str, params: Dict = None) -> Any:
        """Make authenticated request"""
        path = endpoint
        if params and method == "GET":
            query = urllib.parse.urlencode(params)
            path = f"{endpoint}?{query}"
        
        headers = self._sign_request(method, path)
        
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(
                    f"{self.BASE_URL}{path}",
                    headers=headers,
                    timeout=30.0
                )
            else:
                response = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    json=params or {},
                    timeout=30.0
                )
            
            response.raise_for_status()
            return response.json()
    
    async def get_accounts(self) -> List[Dict]:
        """Get all accounts/wallets"""
        try:
            data = await self._request("GET", "/v2/accounts", {"limit": 100})
            return data.get('data', [])
        except Exception as e:
            logger.error(f"Coinbase get_accounts error: {e}")
            return []
    
    async def get_deposits(self) -> List[ExchangeTransaction]:
        """Get deposit history from all accounts"""
        transactions = []
        
        try:
            accounts = await self.get_accounts()
            
            for account in accounts:
                account_id = account.get('id')
                if not account_id:
                    continue
                
                try:
                    data = await self._request(
                        "GET", 
                        f"/v2/accounts/{account_id}/transactions",
                        {"limit": 100}
                    )
                    
                    for tx in data.get('data', []):
                        tx_type = tx.get('type', '')
                        # Only get deposits (receives from external)
                        if tx_type in ['send', 'receive'] and tx.get('network', {}).get('status') == 'confirmed':
                            if tx_type == 'receive' or (tx_type == 'send' and float(tx.get('amount', {}).get('amount', 0)) > 0):
                                transactions.append(ExchangeTransaction(
                                    id=tx.get('id', ''),
                                    exchange='coinbase',
                                    type='deposit' if tx_type == 'receive' else 'withdrawal',
                                    asset=tx.get('amount', {}).get('currency', ''),
                                    amount=abs(float(tx.get('amount', {}).get('amount', 0))),
                                    timestamp=tx.get('created_at', ''),
                                    tx_hash=tx.get('network', {}).get('hash'),
                                    address=tx.get('to', {}).get('address') or tx.get('from', {}).get('address')
                                ))
                except Exception as e:
                    logger.error(f"Coinbase get transactions for account {account_id}: {e}")
                    continue
            
            return transactions
        except Exception as e:
            logger.error(f"Coinbase get_deposits error: {e}")
            return []
    
    async def get_all_transactions(self) -> List[Dict]:
        """Fetch ALL transactions (buys, sells, sends, receives) from all Coinbase accounts"""
        all_txs = []
        
        try:
            accounts = await self.get_accounts()
            logger.info(f"Coinbase sync: found {len(accounts)} accounts")
            
            for account in accounts:
                account_id = account.get('id')
                currency = account.get('currency', {}).get('code', '')
                
                if not account_id or not currency:
                    continue
                
                # Skip fiat accounts
                if currency in ['USD', 'EUR', 'GBP', 'CAD', 'AUD', 'JPY']:
                    continue
                
                try:
                    # Fetch all transactions for this account (paginated)
                    next_uri = f"/v2/accounts/{account_id}/transactions"
                    page_params = {"limit": 100, "order": "desc"}
                    
                    while next_uri:
                        data = await self._request("GET", next_uri, page_params if '?' not in next_uri else None)
                        
                        for tx in data.get('data', []):
                            tx_type = tx.get('type', '')
                            amount_data = tx.get('amount', {})
                            native_amount = tx.get('native_amount', {})
                            
                            amount = abs(float(amount_data.get('amount', 0)))
                            usd_total = abs(float(native_amount.get('amount', 0)))
                            price_usd = usd_total / amount if amount > 0 else 0
                            
                            # Map Coinbase types to our standard types
                            type_map = {
                                'buy': 'buy',
                                'sell': 'sell',
                                'send': 'sell',  # Sending out = disposition
                                'receive': 'buy',  # Receiving = acquisition
                                'trade': 'buy',  # Trade - determine by sign
                                'staking_reward': 'buy',
                                'inflation_reward': 'buy',
                                'interest': 'buy',
                                'learning_reward': 'buy',
                            }
                            
                            mapped_type = type_map.get(tx_type)
                            if not mapped_type:
                                continue
                            
                            # For sends, if amount is negative in the original, it's an outgoing tx
                            original_amount = float(amount_data.get('amount', 0))
                            if tx_type == 'trade':
                                mapped_type = 'buy' if original_amount > 0 else 'sell'
                            
                            all_txs.append({
                                'tx_id': tx.get('id', ''),
                                'exchange': 'coinbase',
                                'tx_type': mapped_type,
                                'asset': currency,
                                'amount': amount,
                                'price_usd': price_usd,
                                'total_usd': usd_total,
                                'timestamp': tx.get('created_at', ''),
                                'source': f"exchange:coinbase",
                                'notes': f"Coinbase {tx_type}",
                                'status': tx.get('status', 'completed')
                            })
                        
                        # Handle pagination
                        pagination = data.get('pagination', {})
                        next_uri = pagination.get('next_uri')
                        page_params = None  # next_uri already has params
                        
                except Exception as e:
                    logger.warning(f"Coinbase: error fetching transactions for {currency}: {e}")
                    continue
            
            logger.info(f"Coinbase sync: fetched {len(all_txs)} total transactions")
            return all_txs
            
        except Exception as e:
            logger.error(f"Coinbase get_all_transactions error: {e}")
            return []
    
    async def get_withdrawals(self) -> List[ExchangeTransaction]:
        """Get withdrawal history - combined with deposits above"""
        # Withdrawals are fetched together with deposits in get_deposits
        return []
    
    async def get_deposit_addresses(self) -> List[ExchangeAddress]:
        """Get deposit addresses for all accounts, including from transactions"""
        addresses = []
        seen_addresses = set()
        
        try:
            accounts = await self.get_accounts()
            logger.info(f"Coinbase: Found {len(accounts)} accounts")
            
            for account in accounts:
                account_id = account.get('id')
                currency = account.get('currency', {}).get('code', '')
                account_name = account.get('name', '')
                balance = account.get('balance', {}).get('amount', '0')
                
                if not account_id:
                    continue
                
                logger.debug(f"Coinbase account: {account_name} ({currency}) - balance: {balance}")
                
                # Skip fiat accounts - they don't have blockchain addresses
                if currency in ['USD', 'EUR', 'GBP', 'CAD', 'AUD']:
                    continue
                
                # Try to get deposit addresses for this account
                try:
                    data = await self._request(
                        "GET",
                        f"/v2/accounts/{account_id}/addresses",
                        {"limit": 25}
                    )
                    
                    for addr in data.get('data', []):
                        address = addr.get('address')
                        if address and address not in seen_addresses:
                            seen_addresses.add(address)
                            network = addr.get('network') or self._guess_network(currency)
                            addresses.append(ExchangeAddress(
                                address=address,
                                asset=currency,
                                exchange='coinbase',
                                network=network
                            ))
                            logger.info(f"Coinbase address found: {address[:16]}... ({currency})")
                except httpx.HTTPStatusError as e:
                    # 404 means no addresses created for this account - that's OK
                    if e.response.status_code != 404:
                        logger.warning(f"Coinbase addresses error for {currency}: {e}")
                except Exception as e:
                    logger.debug(f"No addresses for {currency}: {e}")
                
                # Also get addresses from transactions (sends/receives)
                try:
                    tx_data = await self._request(
                        "GET",
                        f"/v2/accounts/{account_id}/transactions",
                        {"limit": 50}
                    )
                    
                    for tx in tx_data.get('data', []):
                        tx_type = tx.get('type', '')
                        network_data = tx.get('network', {})
                        
                        # Get address from transaction
                        if tx_type == 'send':
                            to_addr = tx.get('to', {})
                            address = to_addr.get('address') if isinstance(to_addr, dict) else None
                        elif tx_type in ['receive', 'deposit']:
                            from_addr = tx.get('from', {})
                            address = from_addr.get('address') if isinstance(from_addr, dict) else None
                            # Also check network.transaction_url for address
                            if not address and network_data:
                                # Try to extract from hash
                                pass
                        else:
                            continue
                        
                        if address and address not in seen_addresses:
                            seen_addresses.add(address)
                            network = network_data.get('name') or self._guess_network(currency)
                            addresses.append(ExchangeAddress(
                                address=address,
                                asset=currency,
                                exchange='coinbase',
                                network=network
                            ))
                except Exception as e:
                    logger.debug(f"Transaction fetch failed for {currency}: {e}")
            
            logger.info(f"Coinbase: Total {len(addresses)} addresses found")
            return addresses
            
        except Exception as e:
            logger.error(f"Coinbase get_deposit_addresses error: {e}")
            return []
    
    def _guess_network(self, currency: str) -> str:
        """Guess the network based on currency"""
        network_map = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'SOL': 'solana',
            'DOGE': 'dogecoin',
            'LTC': 'litecoin',
            'XRP': 'xrp',
            'XLM': 'stellar',
            'ALGO': 'algorand',
            'MATIC': 'polygon',
            'AVAX': 'avalanche',
        }
        return network_map.get(currency.upper(), 'ethereum')


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


class CryptoComClient:
    """Crypto.com Exchange API Client - READ ONLY"""
    
    BASE_URL = "https://api.crypto.com/v2"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _sign_request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """Sign request with HMAC SHA256"""
        params = params or {}
        nonce = str(int(time.time() * 1000))
        
        params_str = ""
        if params:
            params_str = "".join(f"{k}{params[k]}" for k in sorted(params.keys()))
        
        sig_payload = f"{method}{endpoint.split('/')[-1]}{self.api_key}{params_str}{nonce}"
        signature = hmac.new(
            self.api_secret.encode(),
            sig_payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return {
            "id": 1,
            "method": endpoint.split('/')[-1],
            "api_key": self.api_key,
            "params": params,
            "sig": signature,
            "nonce": nonce
        }
    
    async def _request(self, method: str, endpoint: str, params: Dict = None) -> Any:
        """Make authenticated request"""
        payload = self._sign_request(method, endpoint, params)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.BASE_URL}/{endpoint}",
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != 0:
                raise Exception(f"Crypto.com API Error: {data.get('message')}")
            
            return data.get('result', {})
    
    async def get_deposits(self) -> List[ExchangeTransaction]:
        """Get deposit history"""
        try:
            data = await self._request("POST", "private/get-deposit-history")
            
            transactions = []
            for d in data.get('deposit_list', []):
                transactions.append(ExchangeTransaction(
                    id=d.get('id', ''),
                    exchange='cryptocom',
                    type='deposit',
                    asset=d.get('currency', ''),
                    amount=float(d.get('amount', 0)),
                    fee=float(d.get('fee', 0)) if d.get('fee') else None,
                    timestamp=datetime.fromtimestamp(d.get('create_time', 0) / 1000).isoformat(),
                    tx_hash=d.get('txid'),
                    address=d.get('address')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"Crypto.com get_deposits error: {e}")
            return []
    
    async def get_withdrawals(self) -> List[ExchangeTransaction]:
        """Get withdrawal history"""
        try:
            data = await self._request("POST", "private/get-withdrawal-history")
            
            transactions = []
            for w in data.get('withdrawal_list', []):
                transactions.append(ExchangeTransaction(
                    id=w.get('id', ''),
                    exchange='cryptocom',
                    type='withdrawal',
                    asset=w.get('currency', ''),
                    amount=float(w.get('amount', 0)),
                    fee=float(w.get('fee', 0)) if w.get('fee') else None,
                    timestamp=datetime.fromtimestamp(w.get('create_time', 0) / 1000).isoformat(),
                    tx_hash=w.get('txid'),
                    address=w.get('address')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"Crypto.com get_withdrawals error: {e}")
            return []
    
    async def get_deposit_addresses(self) -> List[ExchangeAddress]:
        """Get deposit addresses"""
        try:
            data = await self._request("POST", "private/get-deposit-address", {"currency": "BTC"})
            addresses = []
            
            for addr in data.get('deposit_address_list', []):
                addresses.append(ExchangeAddress(
                    address=addr.get('address', ''),
                    asset=addr.get('currency', ''),
                    exchange='cryptocom',
                    network=addr.get('network')
                ))
            
            return addresses
        except Exception:
            return []


class KuCoinClient:
    """KuCoin API Client - READ ONLY"""
    
    BASE_URL = "https://api.kucoin.com"
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase or ""
    
    def _sign_request(self, method: str, endpoint: str, body: str = "") -> Dict:
        """Sign request with HMAC SHA256"""
        timestamp = str(int(time.time() * 1000))
        str_to_sign = timestamp + method.upper() + endpoint + body
        
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode(),
                str_to_sign.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        passphrase_sign = base64.b64encode(
            hmac.new(
                self.api_secret.encode(),
                self.passphrase.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        
        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": timestamp,
            "KC-API-PASSPHRASE": passphrase_sign,
            "KC-API-KEY-VERSION": "2"
        }
    
    async def _request(self, method: str, endpoint: str, params: Dict = None) -> Any:
        """Make authenticated request"""
        body = json.dumps(params) if params and method == "POST" else ""
        headers = self._sign_request(method, endpoint, body)
        headers["Content-Type"] = "application/json"
        
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    timeout=30.0
                )
            else:
                response = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    content=body,
                    timeout=30.0
                )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != '200000':
                raise Exception(f"KuCoin API Error: {data.get('msg')}")
            
            return data.get('data', {})
    
    async def get_deposits(self) -> List[ExchangeTransaction]:
        """Get deposit history"""
        try:
            data = await self._request("GET", "/api/v1/deposits")
            
            transactions = []
            for d in data.get('items', []):
                transactions.append(ExchangeTransaction(
                    id=d.get('id', ''),
                    exchange='kucoin',
                    type='deposit',
                    asset=d.get('currency', ''),
                    amount=float(d.get('amount', 0)),
                    fee=float(d.get('fee', 0)) if d.get('fee') else None,
                    timestamp=datetime.fromtimestamp(d.get('createdAt', 0) / 1000).isoformat(),
                    tx_hash=d.get('walletTxId'),
                    address=d.get('address')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"KuCoin get_deposits error: {e}")
            return []
    
    async def get_withdrawals(self) -> List[ExchangeTransaction]:
        """Get withdrawal history"""
        try:
            data = await self._request("GET", "/api/v1/withdrawals")
            
            transactions = []
            for w in data.get('items', []):
                transactions.append(ExchangeTransaction(
                    id=w.get('id', ''),
                    exchange='kucoin',
                    type='withdrawal',
                    asset=w.get('currency', ''),
                    amount=float(w.get('amount', 0)),
                    fee=float(w.get('fee', 0)) if w.get('fee') else None,
                    timestamp=datetime.fromtimestamp(w.get('createdAt', 0) / 1000).isoformat(),
                    tx_hash=w.get('walletTxId'),
                    address=w.get('address')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"KuCoin get_withdrawals error: {e}")
            return []
    
    async def get_deposit_addresses(self) -> List[ExchangeAddress]:
        """Get deposit addresses"""
        try:
            # KuCoin requires specifying currency
            currencies = ['BTC', 'ETH', 'USDT']
            addresses = []
            
            for currency in currencies:
                try:
                    data = await self._request("GET", f"/api/v1/deposit-addresses?currency={currency}")
                    if data.get('address'):
                        addresses.append(ExchangeAddress(
                            address=data['address'],
                            asset=currency,
                            exchange='kucoin',
                            network=data.get('chain')
                        ))
                except Exception:
                    pass
            
            return addresses
        except Exception:
            return []


class OKXClient:
    """OKX API Client - READ ONLY"""
    
    BASE_URL = "https://www.okx.com"
    
    def __init__(self, api_key: str, api_secret: str, passphrase: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase or ""
    
    def _sign_request(self, timestamp: str, method: str, endpoint: str, body: str = "") -> str:
        """Sign request with HMAC SHA256"""
        message = timestamp + method.upper() + endpoint + body
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode(),
                message.encode(),
                hashlib.sha256
            ).digest()
        ).decode()
        return signature
    
    async def _request(self, method: str, endpoint: str, params: Dict = None) -> Any:
        """Make authenticated request"""
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
        body = json.dumps(params) if params and method == "POST" else ""
        
        signature = self._sign_request(timestamp, method, endpoint, body)
        
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    timeout=30.0
                )
            else:
                response = await client.post(
                    f"{self.BASE_URL}{endpoint}",
                    headers=headers,
                    content=body,
                    timeout=30.0
                )
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') != '0':
                raise Exception(f"OKX API Error: {data.get('msg')}")
            
            return data.get('data', [])
    
    async def get_deposits(self) -> List[ExchangeTransaction]:
        """Get deposit history"""
        try:
            data = await self._request("GET", "/api/v5/asset/deposit-history")
            
            transactions = []
            for d in data if isinstance(data, list) else []:
                transactions.append(ExchangeTransaction(
                    id=d.get('depId', ''),
                    exchange='okx',
                    type='deposit',
                    asset=d.get('ccy', ''),
                    amount=float(d.get('amt', 0)),
                    fee=float(d.get('fee', 0)) if d.get('fee') else None,
                    timestamp=datetime.fromtimestamp(int(d.get('ts', 0)) / 1000).isoformat(),
                    tx_hash=d.get('txId'),
                    address=d.get('to')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"OKX get_deposits error: {e}")
            return []
    
    async def get_withdrawals(self) -> List[ExchangeTransaction]:
        """Get withdrawal history"""
        try:
            data = await self._request("GET", "/api/v5/asset/withdrawal-history")
            
            transactions = []
            for w in data if isinstance(data, list) else []:
                transactions.append(ExchangeTransaction(
                    id=w.get('wdId', ''),
                    exchange='okx',
                    type='withdrawal',
                    asset=w.get('ccy', ''),
                    amount=float(w.get('amt', 0)),
                    fee=float(w.get('fee', 0)) if w.get('fee') else None,
                    timestamp=datetime.fromtimestamp(int(w.get('ts', 0)) / 1000).isoformat(),
                    tx_hash=w.get('txId'),
                    address=w.get('to')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"OKX get_withdrawals error: {e}")
            return []
    
    async def get_deposit_addresses(self) -> List[ExchangeAddress]:
        """Get deposit addresses"""
        try:
            data = await self._request("GET", "/api/v5/asset/deposit-address?ccy=BTC")
            addresses = []
            
            for addr in data if isinstance(data, list) else []:
                addresses.append(ExchangeAddress(
                    address=addr.get('addr', ''),
                    asset=addr.get('ccy', ''),
                    exchange='okx',
                    network=addr.get('chain')
                ))
            
            return addresses
        except Exception:
            return []


class BybitClient:
    """Bybit API Client - READ ONLY"""
    
    BASE_URL = "https://api.bybit.com"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _sign_request(self, params: Dict) -> Dict:
        """Sign request with HMAC SHA256"""
        timestamp = str(int(time.time() * 1000))
        params['api_key'] = self.api_key
        params['timestamp'] = timestamp
        
        # Sort params and create query string
        sorted_params = sorted(params.items())
        query_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
        
        signature = hmac.new(
            self.api_secret.encode(),
            query_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        params['sign'] = signature
        return params
    
    async def _request(self, endpoint: str, params: Dict = None) -> Any:
        """Make authenticated request"""
        params = params or {}
        params = self._sign_request(params)
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.BASE_URL}{endpoint}",
                params=params,
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get('ret_code') != 0:
                raise Exception(f"Bybit API Error: {data.get('ret_msg')}")
            
            return data.get('result', {})
    
    async def get_deposits(self) -> List[ExchangeTransaction]:
        """Get deposit history"""
        try:
            data = await self._request("/v5/asset/deposit/query-record")
            
            transactions = []
            for d in data.get('rows', []):
                transactions.append(ExchangeTransaction(
                    id=d.get('txID', ''),
                    exchange='bybit',
                    type='deposit',
                    asset=d.get('coin', ''),
                    amount=float(d.get('amount', 0)),
                    timestamp=datetime.fromtimestamp(int(d.get('successAt', 0)) / 1000).isoformat() if d.get('successAt') else '',
                    tx_hash=d.get('txID'),
                    address=d.get('toAddress')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"Bybit get_deposits error: {e}")
            return []
    
    async def get_withdrawals(self) -> List[ExchangeTransaction]:
        """Get withdrawal history"""
        try:
            data = await self._request("/v5/asset/withdraw/query-record")
            
            transactions = []
            for w in data.get('rows', []):
                transactions.append(ExchangeTransaction(
                    id=w.get('withdrawId', ''),
                    exchange='bybit',
                    type='withdrawal',
                    asset=w.get('coin', ''),
                    amount=float(w.get('amount', 0)),
                    fee=float(w.get('withdrawFee', 0)) if w.get('withdrawFee') else None,
                    timestamp=datetime.fromtimestamp(int(w.get('createTime', 0)) / 1000).isoformat() if w.get('createTime') else '',
                    tx_hash=w.get('txID'),
                    address=w.get('toAddress')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"Bybit get_withdrawals error: {e}")
            return []
    
    async def get_deposit_addresses(self) -> List[ExchangeAddress]:
        """Get deposit addresses"""
        try:
            data = await self._request("/v5/asset/deposit/query-address", {"coin": "BTC"})
            addresses = []
            
            chains = data.get('chains', [])
            for chain in chains:
                if chain.get('addressDeposit'):
                    addresses.append(ExchangeAddress(
                        address=chain['addressDeposit'],
                        asset='BTC',
                        exchange='bybit',
                        network=chain.get('chain')
                    ))
            
            return addresses
        except Exception:
            return []


class GateIOClient:
    """Gate.io API Client - READ ONLY"""
    
    BASE_URL = "https://api.gateio.ws/api/v4"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _sign_request(self, method: str, url: str, query_string: str = "", body: str = "") -> Dict:
        """Sign request with HMAC SHA512"""
        timestamp = str(int(time.time()))
        
        # Hash body if present
        body_hash = hashlib.sha512(body.encode() if body else b"").hexdigest()
        
        # Create signature string
        sign_string = f"{method}\n{url}\n{query_string}\n{body_hash}\n{timestamp}"
        
        signature = hmac.new(
            self.api_secret.encode(),
            sign_string.encode(),
            hashlib.sha512
        ).hexdigest()
        
        return {
            "KEY": self.api_key,
            "Timestamp": timestamp,
            "SIGN": signature
        }
    
    async def _request(self, method: str, endpoint: str, params: Dict = None) -> Any:
        """Make authenticated request"""
        query_string = urllib.parse.urlencode(params) if params else ""
        headers = self._sign_request(method, endpoint, query_string)
        headers["Content-Type"] = "application/json"
        
        url = f"{self.BASE_URL}{endpoint}"
        if query_string:
            url += f"?{query_string}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_deposits(self) -> List[ExchangeTransaction]:
        """Get deposit history"""
        try:
            data = await self._request("GET", "/wallet/deposits")
            
            transactions = []
            for d in data if isinstance(data, list) else []:
                transactions.append(ExchangeTransaction(
                    id=d.get('id', ''),
                    exchange='gateio',
                    type='deposit',
                    asset=d.get('currency', ''),
                    amount=float(d.get('amount', 0)),
                    timestamp=datetime.fromtimestamp(int(d.get('timestamp', 0))).isoformat() if d.get('timestamp') else '',
                    tx_hash=d.get('txid'),
                    address=d.get('address')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"Gate.io get_deposits error: {e}")
            return []
    
    async def get_withdrawals(self) -> List[ExchangeTransaction]:
        """Get withdrawal history"""
        try:
            data = await self._request("GET", "/wallet/withdrawals")
            
            transactions = []
            for w in data if isinstance(data, list) else []:
                transactions.append(ExchangeTransaction(
                    id=w.get('id', ''),
                    exchange='gateio',
                    type='withdrawal',
                    asset=w.get('currency', ''),
                    amount=float(w.get('amount', 0)),
                    fee=float(w.get('fee', 0)) if w.get('fee') else None,
                    timestamp=datetime.fromtimestamp(int(w.get('timestamp', 0))).isoformat() if w.get('timestamp') else '',
                    tx_hash=w.get('txid'),
                    address=w.get('address')
                ))
            
            return transactions
        except Exception as e:
            logger.error(f"Gate.io get_withdrawals error: {e}")
            return []
    
    async def get_deposit_addresses(self) -> List[ExchangeAddress]:
        """Get deposit addresses"""
        try:
            data = await self._request("GET", "/wallet/deposit_address", {"currency": "BTC"})
            addresses = []
            
            if data.get('address'):
                addresses.append(ExchangeAddress(
                    address=data['address'],
                    asset='BTC',
                    exchange='gateio',
                    network=data.get('chain')
                ))
            
            return addresses
        except Exception:
            return []


class MultiExchangeService:
    """
    Unified service for multiple exchange integrations.
    All access is READ-ONLY - cannot move or withdraw funds.
    """
    
    SUPPORTED_EXCHANGES = ['binance', 'kraken', 'gemini', 'coinbase', 'cryptocom', 'kucoin', 'okx', 'bybit', 'gateio']
    
    def __init__(self):
        self.clients: Dict[str, Any] = {}
    
    def add_exchange(self, exchange: str, api_key: str, api_secret: str, passphrase: str = None) -> bool:
        """Add an exchange connection"""
        exchange = exchange.lower()
        
        if exchange == 'binance':
            self.clients[exchange] = BinanceClient(api_key, api_secret)
        elif exchange == 'kraken':
            self.clients[exchange] = KrakenClient(api_key, api_secret)
        elif exchange == 'gemini':
            self.clients[exchange] = GeminiClient(api_key, api_secret)
        elif exchange == 'coinbase':
            self.clients[exchange] = CoinbaseClient(api_key, api_secret)
        elif exchange == 'cryptocom':
            self.clients[exchange] = CryptoComClient(api_key, api_secret)
        elif exchange == 'kucoin':
            self.clients[exchange] = KuCoinClient(api_key, api_secret, passphrase)
        elif exchange == 'okx':
            self.clients[exchange] = OKXClient(api_key, api_secret, passphrase)
        elif exchange == 'bybit':
            self.clients[exchange] = BybitClient(api_key, api_secret)
        elif exchange == 'gateio':
            self.clients[exchange] = GateIOClient(api_key, api_secret)
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
