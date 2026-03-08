"""
Base chain analyzer with common functionality
"""
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseChainAnalyzer(ABC):
    """Abstract base class for chain analyzers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get('name', 'Unknown')
        self.symbol = config.get('symbol', 'UNKNOWN')
        self.decimals = config.get('decimals', 18)
        self.explorer = config.get('explorer', '')
    
    @abstractmethod
    def analyze_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze a wallet and return standardized results"""
        pass
    
    def validate_address(self, address: str) -> bool:
        """Validate address format for this chain"""
        return True
    
    def get_address_validation_error(self, address: str) -> Optional[str]:
        """Return error message if address is invalid, None if valid"""
        return None
    
    def wei_to_native(self, value: str, decimals: int = None) -> float:
        """Convert smallest unit to native token"""
        if decimals is None:
            decimals = self.decimals
        try:
            if isinstance(value, str) and value.startswith('0x'):
                return float(Decimal(str(int(value, 16))) / Decimal(10**decimals))
            return float(Decimal(str(value)) / Decimal(10**decimals))
        except Exception:
            return 0.0
    
    def safe_parse_block_num(self, block_num: str) -> int:
        """Safely parse block number that could be hex or decimal"""
        try:
            if block_num == 'pending' or not block_num:
                return float('inf')
            
            if isinstance(block_num, str) and block_num.startswith('0x'):
                return int(block_num, 16)
            
            return int(block_num)
        except (ValueError, TypeError):
            return float('inf')
    
    def format_analysis_result(
        self,
        address: str,
        chain: str,
        total_sent: float,
        total_received: float,
        current_balance: float,
        gas_fees: float = 0.0,
        outgoing_count: int = 0,
        incoming_count: int = 0,
        tokens_sent: Dict = None,
        tokens_received: Dict = None,
        recent_transactions: List = None
    ) -> Dict[str, Any]:
        """Format analysis results in a standardized way"""
        return {
            'address': address,
            'chain': chain,
            'totalEthSent': total_sent,
            'totalEthReceived': total_received,
            'totalGasFees': gas_fees,
            'currentBalance': current_balance,
            'netEth': current_balance,
            'netFlow': total_received - total_sent - gas_fees,
            'outgoingTransactionCount': outgoing_count,
            'incomingTransactionCount': incoming_count,
            'tokensSent': tokens_sent or {},
            'tokensReceived': tokens_received or {},
            'recentTransactions': recent_transactions or []
        }
