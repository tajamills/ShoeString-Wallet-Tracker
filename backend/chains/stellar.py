"""
Stellar/XLM Chain Analyzer
Uses Stellar Horizon API to analyze XLM wallets
"""
import requests
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from .base import BaseChainAnalyzer

logger = logging.getLogger(__name__)

class StellarAnalyzer(BaseChainAnalyzer):
    """Analyzer for Stellar/XLM blockchain"""
    
    def __init__(self):
        config = {
            'name': 'Stellar/XLM',
            'symbol': 'XLM',
            'decimals': 7,
            'explorer': 'https://stellarchain.io'
        }
        super().__init__(config)
        # Stellar Horizon public API
        self.api_url = "https://horizon.stellar.org"
    
    def _stroops_to_xlm(self, stroops: int) -> float:
        """Convert stroops to XLM (1 XLM = 10,000,000 stroops)"""
        return float(stroops) / 10_000_000
    
    def _get_account(self, address: str) -> Dict[str, Any]:
        """Get account info including balances"""
        url = f"{self.api_url}/accounts/{address}"
        
        response = requests.get(url, timeout=30)
        
        if response.status_code == 404:
            # Account not found
            return None
        
        response.raise_for_status()
        return response.json()
    
    def _get_payments(self, address: str, limit: int = 50) -> List[Dict]:
        """Get account payment operations"""
        url = f"{self.api_url}/accounts/{address}/payments"
        params = {
            "limit": limit,
            "order": "desc"  # Most recent first
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 404:
            return []
        
        response.raise_for_status()
        data = response.json()
        
        return data.get('_embedded', {}).get('records', [])
    
    def _get_transactions(self, address: str, limit: int = 50) -> List[Dict]:
        """Get account transactions for fee calculation"""
        url = f"{self.api_url}/accounts/{address}/transactions"
        params = {
            "limit": limit,
            "order": "desc"
        }
        
        response = requests.get(url, params=params, timeout=30)
        
        if response.status_code == 404:
            return []
        
        response.raise_for_status()
        data = response.json()
        
        return data.get('_embedded', {}).get('records', [])
    
    def analyze_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze Stellar/XLM wallet"""
        try:
            # Get account info
            account = self._get_account(address)
            
            if account is None:
                # Account doesn't exist or is not funded
                return self.format_analysis_result(
                    address=address,
                    chain='xlm',
                    total_sent=0,
                    total_received=0,
                    current_balance=0,
                    gas_fees=0,
                    outgoing_count=0,
                    incoming_count=0,
                    recent_transactions=[]
                )
            
            # Get native XLM balance
            balance_xlm = 0.0
            for balance in account.get('balances', []):
                if balance.get('asset_type') == 'native':
                    balance_xlm = float(balance.get('balance', 0))
                    break
            
            # Get payments
            payments = self._get_payments(address)
            
            # Get transactions for fees
            transactions_raw = self._get_transactions(address)
            total_fees = sum(
                int(tx.get('fee_charged', 0)) 
                for tx in transactions_raw 
                if tx.get('source_account') == address
            )
            total_fees_xlm = self._stroops_to_xlm(total_fees)
            
            # Process payments
            transactions = []
            total_sent = 0.0
            total_received = 0.0
            
            for payment in payments:
                # Only process native XLM payments and path payments
                payment_type = payment.get('type')
                if payment_type not in ['payment', 'path_payment_strict_send', 'path_payment_strict_receive', 'create_account']:
                    continue
                
                # Get amount
                if payment_type == 'create_account':
                    amount = float(payment.get('starting_balance', 0))
                    asset_type = 'native'
                else:
                    amount = float(payment.get('amount', 0))
                    asset_type = payment.get('asset_type', '')
                
                # Only track native XLM for now
                if asset_type != 'native':
                    continue
                
                # Determine direction
                sender = payment.get('from', payment.get('source_account', ''))
                receiver = payment.get('to', payment.get('account', ''))
                
                if sender == address:
                    tx_type = 'sent'
                    total_sent += amount
                elif receiver == address:
                    tx_type = 'received'
                    total_received += amount
                else:
                    continue
                
                # Get timestamp
                created_at = payment.get('created_at', '')
                if created_at:
                    try:
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        unix_timestamp = int(dt.timestamp())
                    except:
                        unix_timestamp = 0
                else:
                    unix_timestamp = 0
                
                # Get ledger number from paging token
                paging_token = payment.get('paging_token', '')
                ledger = paging_token.split('-')[0] if '-' in paging_token else ''
                
                transactions.append({
                    'hash': payment.get('transaction_hash', ''),
                    'type': tx_type,
                    'value': amount,
                    'asset': 'XLM',
                    'blockNum': ledger,
                    'blockTime': unix_timestamp,
                    'fee': 0  # Fees tracked separately
                })
            
            logger.info(f"XLM analysis: balance={balance_xlm}, sent={total_sent}, received={total_received}")
            
            return self.format_analysis_result(
                address=address,
                chain='xlm',
                total_sent=total_sent,
                total_received=total_received,
                current_balance=balance_xlm,
                gas_fees=total_fees_xlm,
                outgoing_count=len([t for t in transactions if t['type'] == 'sent']),
                incoming_count=len([t for t in transactions if t['type'] == 'received']),
                recent_transactions=transactions[:20]
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Stellar wallet: {str(e)}")
            raise Exception(f"Failed to analyze Stellar wallet: {str(e)}")


def create_stellar_analyzer():
    return StellarAnalyzer()
