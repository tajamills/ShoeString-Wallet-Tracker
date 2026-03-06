"""
Dogecoin Chain Analyzer
"""
import requests
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from datetime import datetime, timezone
from .base import BaseChainAnalyzer

logger = logging.getLogger(__name__)


class DogecoinAnalyzer(BaseChainAnalyzer):
    """Analyzer for Dogecoin blockchain"""
    
    # Public Dogecoin API endpoints
    API_URLS = [
        "https://dogechain.info/api/v1",
        "https://api.blockcypher.com/v1/doge/main",
    ]
    
    def __init__(self):
        super().__init__({
            'chain_id': 'dogecoin',
            'name': 'Dogecoin',
            'symbol': 'DOGE',
            'decimals': 8,
            'explorer': 'https://dogechain.info'
        })
        self.api_url = self.API_URLS[0]
    
    def validate_address(self, address: str) -> bool:
        """
        Validate Dogecoin address
        - Starts with D, A, or 9
        - 34 characters (legacy) or variable (newer formats)
        """
        if not address:
            return False
        
        # Should not start with 0x (that's EVM)
        if address.startswith('0x'):
            return False
        
        # Dogecoin addresses typically start with D, A, or 9
        if not (address.startswith('D') or address.startswith('A') or address.startswith('9')):
            return False
        
        # Length check (typically 34 chars for legacy)
        if len(address) < 26 or len(address) > 35:
            return False
        
        return True
    
    def get_address_validation_error(self, address: str) -> Optional[str]:
        if address.startswith('0x'):
            return "This appears to be an EVM address (starts with 0x). Dogecoin addresses start with D, A, or 9."
        if not self.validate_address(address):
            return "Invalid Dogecoin address format. Addresses should start with D, A, or 9 and be 26-35 characters."
        return None
    
    def satoshis_to_doge(self, satoshis: int) -> float:
        """Convert satoshis to DOGE (8 decimals)"""
        return float(Decimal(satoshis) / Decimal(10**8))
    
    def analyze_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze Dogecoin wallet"""
        try:
            # Get address info
            address_info = self._get_address_info(address)
            balance = address_info.get('balance', 0)
            
            # Get transactions
            transactions, total_sent, total_received = self._get_transactions(address)
            
            return self.format_analysis_result(
                address=address,
                chain='dogecoin',
                total_sent=total_sent,
                total_received=total_received,
                current_balance=balance,
                gas_fees=0.0,
                outgoing_count=len([t for t in transactions if t['type'] == 'sent']),
                incoming_count=len([t for t in transactions if t['type'] == 'received']),
                recent_transactions=transactions[:50]
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Dogecoin wallet: {str(e)}")
            raise Exception(f"Failed to analyze Dogecoin wallet: {str(e)}")
    
    def _get_address_info(self, address: str) -> Dict:
        """Get address balance and info"""
        try:
            # Try dogechain.info API first
            url = f"{self.api_url}/address/balance/{address}"
            response = requests.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success') == 1:
                    return {'balance': float(data.get('balance', 0))}
            
            # Fallback to BlockCypher
            url = f"https://api.blockcypher.com/v1/doge/main/addrs/{address}/balance"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return {'balance': self.satoshis_to_doge(data.get('balance', 0))}
            
            return {'balance': 0}
            
        except Exception as e:
            logger.error(f"Error fetching Dogecoin address info: {str(e)}")
            return {'balance': 0}
    
    def _get_transactions(self, address: str, limit: int = 50) -> tuple:
        """Get transaction history"""
        transactions = []
        total_sent = 0.0
        total_received = 0.0
        
        try:
            # Use BlockCypher for transaction history
            url = f"https://api.blockcypher.com/v1/doge/main/addrs/{address}"
            params = {"limit": limit}
            
            response = requests.get(url, params=params, timeout=30)
            if response.status_code != 200:
                return transactions, total_sent, total_received
            
            data = response.json()
            
            # Process transactions
            for tx_ref in data.get('txrefs', []):
                tx_type = 'received' if tx_ref.get('tx_input_n', -1) == -1 else 'sent'
                value = self.satoshis_to_doge(abs(tx_ref.get('value', 0)))
                
                # Parse timestamp
                confirmed = tx_ref.get('confirmed')
                if confirmed:
                    try:
                        dt = datetime.fromisoformat(confirmed.replace('Z', '+00:00'))
                        timestamp = int(dt.timestamp())
                    except:
                        timestamp = 0
                else:
                    timestamp = 0
                
                transactions.append({
                    'hash': tx_ref.get('tx_hash', ''),
                    'type': tx_type,
                    'value': value,
                    'value_usd': 0,
                    'asset': 'DOGE',
                    'from': address if tx_type == 'sent' else '',
                    'to': address if tx_type == 'received' else '',
                    'blockNum': str(tx_ref.get('block_height', '')),
                    'timestamp': timestamp,
                    'fee': 0
                })
                
                if tx_type == 'sent':
                    total_sent += value
                else:
                    total_received += value
            
        except Exception as e:
            logger.error(f"Error fetching Dogecoin transactions: {str(e)}")
        
        return transactions, total_sent, total_received


def create_dogecoin_analyzer():
    return DogecoinAnalyzer()
