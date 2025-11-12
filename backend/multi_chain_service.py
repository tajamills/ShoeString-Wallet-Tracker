import os
import requests
from typing import Dict, List, Any, Optional
from decimal import Decimal
import logging

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
    
    def analyze_wallet(
        self,
        address: str,
        chain: str = "ethereum",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze wallet across different chains"""
        
        if chain not in self.chains:
            raise ValueError(f"Unsupported chain: {chain}. Supported chains: {', '.join(self.chains.keys())}")
        
        if chain == "bitcoin":
            return self._analyze_bitcoin_wallet(address, start_date, end_date)
        elif chain == "solana":
            return self._analyze_solana_wallet(address, start_date, end_date)
        else:
            # EVM chains (Ethereum, Arbitrum, BSC) - use Alchemy
            return self._analyze_evm_wallet(address, chain, start_date, end_date)
    
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
            
            # Calculate statistics
            total_sent = 0.0
            total_received = 0.0
            total_gas = 0.0
            tokens_sent = {}
            tokens_received = {}
            recent_transactions = []
            
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
            
            # Get recent transactions (last 10)
            all_txs = []
            for tx in outgoing_txs[:10]:
                all_txs.append({
                    "hash": tx.get('hash', ''),
                    "type": "sent",
                    "value": float(tx.get('value', 0)),
                    "asset": tx.get('asset', symbol),
                    "to": tx.get('to', ''),
                    "blockNum": tx.get('blockNum', ''),
                    "category": tx.get('category', '')
                })
            
            for tx in incoming_txs[:10]:
                all_txs.append({
                    "hash": tx.get('hash', ''),
                    "type": "received",
                    "value": float(tx.get('value', 0)),
                    "asset": tx.get('asset', symbol),
                    "from": tx.get('from', ''),
                    "blockNum": tx.get('blockNum', ''),
                    "category": tx.get('category', '')
                })
            
            recent_transactions = sorted(all_txs, key=lambda x: x.get('blockNum', '0'), reverse=True)[:10]
            
            return {
                'address': address,
                'chain': chain,
                'totalEthSent': total_sent,
                'totalEthReceived': total_received,
                'totalGasFees': total_gas,
                'netEth': total_received - total_sent,
                'outgoingTransactionCount': len(outgoing_txs),
                'incomingTransactionCount': len(incoming_txs),
                'tokensSent': tokens_sent,
                'tokensReceived': tokens_received,
                'recentTransactions': recent_transactions
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {chain} wallet: {str(e)}")
            raise Exception(f"Failed to analyze {chain} wallet: {str(e)}")
    
    def _analyze_bitcoin_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Bitcoin wallet using blockchain.info API"""
        try:
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
                'netEth': final_balance,
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
