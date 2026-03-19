"""
Solana Chain Analyzer
"""
import os
import requests
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from .base import BaseChainAnalyzer

logger = logging.getLogger(__name__)


class SolanaAnalyzer(BaseChainAnalyzer):
    """Analyzer for Solana blockchain"""
    
    def __init__(self):
        api_key = os.environ.get('ALCHEMY_API_KEY', '')
        super().__init__({
            'chain_id': 'solana',
            'name': 'Solana',
            'symbol': 'SOL',
            'decimals': 9,
            'explorer': 'https://solscan.io'
        })
        self.alchemy_url = f"https://solana-mainnet.g.alchemy.com/v2/{api_key}"
    
    def validate_address(self, address: str) -> bool:
        """Validate Solana address (base58, 32-44 chars)"""
        if address.startswith('0x'):
            return False
        # Basic base58 check
        try:
            import base58
            decoded = base58.b58decode(address)
            return len(decoded) == 32
        except Exception:
            # Fallback: check length and characters
            return len(address) >= 32 and len(address) <= 44
    
    def get_address_validation_error(self, address: str) -> Optional[str]:
        if address.startswith('0x'):
            return "This appears to be an EVM address (starts with 0x). Try selecting Ethereum instead."
        if not self.validate_address(address):
            return "Invalid Solana address format. Solana addresses are base58 encoded."
        return None
    
    def lamports_to_sol(self, lamports: int) -> float:
        """Convert lamports to SOL"""
        return float(Decimal(lamports) / Decimal(10**9))
    
    def analyze_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze Solana wallet"""
        try:
            # Get current balance
            balance = self._get_balance(address)
            print(f"SOLANA DEBUG: Balance for {address}: {balance}")
            
            # Get transaction signatures
            signatures = self._get_signatures(address)
            print(f"SOLANA DEBUG: Got {len(signatures)} signatures")
            
            # Get transaction details
            transactions, total_sent, total_received = self._process_signatures(
                signatures, address
            )
            print(f"SOLANA DEBUG: Processed - sent={total_sent}, received={total_received}, txs={len(transactions)}")
            
            return self.format_analysis_result(
                address=address,
                chain='solana',
                total_sent=total_sent,
                total_received=total_received,
                current_balance=balance,
                gas_fees=0.0,
                outgoing_count=len([t for t in transactions if t['type'] == 'sent']),
                incoming_count=len([t for t in transactions if t['type'] == 'received']),
                recent_transactions=transactions
            )
            
        except Exception as e:
            logger.error(f"Error analyzing Solana wallet: {str(e)}")
            raise Exception(f"Failed to analyze Solana wallet: {str(e)}")
    
    def _get_balance(self, address: str) -> float:
        """Get SOL balance for address"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [address]
        }
        
        response = requests.post(self.alchemy_url, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json().get('result', {})
        
        return self.lamports_to_sol(result.get('value', 0))
    
    def _get_signatures(self, address: str, limit: int = 500) -> List[Dict]:
        """Get transaction signatures for address"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getSignaturesForAddress",
            "params": [
                address,
                {"limit": limit}
            ]
        }
        
        response = requests.post(self.alchemy_url, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get('result', [])
    
    def _get_transaction(self, signature: str) -> Optional[Dict]:
        """Get transaction details by signature"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTransaction",
            "params": [
                signature,
                {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}
            ]
        }
        
        try:
            response = requests.post(self.alchemy_url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json().get('result')
        except Exception:
            return None
    
    def _process_signatures(
        self,
        signatures: List[Dict],
        address: str
    ) -> tuple:
        """Process transaction signatures with batch RPC for performance"""
        transactions = []
        total_sent = 0.0
        total_received = 0.0
        
        # Process ALL signatures, not just first 20
        sigs_to_process = signatures[:200]  # Up to 200 transactions
        logger.info(f"Processing {len(sigs_to_process)} signatures for {address}")
        
        # Batch fetch transactions using batch RPC
        batch_size = 20
        for batch_start in range(0, len(sigs_to_process), batch_size):
            batch_sigs = sigs_to_process[batch_start:batch_start + batch_size]
            batch_payload = []
            
            for i, sig_info in enumerate(batch_sigs):
                signature = sig_info.get('signature')
                if not signature:
                    continue
                batch_payload.append({
                    "jsonrpc": "2.0",
                    "id": i,
                    "method": "getTransaction",
                    "params": [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
                })
            
            if not batch_payload:
                continue
            
            try:
                response = requests.post(self.alchemy_url, json=batch_payload, timeout=30)
                response.raise_for_status()
                results = response.json()
                if not isinstance(results, list):
                    results = [results]
                
                for idx, result in enumerate(results):
                    tx = result.get('result')
                    if not tx:
                        continue
                    
                    sig_idx = batch_start + idx
                    if sig_idx < len(sigs_to_process):
                        signature = sigs_to_process[sig_idx].get('signature', '')
                    else:
                        signature = ''
                    
                    meta = tx.get('meta', {})
                    if meta.get('err'):
                        continue
                    
                    pre_balances = meta.get('preBalances', [])
                    post_balances = meta.get('postBalances', [])
                    
                    account_keys = tx.get('transaction', {}).get('message', {}).get('accountKeys', [])
                    address_index = None
                    for i_key, key in enumerate(account_keys):
                        key_str = key.get('pubkey', key) if isinstance(key, dict) else key
                        if key_str == address:
                            address_index = i_key
                            break
                    
                    if address_index is None or address_index >= len(pre_balances):
                        continue
                    
                    pre_balance = pre_balances[address_index]
                    post_balance = post_balances[address_index]
                    change_lamports = post_balance - pre_balance
                    change_sol = abs(self.lamports_to_sol(change_lamports))
                    
                    if change_lamports > 0:
                        tx_type = 'received'
                        total_received += change_sol
                    elif change_lamports < 0:
                        tx_type = 'sent'
                        total_sent += change_sol
                    else:
                        continue
                    
                    transactions.append({
                        'hash': signature,
                        'type': tx_type,
                        'value': change_sol,
                        'asset': 'SOL',
                        'blockNum': str(tx.get('slot', '')),
                        'blockTime': tx.get('blockTime', 0),
                        'timestamp': tx.get('blockTime', 0),
                        'fee': self.lamports_to_sol(meta.get('fee', 0))
                    })
                
            except Exception as e:
                logger.warning(f"Batch transaction fetch failed: {e}")
                # Fall back to individual fetches for this batch
                for sig_info in batch_sigs:
                    signature = sig_info.get('signature')
                    if not signature:
                        continue
                    tx = self._get_transaction(signature)
                    if not tx:
                        continue
                    meta = tx.get('meta', {})
                    if meta.get('err'):
                        continue
                    pre_balances = meta.get('preBalances', [])
                    post_balances = meta.get('postBalances', [])
                    account_keys = tx.get('transaction', {}).get('message', {}).get('accountKeys', [])
                    address_index = None
                    for i_key, key in enumerate(account_keys):
                        key_str = key.get('pubkey', key) if isinstance(key, dict) else key
                        if key_str == address:
                            address_index = i_key
                            break
                    if address_index is None or address_index >= len(pre_balances):
                        continue
                    pre_balance = pre_balances[address_index]
                    post_balance = post_balances[address_index]
                    change_lamports = post_balance - pre_balance
                    change_sol = abs(self.lamports_to_sol(change_lamports))
                    if change_lamports > 0:
                        tx_type = 'received'
                        total_received += change_sol
                    elif change_lamports < 0:
                        tx_type = 'sent'
                        total_sent += change_sol
                    else:
                        continue
                    transactions.append({
                        'hash': signature,
                        'type': tx_type,
                        'value': change_sol,
                        'asset': 'SOL',
                        'blockNum': str(tx.get('slot', '')),
                        'blockTime': tx.get('blockTime', 0),
                        'timestamp': tx.get('blockTime', 0),
                        'fee': self.lamports_to_sol(meta.get('fee', 0))
                    })
        
        # Sort by block time (newest first)
        transactions.sort(key=lambda x: x.get('blockTime', 0), reverse=True)
        
        logger.info(f"Processed: sent={total_sent} SOL, received={total_received} SOL, {len(transactions)} txs")
        
        return transactions, total_sent, total_received


def create_solana_analyzer():
    return SolanaAnalyzer()
