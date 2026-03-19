import os
import requests
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime
import logging
from price_service import price_service
from tax_service import tax_service

logger = logging.getLogger(__name__)

class MultiChainService:
    """Service to handle wallet analysis across multiple blockchains"""
    
    def __init__(self):
        self.alchemy_api_key = os.environ.get('ALCHEMY_API_KEY')
        
        # Chain configurations
        self.chains = {
            "ethereum": {
                "name": "Ethereum",
                "alchemy_url": f"https://eth-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
                "decimals": 18,
                "symbol": "ETH",
                "explorer": "https://etherscan.io"
            },
            "arbitrum": {
                "name": "Arbitrum",
                "alchemy_url": f"https://arb-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
                "decimals": 18,
                "symbol": "ETH",
                "explorer": "https://arbiscan.io"
            },
            "bsc": {
                "name": "BNB Smart Chain",
                "alchemy_url": f"https://bnb-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
                "decimals": 18,
                "symbol": "BNB",
                "explorer": "https://bscscan.com"
            },
            "bitcoin": {
                "name": "Bitcoin",
                "api_url": "https://blockchain.info",
                "decimals": 8,
                "symbol": "BTC",
                "explorer": "https://blockchain.info"
            },
            "solana": {
                "name": "Solana",
                "alchemy_url": f"https://solana-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
                "decimals": 9,
                "symbol": "SOL",
                "explorer": "https://solscan.io"
            },
            "polygon": {
                "name": "Polygon",
                "alchemy_url": f"https://polygon-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
                "decimals": 18,
                "symbol": "MATIC",
                "explorer": "https://polygonscan.com"
            },
            "algorand": {
                "name": "Algorand",
                "api_url": "https://mainnet-idx.algonode.cloud",
                "decimals": 6,
                "symbol": "ALGO",
                "explorer": "https://algoexplorer.io"
            },
            "avalanche": {
                "name": "Avalanche C-Chain",
                "alchemy_url": f"https://avax-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
                "decimals": 18,
                "symbol": "AVAX",
                "explorer": "https://snowtrace.io"
            },
            "optimism": {
                "name": "Optimism",
                "alchemy_url": f"https://opt-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
                "decimals": 18,
                "symbol": "ETH",
                "explorer": "https://optimistic.etherscan.io"
            },
            "base": {
                "name": "Base",
                "alchemy_url": f"https://base-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
                "decimals": 18,
                "symbol": "ETH",
                "explorer": "https://basescan.org"
            },
            "fantom": {
                "name": "Fantom",
                "alchemy_url": f"https://fantom-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
                "decimals": 18,
                "symbol": "FTM",
                "explorer": "https://ftmscan.com"
            },
            "dogecoin": {
                "name": "Dogecoin",
                "api_url": "https://dogechain.info/api/v1",
                "decimals": 8,
                "symbol": "DOGE",
                "explorer": "https://dogechain.info"
            },
            "xrp": {
                "name": "XRP/Ripple",
                "api_url": "https://xrplcluster.com",
                "decimals": 6,
                "symbol": "XRP",
                "explorer": "https://xrpscan.com"
            },
            "xlm": {
                "name": "Stellar/XLM",
                "api_url": "https://horizon.stellar.org",
                "decimals": 7,
                "symbol": "XLM",
                "explorer": "https://stellarchain.io"
            }
        }
    
    def wei_to_native(self, value: str, decimals: int = 18) -> float:
        """Convert smallest unit to native token"""
        try:
            return float(Decimal(str(int(value, 16))) / Decimal(10**decimals))
        except:
            return 0.0
    
    def safe_parse_block_num(self, block_num: str) -> int:
        """Safely parse block number that could be hex or decimal"""
        try:
            if block_num == 'pending' or not block_num:
                return float('inf')
            
            # Try hex first (if starts with 0x)
            if isinstance(block_num, str) and block_num.startswith('0x'):
                return int(block_num, 16)
            
            # Try decimal
            return int(block_num)
        except (ValueError, TypeError):
            return float('inf')
    
    def satoshi_to_btc(self, satoshi: int) -> float:
        """Convert Satoshi to BTC"""
        return float(Decimal(satoshi) / Decimal(10**8))
    
    def add_usd_values(self, analysis: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """Add USD values to analysis data"""
        try:
            # Get current price
            current_price = price_service.get_current_price(symbol)
            logger.info(f"Price for {symbol}: {current_price}")
            
            if current_price:
                analysis['current_price_usd'] = current_price
                analysis['total_value_usd'] = analysis.get('currentBalance', analysis.get('netEth', 0)) * current_price
                analysis['net_balance_usd'] = analysis.get('currentBalance', analysis.get('netEth', 0)) * current_price
                analysis['total_received_usd'] = analysis.get('totalEthReceived', 0) * current_price
                analysis['total_sent_usd'] = analysis.get('totalEthSent', 0) * current_price
                analysis['total_gas_fees_usd'] = analysis.get('totalGasFees', 0) * current_price
            
            # Add USD value to each transaction - ONLY for native token
            for tx in analysis.get('recentTransactions', []):
                tx_asset = (tx.get('asset') or symbol).upper()
                is_native = tx_asset == symbol.upper()
                
                if is_native and current_price:
                    # Native token (ETH, SOL, etc.) - use chain's price
                    tx['value_usd'] = float(tx.get('value', 0)) * current_price
                else:
                    # ERC-20/SPL token - look up specific price or set to 0
                    token_price = price_service.get_current_price(tx_asset)
                    if token_price:
                        tx['value_usd'] = float(tx.get('value', 0)) * token_price
                    else:
                        tx['value_usd'] = 0  # Unknown token - don't assign native chain price!
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error adding USD values: {str(e)}")
            return analysis
    
    def add_tax_data(self, analysis: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """Add tax calculations including cost basis and capital gains using historical prices"""
        try:
            current_price = analysis.get('current_price_usd')
            current_balance = analysis.get('currentBalance', analysis.get('netEth', 0))
            transactions = analysis.get('recentTransactions', [])
            
            if not current_price or not transactions:
                return analysis
            
            # Use the new historical tax enrichment service for accurate cost basis
            try:
                from historical_tax_enrichment import historical_tax_enrichment
                
                tax_data = historical_tax_enrichment.calculate_on_chain_tax_data(
                    transactions=transactions,
                    symbol=symbol,
                    current_price=current_price,
                    current_balance=current_balance
                )
                
                logger.info(f"Tax data calculated with historical prices: "
                           f"{tax_data.get('sources', {}).get('historical_prices_used', 0)} historical, "
                           f"{tax_data.get('sources', {}).get('current_prices_used', 0)} current")
                
            except ImportError:
                # Fallback to old tax service if historical enrichment not available
                logger.warning("Historical tax enrichment not available, using fallback")
                tax_data = tax_service.calculate_tax_data(
                    transactions=transactions,
                    current_balance=current_balance,
                    current_price=current_price,
                    symbol=symbol
                )
            
            # Add to analysis
            analysis['tax_data'] = tax_data
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error adding tax data: {str(e)}")
            return analysis
    
    def _detect_exchange_deposit_address(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect if a wallet is an exchange deposit address (e.g., Coinbase).
        Exchange deposit addresses: receive funds then immediately sweep to main wallet.
        """
        txs = analysis.get('recentTransactions', [])
        balance = analysis.get('currentBalance', 0) or 0
        total_in = analysis.get('totalEthReceived', 0) or 0
        total_out = analysis.get('totalEthSent', 0) or 0
        
        if not txs or len(txs) < 2 or total_in == 0:
            return analysis
        
        receives = [t for t in txs if t.get('type') in ['received', 'receive']]
        sends = [t for t in txs if t.get('type') in ['sent', 'send']]
        
        if not receives or not sends:
            return analysis
        
        # Check: every send happens shortly after a receive (within 30 min)
        sweep_sends = 0
        for send in sends:
            send_time = send.get('blockTime', 0) or 0
            for recv in receives:
                recv_time = recv.get('blockTime', 0) or 0
                if 0 < (send_time - recv_time) < 1800:  # Send within 30 min after receive
                    sweep_sends += 1
                    break
        
        # Heuristic: exchange deposit if balance ~0 and total in ≈ total out
        is_exchange_deposit = (
            balance < 0.01 and
            abs(total_in - total_out) / total_in < 0.02 and
            sweep_sends >= len(sends) * 0.5 and
            len(sends) >= 1
        )
        
        if is_exchange_deposit:
            analysis['exchange_deposit_warning'] = {
                'detected': True,
                'message': 'This appears to be an exchange deposit address (e.g., Coinbase). Exchanges sweep deposited funds to their main wallets immediately, so the on-chain balance shows $0. Your actual balance is held by the exchange internally.',
                'suggestion': 'To see your real holdings and calculate accurate tax gains, use one of these methods:',
                'options': [
                    'Connect your exchange via API key (Settings > Exchange Connections)',
                    'Import your exchange transaction history CSV (Download from your exchange, then upload here)'
                ]
            }
        
        return analysis

    def analyze_wallet(
        self,
        address: str,
        chain: str = "ethereum",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_tier: str = 'free'
    ) -> Dict[str, Any]:
        """Analyze wallet across different chains"""
        
        if chain not in self.chains:
            raise ValueError(f"Unsupported chain: {chain}. Supported chains: {', '.join(self.chains.keys())}")
        
        # Provide helpful error if wrong chain selected for address type
        if chain in ["ethereum", "polygon", "arbitrum", "bsc"]:
            if not address.startswith('0x'):
                raise ValueError(f"This appears to be a non-EVM address. For {chain}, use an address starting with 0x. Try selecting Bitcoin, Solana, or Algorand instead.")
        elif chain == "bitcoin":
            if address.startswith('0x'):
                raise ValueError(f"This appears to be an EVM address (starts with 0x). Try selecting Ethereum, Polygon, Arbitrum, or BSC instead.")
        elif chain == "solana":
            if address.startswith('0x'):
                raise ValueError(f"This appears to be an EVM address (starts with 0x). Try selecting Ethereum, Polygon, Arbitrum, or BSC instead.")
        elif chain == "algorand":
            if address.startswith('0x'):
                raise ValueError(f"This appears to be an EVM address (starts with 0x). Algorand addresses are 58-character base32 strings.")
            if len(address) != 58:
                raise ValueError(f"Invalid Algorand address. Expected 58 characters, got {len(address)}.")
        
        # Get analysis data
        if chain == "bitcoin":
            analysis = self._analyze_bitcoin_wallet(address, start_date, end_date, user_tier)
            symbol = 'BTC'
        elif chain == "solana":
            analysis = self._analyze_solana_wallet(address, start_date, end_date)
            symbol = 'SOL'
        elif chain == "algorand":
            analysis = self._analyze_algorand_wallet(address, start_date, end_date)
            symbol = 'ALGO'
        elif chain == "dogecoin":
            analysis = self._analyze_dogecoin_wallet(address, start_date, end_date)
            symbol = 'DOGE'
        elif chain == "xrp":
            analysis = self._analyze_xrp_wallet(address, start_date, end_date)
            symbol = 'XRP'
        elif chain == "xlm":
            analysis = self._analyze_xlm_wallet(address, start_date, end_date)
            symbol = 'XLM'
        else:
            # EVM chains (ethereum, polygon, arbitrum, bsc)
            analysis = self._analyze_evm_wallet(address, chain, start_date, end_date)
            symbol = 'ETH' if chain == 'ethereum' else 'MATIC' if chain == 'polygon' else 'BNB' if chain == 'bsc' else 'ETH'
        
        # Add USD values
        analysis = self.add_usd_values(analysis, symbol)
        
        # Detect exchange deposit address pattern
        analysis = self._detect_exchange_deposit_address(analysis)
        
        # Add tax calculations (Unlimited/Premium/Pro feature)
        if user_tier in ['premium', 'pro', 'unlimited']:
            analysis = self.add_tax_data(analysis, symbol)
        
        return analysis
    
    def _analyze_evm_wallet(
        self,
        address: str,
        chain: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze EVM-compatible wallet using Alchemy"""
        try:
            chain_config = self.chains[chain]
            alchemy_url = chain_config["alchemy_url"]
            symbol = chain_config["symbol"]
            
            address = address.lower()
            
            # BSC has different API parameter support
            is_bsc = chain == 'bsc'
            
            # Get outgoing transactions
            out_params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "fromAddress": address,
                "category": ["external"] if is_bsc else ["external", "internal", "erc20"],
                "maxCount": "0x3e8"
            }
            if not is_bsc:
                out_params["withMetadata"] = True
                out_params["excludeZeroValue"] = False
                
            payload_out = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [out_params]
            }
            
            # Get incoming transactions
            in_params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": address,
                "category": ["external"] if is_bsc else ["external", "internal", "erc20"],
                "maxCount": "0x3e8"
            }
            if not is_bsc:
                in_params["withMetadata"] = True
                in_params["excludeZeroValue"] = False
                
            payload_in = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "alchemy_getAssetTransfers",
                "params": [in_params]
            }
            
            response_out = requests.post(alchemy_url, json=payload_out, timeout=30)
            response_out.raise_for_status()
            out_result = response_out.json().get('result')
            outgoing_txs = out_result.get('transfers', []) if out_result else []
            
            # Paginate outgoing transfers for large wallets
            page_key = out_result.get('pageKey') if out_result else None
            max_pages = 5
            page = 0
            while page_key and page < max_pages:
                page += 1
                page_params = dict(out_params)
                page_params['pageKey'] = page_key
                page_payload = {"jsonrpc": "2.0", "id": 1, "method": "alchemy_getAssetTransfers", "params": [page_params]}
                try:
                    resp = requests.post(alchemy_url, json=page_payload, timeout=30)
                    r = resp.json().get('result', {})
                    outgoing_txs.extend(r.get('transfers', []))
                    page_key = r.get('pageKey')
                except Exception:
                    break
            
            response_in = requests.post(alchemy_url, json=payload_in, timeout=30)
            response_in.raise_for_status()
            in_result = response_in.json().get('result')
            incoming_txs = in_result.get('transfers', []) if in_result else []
            
            # Paginate incoming transfers
            page_key = in_result.get('pageKey') if in_result else None
            page = 0
            while page_key and page < max_pages:
                page += 1
                page_params = dict(in_params)
                page_params['pageKey'] = page_key
                page_payload = {"jsonrpc": "2.0", "id": 2, "method": "alchemy_getAssetTransfers", "params": [page_params]}
                try:
                    resp = requests.post(alchemy_url, json=page_payload, timeout=30)
                    r = resp.json().get('result', {})
                    incoming_txs.extend(r.get('transfers', []))
                    page_key = r.get('pageKey')
                except Exception:
                    break
            
            logger.info(f"EVM analysis: {len(outgoing_txs)} outgoing, {len(incoming_txs)} incoming transfers")
            
            # Get CURRENT BALANCE from blockchain
            balance_payload = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "eth_getBalance",
                "params": [address, "latest"]
            }
            balance_response = requests.post(alchemy_url, json=balance_payload, timeout=30)
            balance_response.raise_for_status()
            current_balance_hex = balance_response.json().get('result', '0x0')
            current_balance_wei = int(current_balance_hex, 16)
            current_balance = current_balance_wei / 1e18
            
            # Calculate statistics
            total_sent = 0.0
            total_received = 0.0
            total_gas = 0.0
            tokens_sent = {}
            tokens_received = {}
            
            # BATCH gas fee calculation (instead of 100 individual calls)
            native_out_hashes = [tx.get('hash') for tx in outgoing_txs if tx.get('hash') and tx.get('asset') == symbol]
            sample_hashes = native_out_hashes[:20]
            if sample_hashes:
                batch_payload = [
                    {"jsonrpc": "2.0", "id": i, "method": "eth_getTransactionReceipt", "params": [h]}
                    for i, h in enumerate(sample_hashes)
                ]
                try:
                    batch_resp = requests.post(alchemy_url, json=batch_payload, timeout=30)
                    results = batch_resp.json() if batch_resp.status_code == 200 else []
                    sampled_gas = 0.0
                    sampled_count = 0
                    for r in results:
                        receipt = r.get('result', {})
                        if receipt:
                            gas_used = int(receipt.get('gasUsed', '0x0'), 16)
                            gas_price = int(receipt.get('effectiveGasPrice', '0x0'), 16)
                            sampled_gas += (gas_used * gas_price) / 1e18
                            sampled_count += 1
                    if sampled_count > 0:
                        avg_gas = sampled_gas / sampled_count
                        total_gas = avg_gas * len(native_out_hashes)
                except Exception as e:
                    logger.warning(f"Batch gas fee error: {e}")
            
            # Process outgoing
            for tx in outgoing_txs:
                value = tx.get('value')
                if value is None:
                    continue
                if tx.get('asset') == symbol:
                    total_sent += float(value)
                else:
                    token = tx.get('asset', 'UNKNOWN')
                    tokens_sent[token] = tokens_sent.get(token, 0) + float(value)
            
            # Process incoming
            for tx in incoming_txs:
                value = tx.get('value')
                if value is None:
                    continue
                if tx.get('asset') == symbol:
                    total_received += float(value)
                else:
                    token = tx.get('asset', 'UNKNOWN')
                    tokens_received[token] = tokens_received.get(token, 0) + float(value)
            
            # Build ALL transactions for tax calculations
            all_txs = []
            for tx in outgoing_txs:
                value = tx.get('value', 0)
                metadata = tx.get('metadata') or {}
                to_label = metadata.get('exchangeName') or metadata.get('contractName')
                
                block_timestamp = metadata.get('blockTimestamp', '')
                timestamp = None
                if block_timestamp:
                    try:
                        dt = datetime.fromisoformat(block_timestamp.replace('Z', '+00:00'))
                        timestamp = int(dt.timestamp())
                    except Exception:
                        pass
                
                all_txs.append({
                    "hash": tx.get('hash', ''),
                    "type": "sent",
                    "value": float(value) if value is not None else 0.0,
                    "asset": tx.get('asset', symbol),
                    "to": tx.get('to', ''),
                    "to_label": to_label,
                    "blockNum": tx.get('blockNum', ''),
                    "blockTime": timestamp,
                    "timestamp": timestamp,
                    "category": tx.get('category', '')
                })
            
            for tx in incoming_txs:
                value = tx.get('value', 0)
                metadata = tx.get('metadata') or {}
                from_label = metadata.get('exchangeName') or metadata.get('contractName')
                
                block_timestamp = metadata.get('blockTimestamp', '')
                timestamp = None
                if block_timestamp:
                    try:
                        dt = datetime.fromisoformat(block_timestamp.replace('Z', '+00:00'))
                        timestamp = int(dt.timestamp())
                    except Exception:
                        pass
                
                all_txs.append({
                    "hash": tx.get('hash', ''),
                    "type": "received",
                    "value": float(value) if value is not None else 0.0,
                    "asset": tx.get('asset', symbol),
                    "from": tx.get('from', ''),
                    "from_label": from_label,
                    "blockNum": tx.get('blockNum', ''),
                    "blockTime": timestamp,
                    "timestamp": timestamp,
                    "category": tx.get('category', '')
                })
            
            # Sort ALL by block number, newest first
            recent_transactions = sorted(all_txs, key=lambda x: self.safe_parse_block_num(x['blockNum']), reverse=True)
            
            return {
                'address': address,
                'chain': chain,
                'totalEthSent': total_sent,
                'totalEthReceived': total_received,
                'totalGasFees': total_gas,
                'currentBalance': current_balance,
                'netEth': current_balance,  # Keep for backward compatibility
                'netFlow': total_received - total_sent - total_gas,  # This can be negative
                'outgoingTransactionCount': len(outgoing_txs),
                'incomingTransactionCount': len(incoming_txs),
                'tokensSent': tokens_sent,
                'tokensReceived': tokens_received,
                'recentTransactions': recent_transactions
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {chain} wallet: {str(e)}")
            raise Exception(f"Failed to analyze {chain} wallet: {str(e)}")
    
    def _analyze_bitcoin_xpub(
        self,
        xpub: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Bitcoin HD wallet using xPub/yPub/zPub"""
        try:
            from bip32 import BIP32
            import hashlib
            
            # Determine address type from xpub prefix
            if xpub.startswith('xpub'):
                # BIP44 - Legacy P2PKH
                address_type = 'legacy'
            elif xpub.startswith('ypub'):
                # BIP49 - P2SH-P2WPKH (SegWit wrapped)
                address_type = 'p2sh-segwit'
            elif xpub.startswith('zpub'):
                # BIP84 - Native SegWit (Bech32)
                address_type = 'native-segwit'
            else:
                raise ValueError("Unsupported xPub format. Use xpub/ypub/zpub")
            
            # Initialize BIP32 with xpub
            bip32 = BIP32.from_xpub(xpub)
            
            # Derive addresses (checking both external and internal chains)
            gap_limit = 20  # Standard gap limit
            addresses_to_check = []
            
            # External chain (receiving addresses) - m/0/*
            for i in range(gap_limit):
                child = bip32.get_pubkey_from_path(f"m/0/{i}")
                address = self._pubkey_to_address(child, address_type)
                addresses_to_check.append({
                    'address': address,
                    'path': f"m/0/{i}",
                    'type': 'external'
                })
            
            # Internal chain (change addresses) - m/1/*
            for i in range(gap_limit):
                child = bip32.get_pubkey_from_path(f"m/1/{i}")
                address = self._pubkey_to_address(child, address_type)
                addresses_to_check.append({
                    'address': address,
                    'path': f"m/1/{i}",
                    'type': 'internal'
                })
            
            # Check balance for each derived address
            total_received = 0.0
            total_sent = 0.0
            total_balance = 0.0
            all_transactions = []
            active_addresses = []
            
            logger.info(f"Checking {len(addresses_to_check)} derived addresses from xPub...")
            
            for addr_info in addresses_to_check:
                try:
                    # Use Blockstream API (supports all address types)
                    url = f"https://blockstream.info/api/address/{addr_info['address']}"
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    data = response.json()
                    
                    chain_stats = data.get('chain_stats', {})
                    funded_sum = chain_stats.get('funded_txo_sum', 0)
                    spent_sum = chain_stats.get('spent_txo_sum', 0)
                    
                    if funded_sum > 0 or spent_sum > 0:
                        # This address has activity
                        addr_received = self.satoshi_to_btc(funded_sum)
                        addr_sent = self.satoshi_to_btc(spent_sum)
                        addr_balance = addr_received - addr_sent
                        
                        total_received += addr_received
                        total_sent += addr_sent
                        total_balance += addr_balance
                        
                        active_addresses.append({
                            'address': addr_info['address'],
                            'path': addr_info['path'],
                            'type': addr_info['type'],
                            'received': addr_received,
                            'sent': addr_sent,
                            'balance': addr_balance,
                            'tx_count': chain_stats.get('tx_count', 0)
                        })
                        
                        # Fetch recent transactions for this address
                        txs_url = f"https://blockstream.info/api/address/{addr_info['address']}/txs"
                        txs_response = requests.get(txs_url, timeout=10)
                        if txs_response.status_code == 200:
                            txs = txs_response.json()[:5]  # Get 5 most recent per address
                            for tx in txs:
                                all_transactions.append({
                                    "hash": tx.get('txid', ''),
                                    "address": addr_info['address'],
                                    "path": addr_info['path'],
                                    "blockNum": str(tx.get('status', {}).get('block_height', 'pending')),
                                    "asset": "BTC"
                                })
                        
                        logger.info(f"Found activity on {addr_info['path']}: {addr_balance} BTC")
                    
                    # Small delay to avoid rate limiting
                    import time
                    time.sleep(0.1)
                    
                except Exception as e:
                    logger.warning(f"Error checking {addr_info['address']}: {str(e)}")
                    continue
            
            # Sort transactions by block number
            all_transactions.sort(key=lambda x: self.safe_parse_block_num(x['blockNum']), reverse=True)
            
            return {
                'address': xpub[:20] + '...' + xpub[-10:],  # Shortened xPub display
                'xpub': xpub,
                'address_type': address_type,
                'chain': 'bitcoin',
                'totalEthSent': total_sent,
                'totalEthReceived': total_received,
                'totalGasFees': 0.0,
                'netEth': total_balance,
                'outgoingTransactionCount': sum(a['tx_count'] for a in active_addresses),
                'incomingTransactionCount': sum(a['tx_count'] for a in active_addresses),
                'tokensSent': {},
                'tokensReceived': {},
                'recentTransactions': all_transactions[:20],
                'active_addresses': active_addresses,
                'total_addresses_checked': len(addresses_to_check),
                'addresses_with_activity': len(active_addresses)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing Bitcoin xPub: {str(e)}")
            raise Exception(f"Failed to analyze Bitcoin xPub: {str(e)}")
    
    def _pubkey_to_address(self, pubkey: bytes, address_type: str) -> str:
        """Convert public key to Bitcoin address based on type"""
        import hashlib
        
        if address_type == 'native-segwit':
            # Bech32 (bc1q...)
            from bech32 import bech32_encode, convertbits
            
            # SHA256 then RIPEMD160
            sha = hashlib.sha256(pubkey).digest()
            ripe = hashlib.new('ripemd160', sha).digest()
            
            # Convert to 5-bit groups for bech32
            five_bit = convertbits(ripe, 8, 5)
            # Witness version 0 for P2WPKH
            return bech32_encode('bc', [0] + five_bit)
        
        elif address_type == 'legacy':
            # Legacy P2PKH (1...)
            import base58
            
            # SHA256 then RIPEMD160
            sha = hashlib.sha256(pubkey).digest()
            ripe = hashlib.new('ripemd160', sha).digest()
            
            # Add version byte (0x00 for mainnet)
            versioned = b'\x00' + ripe
            
            # Double SHA256 for checksum
            checksum = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
            
            # Encode with base58
            return base58.b58encode(versioned + checksum).decode()
        
        else:
            raise ValueError(f"Unsupported address type: {address_type}")
    
    def _analyze_bitcoin_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_tier: str = 'free'
    ) -> Dict[str, Any]:
        """Analyze Bitcoin wallet using blockchain.info API"""
        try:
            # Check if input is an xPub instead of regular address
            if address.startswith(('xpub', 'ypub', 'zpub')):
                # xPub analysis is Pro-only
                if user_tier != 'pro':
                    raise Exception("xPub analysis is a Pro-only feature. Upgrade to Pro to analyze Ledger/HD wallets using xPub.")
                return self._analyze_bitcoin_xpub(address, start_date, end_date)
            
            url = f"https://blockchain.info/rawaddr/{address}?limit=50"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            total_received = self.satoshi_to_btc(data.get('total_received', 0))
            total_sent = self.satoshi_to_btc(data.get('total_sent', 0))
            final_balance = self.satoshi_to_btc(data.get('final_balance', 0))
            n_tx = data.get('n_tx', 0)
            
            txs = data.get('txs', [])
            recent_transactions = []
            
            for tx in txs[:10]:
                # Calculate transaction value for this address
                tx_value = abs(tx.get('result', 0))
                is_sender = tx.get('result', 0) < 0
                
                recent_transactions.append({
                    "hash": tx.get('hash', ''),
                    "type": "sent" if is_sender else "received",
                    "value": self.satoshi_to_btc(abs(tx_value)),
                    "asset": "BTC",
                    "blockNum": str(tx.get('block_height', 'pending')),
                    "category": "external"
                })
            
            return {
                'address': address,
                'chain': 'bitcoin',
                'totalEthSent': total_sent,
                'totalEthReceived': total_received,
                'totalGasFees': 0.0,
                'currentBalance': final_balance,
                'netEth': final_balance,  # Current balance (not net flow)
                'netFlow': total_received - total_sent,
                'outgoingTransactionCount': n_tx,
                'incomingTransactionCount': n_tx,
                'tokensSent': {},
                'tokensReceived': {},
                'recentTransactions': recent_transactions
            }
            
        except Exception as e:
            logger.error(f"Error analyzing Bitcoin wallet: {str(e)}")
            raise Exception(f"Failed to analyze Bitcoin wallet: {str(e)}")
    
    def _analyze_solana_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Solana wallet using the dedicated Solana analyzer"""
        try:
            from chains.solana import create_solana_analyzer
            
            analyzer = create_solana_analyzer()
            result = analyzer.analyze_wallet(address, start_date, end_date)
            
            # Result is already in the correct format from format_analysis_result
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing Solana wallet: {str(e)}")
            raise Exception(f"Failed to analyze Solana wallet: {str(e)}")
    
    def _analyze_algorand_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Algorand wallet using the dedicated Algorand analyzer"""
        try:
            from chains.algorand import create_algorand_analyzer
            
            analyzer = create_algorand_analyzer()
            result = analyzer.analyze_wallet(address, start_date, end_date)
            
            # Result is already in the correct format from format_analysis_result
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing Algorand wallet: {str(e)}")
            raise Exception(f"Failed to analyze Algorand wallet: {str(e)}")
    
    def _analyze_dogecoin_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Dogecoin wallet using the dedicated Dogecoin analyzer"""
        try:
            from chains.dogecoin import create_dogecoin_analyzer
            
            analyzer = create_dogecoin_analyzer()
            result = analyzer.analyze_wallet(address, start_date, end_date)
            
            # Result is already in the correct format from format_analysis_result
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing Dogecoin wallet: {str(e)}")
            raise Exception(f"Failed to analyze Dogecoin wallet: {str(e)}")

    def _analyze_xrp_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze XRP wallet using the dedicated XRP analyzer"""
        try:
            from chains.xrp import create_xrp_analyzer
            
            analyzer = create_xrp_analyzer()
            result = analyzer.analyze_wallet(address, start_date, end_date)
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing XRP wallet: {str(e)}")
            raise Exception(f"Failed to analyze XRP wallet: {str(e)}")
    
    def _analyze_xlm_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Stellar/XLM wallet using the dedicated Stellar analyzer"""
        try:
            from chains.stellar import create_stellar_analyzer
            
            analyzer = create_stellar_analyzer()
            result = analyzer.analyze_wallet(address, start_date, end_date)
            
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing Stellar wallet: {str(e)}")
            raise Exception(f"Failed to analyze Stellar wallet: {str(e)}")

    
    def get_supported_chains(self) -> List[Dict[str, str]]:
        """Get list of supported chains"""
        return [
            {
                "id": chain_id,
                "name": config["name"],
                "symbol": config["symbol"],
                "explorer": config["explorer"]
            }
            for chain_id, config in self.chains.items()
        ]
