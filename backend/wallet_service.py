import os
import requests
from typing import Dict, List, Any
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

class WalletService:
    def __init__(self):
        self.alchemy_api_key = os.environ.get('ALCHEMY_API_KEY')
        self.alchemy_url = f"https://eth-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}"
    
    def wei_to_eth(self, wei_value: str) -> float:
        """Convert Wei to ETH"""
        try:
            return float(Decimal(str(int(wei_value, 16))) / Decimal(10**18))
        except:
            return 0.0
    
    def get_transactions(self, address: str) -> List[Dict[str, Any]]:
        """Fetch all transactions for a wallet address using Alchemy API"""
        try:
            # Normalize address
            address = address.lower()
            
            # Get transaction history using Alchemy's enhanced API
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [
                    {
                        "fromBlock": "0x0",
                        "toBlock": "latest",
                        "fromAddress": address,
                        "category": ["external", "internal", "erc20", "erc721", "erc1155"],
                        "withMetadata": True,
                        "excludeZeroValue": False,
                        "maxCount": "0x3e8"  # 1000 transactions
                    }
                ]
            }
            
            response = requests.post(self.alchemy_url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            outgoing_txs = data.get('result', {}).get('transfers', [])
            
            # Get incoming transactions
            payload_incoming = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "alchemy_getAssetTransfers",
                "params": [
                    {
                        "fromBlock": "0x0",
                        "toBlock": "latest",
                        "toAddress": address,
                        "category": ["external", "internal", "erc20", "erc721", "erc1155"],
                        "withMetadata": True,
                        "excludeZeroValue": False,
                        "maxCount": "0x3e8"
                    }
                ]
            }
            
            response_incoming = requests.post(self.alchemy_url, json=payload_incoming, timeout=30)
            response_incoming.raise_for_status()
            data_incoming = response_incoming.json()
            
            incoming_txs = data_incoming.get('result', {}).get('transfers', [])
            
            return {
                'outgoing': outgoing_txs,
                'incoming': incoming_txs
            }
            
        except Exception as e:
            logger.error(f"Error fetching transactions: {str(e)}")
            raise Exception(f"Failed to fetch transactions: {str(e)}")
    
    def get_transaction_receipts(self, tx_hashes: List[str]) -> Dict[str, Any]:
        """Fetch transaction receipts to get gas fees"""
        receipts = {}
        
        for tx_hash in tx_hashes[:100]:  # Limit to 100 for performance
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "eth_getTransactionReceipt",
                    "params": [tx_hash]
                }
                
                response = requests.post(self.alchemy_url, json=payload, timeout=10)
                data = response.json()
                
                if 'result' in data and data['result']:
                    receipt = data['result']
                    gas_used = int(receipt.get('gasUsed', '0x0'), 16)
                    effective_gas_price = int(receipt.get('effectiveGasPrice', '0x0'), 16)
                    gas_fee_wei = gas_used * effective_gas_price
                    gas_fee_eth = gas_fee_wei / 10**18
                    
                    receipts[tx_hash] = {
                        'gasUsed': gas_used,
                        'effectiveGasPrice': effective_gas_price,
                        'gasFeeEth': gas_fee_eth
                    }
            except Exception as e:
                logger.warning(f"Error fetching receipt for {tx_hash}: {str(e)}")
                continue
        
        return receipts
    
    def analyze_wallet(self, address: str) -> Dict[str, Any]:
        """Analyze wallet and calculate statistics"""
        try:
            # Normalize address
            address = address.lower()
            
            # Fetch transactions
            transactions = self.get_transactions(address)
            outgoing = transactions['outgoing']
            incoming = transactions['incoming']
            
            # Initialize totals
            total_eth_sent = 0.0
            total_eth_received = 0.0
            total_gas_fees = 0.0
            
            # Track tokens
            tokens_sent = {}
            tokens_received = {}
            
            # Get unique transaction hashes for gas fee calculation
            tx_hashes = set()
            
            # Process outgoing transactions
            for tx in outgoing:
                category = tx.get('category', '')
                value = tx.get('value', 0)
                asset = tx.get('asset', 'ETH')
                tx_hash = tx.get('hash', '')
                
                if tx_hash:
                    tx_hashes.add(tx_hash)
                
                if category in ['external', 'internal'] and asset == 'ETH':
                    total_eth_sent += float(value)
                elif category in ['erc20']:
                    token_symbol = asset
                    if token_symbol not in tokens_sent:
                        tokens_sent[token_symbol] = 0.0
                    tokens_sent[token_symbol] += float(value)
            
            # Process incoming transactions
            for tx in incoming:
                category = tx.get('category', '')
                value = tx.get('value', 0)
                asset = tx.get('asset', 'ETH')
                
                if category in ['external', 'internal'] and asset == 'ETH':
                    total_eth_received += float(value)
                elif category in ['erc20']:
                    token_symbol = asset
                    if token_symbol not in tokens_received:
                        tokens_received[token_symbol] = 0.0
                    tokens_received[token_symbol] += float(value)
            
            # Get gas fees for outgoing transactions
            receipts = self.get_transaction_receipts(list(tx_hashes))
            total_gas_fees = sum(r['gasFeeEth'] for r in receipts.values())
            
            # Calculate net
            net_eth = total_eth_received - total_eth_sent - total_gas_fees
            
            return {
                'address': address,
                'totalEthSent': round(total_eth_sent, 6),
                'totalEthReceived': round(total_eth_received, 6),
                'totalGasFees': round(total_gas_fees, 6),
                'netEth': round(net_eth, 6),
                'outgoingTransactionCount': len(outgoing),
                'incomingTransactionCount': len(incoming),
                'tokensSent': tokens_sent,
                'tokensReceived': tokens_received,
                'recentTransactions': self._format_recent_transactions(outgoing[:20], incoming[:20])
            }
            
        except Exception as e:
            logger.error(f"Error analyzing wallet: {str(e)}")
            raise Exception(f"Failed to analyze wallet: {str(e)}")
    
    def _format_recent_transactions(self, outgoing: List, incoming: List) -> List[Dict]:
        """Format recent transactions for display"""
        formatted = []
        
        # Format outgoing
        for tx in outgoing[:10]:
            formatted.append({
                'hash': tx.get('hash', ''),
                'type': 'sent',
                'value': tx.get('value', 0),
                'asset': tx.get('asset', 'ETH'),
                'to': tx.get('to', ''),
                'blockNum': tx.get('blockNum', ''),
                'category': tx.get('category', '')
            })
        
        # Format incoming
        for tx in incoming[:10]:
            formatted.append({
                'hash': tx.get('hash', ''),
                'type': 'received',
                'value': tx.get('value', 0),
                'asset': tx.get('asset', 'ETH'),
                'from': tx.get('from', ''),
                'blockNum': tx.get('blockNum', ''),
                'category': tx.get('category', '')
            })
        
        # Sort by block number (most recent first)
        formatted.sort(key=lambda x: int(x.get('blockNum', '0'), 16) if x.get('blockNum', '').startswith('0x') else int(x.get('blockNum', '0')), reverse=True)
        
        return formatted[:20]
