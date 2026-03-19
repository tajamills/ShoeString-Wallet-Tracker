"""
XRP/Ripple Chain Analyzer
Uses XRPL public API to analyze XRP wallets
"""
import requests
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from .base import BaseChainAnalyzer

logger = logging.getLogger(__name__)

class XRPAnalyzer(BaseChainAnalyzer):
    """Analyzer for XRP/Ripple blockchain"""
    
    def __init__(self):
        config = {
            'name': 'XRP/Ripple',
            'symbol': 'XRP',
            'decimals': 6,
            'explorer': 'https://xrpscan.com'
        }
        super().__init__(config)
        # XRPL public servers
        self.api_url = "https://xrplcluster.com"
        self.backup_url = "https://s1.ripple.com:51234"
    
    def _make_request(self, payload: dict) -> dict:
        """Make JSON-RPC request to XRPL"""
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(self.api_url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Try backup server
            logger.warning(f"Primary XRPL server failed, trying backup: {str(e)}")
            try:
                response = requests.post(self.backup_url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                return response.json()
            except Exception as e2:
                logger.error(f"Both XRPL servers failed: {str(e2)}")
                raise
    
    def _drops_to_xrp(self, drops: int) -> float:
        """Convert drops to XRP (1 XRP = 1,000,000 drops)"""
        return float(drops) / 1_000_000
    
    def _get_account_info(self, address: str) -> Dict[str, Any]:
        """Get account info including balance"""
        payload = {
            "method": "account_info",
            "params": [{
                "account": address,
                "ledger_index": "validated"
            }]
        }
        
        result = self._make_request(payload)
        
        if result.get('result', {}).get('status') == 'error':
            error = result.get('result', {}).get('error', 'Unknown error')
            if error == 'actNotFound':
                # Account not found - return 0 balance
                return {'Balance': '0'}
            raise Exception(f"XRPL error: {error}")
        
        return result.get('result', {}).get('account_data', {})
    
    def _get_transactions(self, address: str, limit: int = 50) -> List[Dict]:
        """Get account transactions"""
        payload = {
            "method": "account_tx",
            "params": [{
                "account": address,
                "ledger_index_min": -1,
                "ledger_index_max": -1,
                "limit": limit,
                "forward": False  # Most recent first
            }]
        }
        
        result = self._make_request(payload)
        
        if result.get('result', {}).get('status') == 'error':
            error = result.get('result', {}).get('error', 'Unknown error')
            if error == 'actNotFound':
                return []
            raise Exception(f"XRPL error: {error}")
        
        return result.get('result', {}).get('transactions', [])
    
    def analyze_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze XRP wallet"""
        try:
            # Get account info
            account_info = self._get_account_info(address)
            balance_drops = int(account_info.get('Balance', 0))
            balance_xrp = self._drops_to_xrp(balance_drops)
            
            # Get transactions
            raw_transactions = self._get_transactions(address)
            
            # Process transactions
            transactions = []
            total_sent = 0.0
            total_received = 0.0
            total_fees = 0.0
            
            for tx_wrapper in raw_transactions:
                tx = tx_wrapper.get('tx', {})
                meta = tx_wrapper.get('meta', {})
                
                # Only process Payment transactions
                if tx.get('TransactionType') != 'Payment':
                    continue
                
                # Skip failed transactions
                if meta.get('TransactionResult') != 'tesSUCCESS':
                    continue
                
                # Get amount (can be drops or currency object)
                amount_raw = tx.get('Amount')
                if isinstance(amount_raw, str):
                    # XRP amount in drops
                    amount_xrp = self._drops_to_xrp(int(amount_raw))
                elif isinstance(amount_raw, dict):
                    # Token/IOU - skip for now
                    continue
                else:
                    continue
                
                # Determine direction
                sender = tx.get('Account', '')
                destination = tx.get('Destination', '')
                
                if sender.lower() == address.lower():
                    tx_type = 'sent'
                    total_sent += amount_xrp
                    fee_drops = int(tx.get('Fee', 0))
                    total_fees += self._drops_to_xrp(fee_drops)
                elif destination.lower() == address.lower():
                    tx_type = 'received'
                    total_received += amount_xrp
                else:
                    continue
                
                # Get timestamp
                ripple_epoch = 946684800  # Jan 1, 2000
                close_time = tx.get('date', 0)
                unix_timestamp = close_time + ripple_epoch if close_time else 0
                
                transactions.append({
                    'hash': tx.get('hash', ''),
                    'type': tx_type,
                    'value': amount_xrp,
                    'asset': 'XRP',
                    'blockNum': str(tx.get('ledger_index', '')),
                    'blockTime': unix_timestamp,
                    'fee': self._drops_to_xrp(int(tx.get('Fee', 0))) if tx_type == 'sent' else 0
                })
            
            # Sort by time (newest first)
            transactions.sort(key=lambda x: x.get('blockTime', 0), reverse=True)
            
            logger.info(f"XRP analysis: balance={balance_xrp}, sent={total_sent}, received={total_received}")
            
            return self.format_analysis_result(
                address=address,
                chain='xrp',
                total_sent=total_sent,
                total_received=total_received,
                current_balance=balance_xrp,
                gas_fees=total_fees,
                outgoing_count=len([t for t in transactions if t['type'] == 'sent']),
                incoming_count=len([t for t in transactions if t['type'] == 'received']),
                recent_transactions=transactions[:20]
            )
            
        except Exception as e:
            logger.error(f"Error analyzing XRP wallet: {str(e)}")
            raise Exception(f"Failed to analyze XRP wallet: {str(e)}")


def create_xrp_analyzer():
    return XRPAnalyzer()
