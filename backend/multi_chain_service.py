import os
import requests
from typing import Dict, List, Any, Optional
from decimal import Decimal
import logging
from price_service import price_service

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
            }
        }
    
    def wei_to_native(self, value: str, decimals: int = 18) -> float:
        """Convert smallest unit to native token"""
        try:
            return float(Decimal(str(int(value, 16))) / Decimal(10**decimals))
        except:
            return 0.0
    
    def satoshi_to_btc(self, satoshi: int) -> float:
        """Convert Satoshi to BTC"""
        return float(Decimal(satoshi) / Decimal(10**8))
    
    def add_usd_values(self, analysis: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """Add USD values to analysis data"""
        try:
            # Get current price
            current_price = price_service.get_current_price(symbol)
            
            if current_price:
                analysis['current_price_usd'] = current_price
                analysis['total_value_usd'] = analysis.get('netEth', 0) * current_price
                analysis['net_balance_usd'] = analysis.get('netEth', 0) * current_price
                analysis['total_received_usd'] = analysis.get('totalEthReceived', 0) * current_price
                analysis['total_sent_usd'] = analysis.get('totalEthSent', 0) * current_price
                analysis['gas_fees_usd'] = analysis.get('totalGasFees', 0) * current_price
            
            # Add USD value to each transaction (if we have timestamp)
            for tx in analysis.get('recentTransactions', []):
                if current_price:
                    tx['value_usd'] = float(tx.get('value', 0)) * current_price
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error adding USD values: {str(e)}")
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
                raise ValueError(f"This appears to be a non-EVM address. For {chain}, use an address starting with 0x. Try selecting Bitcoin or Solana instead.")
        elif chain == "bitcoin":
            if address.startswith('0x'):
                raise ValueError(f"This appears to be an EVM address (starts with 0x). Try selecting Ethereum, Polygon, Arbitrum, or BSC instead.")
        elif chain == "solana":
            if address.startswith('0x'):
                raise ValueError(f"This appears to be an EVM address (starts with 0x). Try selecting Ethereum, Polygon, Arbitrum, or BSC instead.")
        
        # Get analysis data
        if chain == "bitcoin":
            analysis = self._analyze_bitcoin_wallet(address, start_date, end_date, user_tier)
            symbol = 'BTC'
        elif chain == "solana":
            analysis = self._analyze_solana_wallet(address, start_date, end_date)
            symbol = 'SOL'
        else:
            # EVM chains (ethereum, polygon, arbitrum, bsc)
            analysis = self._analyze_evm_wallet(address, chain, start_date, end_date)
            symbol = 'ETH' if chain == 'ethereum' else 'MATIC' if chain == 'polygon' else 'BNB' if chain == 'bsc' else 'ETH'
        
        # Add USD values
        analysis = self.add_usd_values(analysis, symbol)
        
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
            
            # Get outgoing transactions
            payload_out = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [{
                    "fromBlock": "0x0",
                    "toBlock": "latest",
                    "fromAddress": address,
                    "category": ["external", "internal", "erc20"],
                    "withMetadata": True,
                    "excludeZeroValue": False,
                    "maxCount": "0x3e8"
                }]
            }
            
            # Get incoming transactions
            payload_in = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "alchemy_getAssetTransfers",
                "params": [{
                    "fromBlock": "0x0",
                    "toBlock": "latest",
                    "toAddress": address,
                    "category": ["external", "internal", "erc20"],
                    "withMetadata": True,
                    "excludeZeroValue": False,
                    "maxCount": "0x3e8"
                }]
            }
            
            response_out = requests.post(alchemy_url, json=payload_out, timeout=30)
            response_out.raise_for_status()
            outgoing_txs = response_out.json().get('result', {}).get('transfers', [])
            
            response_in = requests.post(alchemy_url, json=payload_in, timeout=30)
            response_in.raise_for_status()
            incoming_txs = response_in.json().get('result', {}).get('transfers', [])
            
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
            current_balance = current_balance_wei / 1e18  # Convert wei to ETH
            
            # Calculate statistics
            total_sent = 0.0
            total_received = 0.0
            total_gas = 0.0
            tokens_sent = {}
            tokens_received = {}
            recent_transactions = []
            
            # Get transaction receipts for gas fees (only for sent transactions)
            for tx in outgoing_txs[:100]:  # Limit to first 100 to avoid rate limits
                tx_hash = tx.get('hash')
                if tx_hash and tx.get('asset') == symbol:
                    try:
                        receipt_payload = {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "eth_getTransactionReceipt",
                            "params": [tx_hash]
                        }
                        receipt_response = requests.post(alchemy_url, json=receipt_payload, timeout=10)
                        receipt_data = receipt_response.json().get('result', {})
                        
                        if receipt_data:
                            gas_used = int(receipt_data.get('gasUsed', '0x0'), 16)
                            effective_gas_price = int(receipt_data.get('effectiveGasPrice', '0x0'), 16)
                            gas_cost_wei = gas_used * effective_gas_price
                            gas_cost_eth = gas_cost_wei / 10**18
                            total_gas += gas_cost_eth
                    except:
                        pass  # Skip if can't get receipt
            
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
            
            # Get recent transactions (last 10) with metadata
            all_txs = []
            for tx in outgoing_txs[:10]:
                value = tx.get('value', 0)
                to_address = tx.get('to', '')
                
                # Get metadata for the address (exchange, contract name, etc.)
                to_metadata = tx.get('metadata', {})
                to_label = to_metadata.get('exchangeName') or to_metadata.get('contractName') or None
                
                all_txs.append({
                    "hash": tx.get('hash', ''),
                    "type": "sent",
                    "value": float(value) if value is not None else 0.0,
                    "asset": tx.get('asset', symbol),
                    "to": to_address,
                    "to_label": to_label,
                    "blockNum": tx.get('blockNum', ''),
                    "category": tx.get('category', '')
                })
            
            for tx in incoming_txs[:10]:
                value = tx.get('value', 0)
                from_address = tx.get('from', '')
                
                # Get metadata for the address
                from_metadata = tx.get('metadata', {})
                from_label = from_metadata.get('exchangeName') or from_metadata.get('contractName') or None
                
                all_txs.append({
                    "hash": tx.get('hash', ''),
                    "type": "received",
                    "value": float(value) if value is not None else 0.0,
                    "asset": tx.get('asset', symbol),
                    "from": from_address,
                    "from_label": from_label,
                    "blockNum": tx.get('blockNum', ''),
                    "category": tx.get('category', '')
                })
            
            # Sort transactions by block number (oldest first for running balance calculation)
            all_transactions_sorted = sorted(all_txs, key=lambda x: int(x['blockNum']) if x['blockNum'] != 'pending' else float('inf'), reverse=False)
            
            # Calculate running balance for each transaction
            running_balance = current_balance
            for tx in reversed(all_transactions_sorted):  # Work backwards from most recent
                if tx['type'] == 'sent':
                    # Before this send, balance was higher
                    running_balance += float(tx['value']) + float(tx.get('gasFee', 0))
                else:
                    # Before this receive, balance was lower
                    running_balance -= float(tx['value'])
                tx['running_balance'] = running_balance
            
            # Now sort for display (newest first) and take top 10
            recent_transactions = sorted(all_transactions_sorted, key=lambda x: int(x['blockNum']) if x['blockNum'] != 'pending' else float('inf'), reverse=True)[:10]
            
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
            all_transactions.sort(key=lambda x: int(x['blockNum']) if x['blockNum'] != 'pending' else 0, reverse=True)
            
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
        """Analyze Solana wallet using Alchemy"""
        try:
            rpc_url = self.chains['solana']['alchemy_url']
            
            # Get balance
            balance_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [address]
            }
            
            balance_response = requests.post(rpc_url, json=balance_payload, timeout=30)
            balance_response.raise_for_status()
            balance_data = balance_response.json()
            balance_lamports = balance_data.get('result', {}).get('value', 0)
            balance_sol = balance_lamports / 10**9
            
            # Get recent signatures
            sig_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getSignaturesForAddress",
                "params": [address, {"limit": 10}]
            }
            
            sig_response = requests.post(rpc_url, json=sig_payload, timeout=30)
            sig_response.raise_for_status()
            sig_data = sig_response.json()
            signatures = sig_data.get('result', [])
            
            recent_transactions = []
            for sig in signatures:
                recent_transactions.append({
                    "hash": sig.get('signature', ''),
                    "type": "transaction",
                    "value": 0.0,  # Would need to parse tx details for exact amount
                    "asset": "SOL",
                    "blockNum": str(sig.get('slot', '')),
                    "category": "external"
                })
            
            return {
                'address': address,
                'chain': 'solana',
                'totalEthSent': 0.0,
                'totalEthReceived': balance_sol,
                'totalGasFees': 0.0,
                'netEth': balance_sol,
                'outgoingTransactionCount': len(signatures),
                'incomingTransactionCount': len(signatures),
                'tokensSent': {},
                'tokensReceived': {},
                'recentTransactions': recent_transactions
            }
            
        except Exception as e:
            logger.error(f"Error analyzing Solana wallet: {str(e)}")
            raise Exception(f"Failed to analyze Solana wallet: {str(e)}")
    
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
