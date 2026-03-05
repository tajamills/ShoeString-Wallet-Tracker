"""
Multi-Chain Service - Refactored Version

This module provides a unified interface for analyzing wallets across multiple blockchains.
It delegates to chain-specific analyzers in the chains/ package.
"""

import logging
from typing import Dict, List, Any, Optional

from chains import (
    create_ethereum_analyzer,
    create_polygon_analyzer,
    create_arbitrum_analyzer,
    create_bsc_analyzer,
    create_bitcoin_analyzer,
    create_solana_analyzer
)
from price_service import price_service
from tax_service import tax_service

logger = logging.getLogger(__name__)


class MultiChainServiceV2:
    """
    Refactored multi-chain wallet analysis service.
    
    Uses modular chain analyzers for cleaner separation of concerns.
    """
    
    def __init__(self):
        # Initialize chain analyzers
        self.analyzers = {
            'ethereum': create_ethereum_analyzer(),
            'polygon': create_polygon_analyzer(),
            'arbitrum': create_arbitrum_analyzer(),
            'bsc': create_bsc_analyzer(),
            'bitcoin': create_bitcoin_analyzer(),
            'solana': create_solana_analyzer()
        }
        
        # Chain metadata
        self.chain_symbols = {
            'ethereum': 'ETH',
            'polygon': 'MATIC',
            'arbitrum': 'ETH',
            'bsc': 'BNB',
            'bitcoin': 'BTC',
            'solana': 'SOL'
        }
    
    @property
    def supported_chains(self) -> List[str]:
        """Get list of supported chain identifiers"""
        return list(self.analyzers.keys())
    
    def get_chain_symbol(self, chain: str) -> str:
        """Get native token symbol for a chain"""
        return self.chain_symbols.get(chain, 'ETH')
    
    def analyze_wallet(
        self,
        address: str,
        chain: str = "ethereum",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_tier: str = 'free'
    ) -> Dict[str, Any]:
        """
        Analyze a wallet on the specified chain.
        
        Args:
            address: Wallet address to analyze
            chain: Blockchain identifier (ethereum, bitcoin, etc.)
            start_date: Optional start date filter (YYYY-MM-DD)
            end_date: Optional end date filter (YYYY-MM-DD)
            user_tier: User's subscription tier (free, premium, pro)
        
        Returns:
            Analysis results with USD values and tax data (for premium+ users)
        """
        if chain not in self.analyzers:
            raise ValueError(
                f"Unsupported chain: {chain}. "
                f"Supported chains: {', '.join(self.supported_chains)}"
            )
        
        analyzer = self.analyzers[chain]
        
        # Validate address
        error = analyzer.get_address_validation_error(address)
        if error:
            raise ValueError(error)
        
        # Get analysis from chain-specific analyzer
        analysis = analyzer.analyze_wallet(
            address=address,
            start_date=start_date,
            end_date=end_date,
            user_tier=user_tier
        )
        
        # Add USD values
        symbol = self.get_chain_symbol(chain)
        analysis = self._add_usd_values(analysis, symbol)
        
        # Add tax data for premium+ users
        if user_tier in ['premium', 'pro', 'unlimited']:
            analysis = self._add_tax_data(analysis, symbol)
        
        return analysis
    
    def analyze_all_chains(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_tier: str = 'pro'
    ) -> Dict[str, Any]:
        """
        Analyze a wallet across all EVM-compatible chains.
        
        Args:
            address: EVM wallet address (must start with 0x)
            start_date: Optional start date filter
            end_date: Optional end date filter
            user_tier: User's subscription tier
        
        Returns:
            Aggregated results from all EVM chains
        """
        if not address.startswith('0x'):
            raise ValueError("Multi-chain analysis requires an EVM address (0x...)")
        
        evm_chains = ['ethereum', 'polygon', 'arbitrum', 'bsc']
        results = []
        failed_chains = []
        
        for chain in evm_chains:
            try:
                result = self.analyze_wallet(
                    address=address,
                    chain=chain,
                    start_date=start_date,
                    end_date=end_date,
                    user_tier=user_tier
                )
                
                results.append({
                    'chain': chain,
                    'totalSent': result.get('totalEthSent', 0),
                    'totalReceived': result.get('totalEthReceived', 0),
                    'netBalance': result.get('currentBalance', 0),
                    'transactionCount': (
                        result.get('outgoingTransactionCount', 0) +
                        result.get('incomingTransactionCount', 0)
                    ),
                    'gasFees': result.get('totalGasFees', 0),
                    'valueUsd': result.get('total_value_usd', 0)
                })
                
            except Exception as e:
                logger.warning(f"Failed to analyze {chain}: {str(e)}")
                failed_chains.append({
                    'chain': chain,
                    'error': str(e)
                })
        
        # Aggregate results
        aggregated = {
            'total_transactions': sum(r['transactionCount'] for r in results),
            'total_gas_fees': sum(r['gasFees'] for r in results),
            'total_value_usd': sum(r['valueUsd'] for r in results)
        }
        
        return {
            'address': address,
            'results': results,
            'failed_chains': failed_chains,
            'aggregated': aggregated,
            'chains_analyzed': len(results),
            'total_chains': len(evm_chains)
        }
    
    def _add_usd_values(self, analysis: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """Add USD valuations to analysis results"""
        try:
            current_price = price_service.get_current_price(symbol)
            
            if current_price:
                balance = analysis.get('currentBalance', analysis.get('netEth', 0))
                
                analysis['current_price_usd'] = current_price
                analysis['total_value_usd'] = balance * current_price
                analysis['net_balance_usd'] = balance * current_price
                analysis['total_received_usd'] = analysis.get('totalEthReceived', 0) * current_price
                analysis['total_sent_usd'] = analysis.get('totalEthSent', 0) * current_price
                analysis['total_gas_fees_usd'] = analysis.get('totalGasFees', 0) * current_price
                
                # Add USD value to transactions
                for tx in analysis.get('recentTransactions', []):
                    tx['value_usd'] = float(tx.get('value', 0)) * current_price
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error adding USD values: {str(e)}")
            return analysis
    
    def _add_tax_data(self, analysis: Dict[str, Any], symbol: str) -> Dict[str, Any]:
        """Add tax calculations (cost basis, capital gains)"""
        try:
            current_price = analysis.get('current_price_usd')
            current_balance = analysis.get('currentBalance', analysis.get('netEth', 0))
            transactions = analysis.get('recentTransactions', [])
            
            if not current_price or not transactions:
                return analysis
            
            tax_data = tax_service.calculate_tax_data(
                transactions=transactions,
                current_balance=current_balance,
                current_price=current_price,
                symbol=symbol
            )
            
            analysis['tax_data'] = tax_data
            return analysis
            
        except Exception as e:
            logger.error(f"Error adding tax data: {str(e)}")
            return analysis


# Create singleton instance
multi_chain_service_v2 = MultiChainServiceV2()
