"""
Transfer Matcher Service

Identifies and links transfers between:
- User's own wallet addresses
- User's exchange accounts
- CSV-imported transactions (Ledger, etc.)

This prevents double-counting of cost basis when crypto moves between
the user's own wallets/exchanges.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

logger = logging.getLogger(__name__)


class TransferMatcherService:
    """Service to detect and match transfers across wallets and exchanges"""
    
    def __init__(self):
        self.tolerance_hours = 24  # Time window for matching
        self.amount_tolerance = 0.02  # 2% tolerance for fees
    
    def match_transfers(
        self,
        all_transactions: List[Dict],
        user_addresses: Set[str] = None,
        user_exchanges: Set[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze all transactions and identify transfer pairs.
        
        Args:
            all_transactions: List of all transactions from all sources
            user_addresses: Set of user's known wallet addresses
            user_exchanges: Set of user's exchange names
            
        Returns:
            Dict with matched transfers and updated transactions
        """
        if user_addresses is None:
            user_addresses = set()
        if user_exchanges is None:
            user_exchanges = set()
        
        # Group transactions by asset and type
        sends = []  # Outgoing transactions
        receives = []  # Incoming transactions
        
        for tx in all_transactions:
            tx_type = tx.get('tx_type', '').lower()
            
            if tx_type in ['send', 'sent', 'withdrawal', 'transfer_out']:
                sends.append(tx)
            elif tx_type in ['receive', 'received', 'deposit', 'transfer_in']:
                receives.append(tx)
        
        # Find matching pairs
        matched_pairs = []
        matched_send_ids = set()
        matched_receive_ids = set()
        
        for send in sends:
            if send.get('tx_id') in matched_send_ids:
                continue
                
            send_asset = send.get('asset', '').upper()
            send_amount = abs(float(send.get('amount', 0)))
            send_time = self._parse_timestamp(send.get('timestamp'))
            send_source = send.get('exchange', send.get('source', '')).lower()
            
            best_match = None
            best_score = 0
            
            for receive in receives:
                if receive.get('tx_id') in matched_receive_ids:
                    continue
                    
                receive_asset = receive.get('asset', '').upper()
                receive_amount = abs(float(receive.get('amount', 0)))
                receive_time = self._parse_timestamp(receive.get('timestamp'))
                receive_source = receive.get('exchange', receive.get('source', '')).lower()
                
                # Must be same asset
                if send_asset != receive_asset:
                    continue
                
                # Must be different sources
                if send_source == receive_source:
                    continue
                
                # Check amount match (within tolerance for fees)
                if send_amount > 0 and receive_amount > 0:
                    amount_diff = abs(send_amount - receive_amount) / send_amount
                    if amount_diff > self.amount_tolerance:
                        continue
                
                # Check time match
                if send_time and receive_time:
                    time_diff = abs((receive_time - send_time).total_seconds())
                    if time_diff > self.tolerance_hours * 3600:
                        continue
                    
                    # Score based on how close the match is
                    time_score = 1 - (time_diff / (self.tolerance_hours * 3600))
                    amount_score = 1 - amount_diff
                    score = time_score * amount_score
                    
                    if score > best_score:
                        best_score = score
                        best_match = receive
            
            if best_match:
                matched_pairs.append({
                    'send': send,
                    'receive': best_match,
                    'asset': send_asset,
                    'amount': send_amount,
                    'send_source': send_source,
                    'receive_source': best_match.get('exchange', best_match.get('source', '')).lower(),
                    'confidence': best_score
                })
                matched_send_ids.add(send.get('tx_id'))
                matched_receive_ids.add(best_match.get('tx_id'))
        
        # Mark matched transactions
        for tx in all_transactions:
            tx_id = tx.get('tx_id')
            if tx_id in matched_send_ids or tx_id in matched_receive_ids:
                tx['is_transfer'] = True
                tx['matched_transfer'] = True
        
        logger.info(f"Matched {len(matched_pairs)} transfer pairs")
        
        return {
            'matched_pairs': matched_pairs,
            'matched_count': len(matched_pairs),
            'unmatched_sends': len(sends) - len(matched_send_ids),
            'unmatched_receives': len(receives) - len(matched_receive_ids),
            'transactions': all_transactions
        }
    
    def _parse_timestamp(self, ts) -> Optional[datetime]:
        """Parse timestamp to datetime"""
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except:
                pass
        return None
    
    def deduplicate_cost_basis(
        self,
        transactions: List[Dict],
        matched_pairs: List[Dict]
    ) -> List[Dict]:
        """
        Remove duplicate cost basis from transfer receives.
        
        When we have a matched transfer pair, the receive should NOT
        add new cost basis - it should inherit from the original buy.
        
        Args:
            transactions: All transactions
            matched_pairs: List of matched send/receive pairs
            
        Returns:
            Transactions with receives marked to not add cost basis
        """
        # Get IDs of receives that are part of transfer pairs
        transfer_receive_ids = set()
        for pair in matched_pairs:
            receive = pair.get('receive', {})
            if receive.get('tx_id'):
                transfer_receive_ids.add(receive.get('tx_id'))
        
        # Mark these receives as transfers (don't add cost basis)
        for tx in transactions:
            if tx.get('tx_id') in transfer_receive_ids:
                tx['is_transfer'] = True
                tx['skip_cost_basis'] = True
                logger.debug(f"Marked transfer receive: {tx.get('amount')} {tx.get('asset')}")
        
        return transactions


# Singleton instance
transfer_matcher_service = TransferMatcherService()
