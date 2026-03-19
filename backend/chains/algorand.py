"""
Algorand Chain Analyzer
"""
import os
import requests
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone
from .base import BaseChainAnalyzer

logger = logging.getLogger(__name__)


class AlgorandAnalyzer(BaseChainAnalyzer):
    """Analyzer for Algorand blockchain"""
    
    # Public Algorand Indexer API endpoints
    INDEXER_URLS = [
        "https://mainnet-idx.algonode.cloud",
        "https://algoindexer.algoexplorerapi.io",
    ]
    
    # Node API for balance
    NODE_URLS = [
        "https://mainnet-api.algonode.cloud",
        "https://node.algoexplorerapi.io",
    ]
    
    def __init__(self):
        super().__init__({
            'chain_id': 'algorand',
            'name': 'Algorand',
            'symbol': 'ALGO',
            'decimals': 6,  # ALGO uses 6 decimals (microAlgos)
            'explorer': 'https://algoexplorer.io'
        })
        self.indexer_url = self.INDEXER_URLS[0]
        self.node_url = self.NODE_URLS[0]
    
    def validate_address(self, address: str) -> bool:
        """
        Validate Algorand address
        - 58 characters long
        - Base32 encoded
        - Starts with uppercase letter
        """
        if not address:
            return False
        
        # Algorand addresses are 58 chars, base32
        if len(address) != 58:
            return False
        
        # Should not start with 0x (that's EVM)
        if address.startswith('0x'):
            return False
        
        # Basic check: should be uppercase alphanumeric (base32)
        valid_chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
        return all(c in valid_chars for c in address.upper())
    
    def get_address_validation_error(self, address: str) -> Optional[str]:
        if address.startswith('0x'):
            return "This appears to be an EVM address (starts with 0x). Algorand addresses are 58-character base32 strings."
        if len(address) != 58:
            return f"Invalid Algorand address length. Expected 58 characters, got {len(address)}."
        if not self.validate_address(address):
            return "Invalid Algorand address format. Addresses should be base32 encoded (uppercase letters A-Z and digits 2-7)."
        return None
    
    def microalgos_to_algo(self, microalgos: int) -> float:
        """Convert microAlgos to ALGO"""
        return float(Decimal(microalgos) / Decimal(10**6))
    
    def analyze_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze Algorand wallet"""
        try:
            # Get account info (includes balance)
            account_info = self._get_account_info(address)
            balance = self.microalgos_to_algo(account_info.get('amount', 0))
            
            # Get transactions
            transactions, total_sent, total_received = self._get_transactions(
                address, start_date, end_date
            )
            
            return self.format_analysis_result(
                address=address,
                chain='algorand',
                total_sent=total_sent,
                total_received=total_received,
                current_balance=balance,
                gas_fees=0.0,  # ALGO fees are minimal
                outgoing_count=len([t for t in transactions if t['type'] == 'sent']),
                incoming_count=len([t for t in transactions if t['type'] == 'received']),
                recent_transactions=transactions[:50]
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Algorand wallet: {str(e)}")
            raise Exception(f"Failed to analyze Algorand wallet: {str(e)}")
    
    def _get_account_info(self, address: str) -> Dict:
        """Get account info including balance"""
        url = f"{self.node_url}/v2/accounts/{address}"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Algorand account info: {str(e)}")
            # Try backup URL
            try:
                backup_url = f"{self.NODE_URLS[1]}/v2/accounts/{address}"
                response = requests.get(backup_url, timeout=30)
                response.raise_for_status()
                return response.json()
            except:
                return {'amount': 0}
    
    def _get_transactions(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 500
    ) -> tuple:
        """Get transaction history for address"""
        transactions = []
        total_sent = 0.0
        total_received = 0.0
        
        # Build URL with params
        url = f"{self.indexer_url}/v2/accounts/{address}/transactions"
        params = {"limit": limit}
        
        # Add date filters if provided
        if start_date:
            try:
                dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                params['after-time'] = dt.isoformat()
            except:
                pass
        
        if end_date:
            try:
                dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                params['before-time'] = dt.isoformat()
            except:
                pass
        
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            for tx in data.get('transactions', []):
                parsed = self._parse_transaction(tx, address)
                if parsed:
                    transactions.append(parsed)
                    if parsed['type'] == 'sent':
                        total_sent += parsed['value']
                    else:
                        total_received += parsed['value']
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Algorand transactions: {str(e)}")
            # Try backup indexer
            try:
                backup_url = f"{self.INDEXER_URLS[1]}/v2/accounts/{address}/transactions"
                response = requests.get(backup_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                for tx in data.get('transactions', []):
                    parsed = self._parse_transaction(tx, address)
                    if parsed:
                        transactions.append(parsed)
                        if parsed['type'] == 'sent':
                            total_sent += parsed['value']
                        else:
                            total_received += parsed['value']
            except:
                pass
        
        # Sort by timestamp (newest first)
        transactions.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        return transactions, total_sent, total_received
    
    def _parse_transaction(self, tx: Dict, address: str) -> Optional[Dict]:
        """Parse an Algorand transaction"""
        try:
            tx_type = tx.get('tx-type')
            
            # Handle payment transactions (ALGO transfers)
            if tx_type == 'pay':
                payment = tx.get('payment-transaction', {})
                sender = tx.get('sender', '')
                receiver = payment.get('receiver', '')
                amount = self.microalgos_to_algo(payment.get('amount', 0))
                
                # Determine if sent or received
                if sender.upper() == address.upper():
                    tx_direction = 'sent'
                    counterparty = receiver
                elif receiver.upper() == address.upper():
                    tx_direction = 'received'
                    counterparty = sender
                else:
                    return None
                
                # Get timestamp
                round_time = tx.get('round-time', 0)
                
                return {
                    'hash': tx.get('id', ''),
                    'type': tx_direction,
                    'value': amount,
                    'value_usd': 0,  # Will be enriched later
                    'asset': 'ALGO',
                    'from': sender,
                    'to': receiver,
                    'blockNum': str(tx.get('confirmed-round', '')),
                    'timestamp': round_time,
                    'fee': self.microalgos_to_algo(tx.get('fee', 0)),
                    'note': tx.get('note', '')
                }
            
            # Handle asset transfers (ASA tokens)
            elif tx_type == 'axfer':
                asset_transfer = tx.get('asset-transfer-transaction', {})
                sender = tx.get('sender', '')
                receiver = asset_transfer.get('receiver', '')
                amount = asset_transfer.get('amount', 0)
                asset_id = asset_transfer.get('asset-id', 0)
                
                # Determine if sent or received
                if sender.upper() == address.upper():
                    tx_direction = 'sent'
                elif receiver.upper() == address.upper():
                    tx_direction = 'received'
                else:
                    return None
                
                round_time = tx.get('round-time', 0)
                
                return {
                    'hash': tx.get('id', ''),
                    'type': tx_direction,
                    'value': amount,  # Raw amount - would need asset decimals
                    'value_usd': 0,
                    'asset': f'ASA-{asset_id}',  # Algorand Standard Asset
                    'from': sender,
                    'to': receiver,
                    'blockNum': str(tx.get('confirmed-round', '')),
                    'timestamp': round_time,
                    'fee': self.microalgos_to_algo(tx.get('fee', 0)),
                    'note': tx.get('note', '')
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error parsing Algorand transaction: {str(e)}")
            return None


def create_algorand_analyzer():
    return AlgorandAnalyzer()
