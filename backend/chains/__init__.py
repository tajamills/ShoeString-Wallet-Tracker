"""
Chain Analyzers Package

This package provides modular blockchain analyzers for different chains.
Each chain has its own analyzer class that implements the BaseChainAnalyzer interface.
"""

from .base import BaseChainAnalyzer
from .evm import (
    EVMChainAnalyzer,
    create_ethereum_analyzer,
    create_polygon_analyzer,
    create_arbitrum_analyzer,
    create_bsc_analyzer,
    create_avalanche_analyzer,
    create_optimism_analyzer,
    create_base_analyzer,
    create_fantom_analyzer
)
from .bitcoin import BitcoinAnalyzer, create_bitcoin_analyzer
from .solana import SolanaAnalyzer, create_solana_analyzer
from .algorand import AlgorandAnalyzer, create_algorand_analyzer
from .dogecoin import DogecoinAnalyzer, create_dogecoin_analyzer

__all__ = [
    'BaseChainAnalyzer',
    'EVMChainAnalyzer',
    'BitcoinAnalyzer',
    'SolanaAnalyzer',
    'AlgorandAnalyzer',
    'DogecoinAnalyzer',
    'create_ethereum_analyzer',
    'create_polygon_analyzer',
    'create_arbitrum_analyzer',
    'create_bsc_analyzer',
    'create_avalanche_analyzer',
    'create_optimism_analyzer',
    'create_base_analyzer',
    'create_fantom_analyzer',
    'create_bitcoin_analyzer',
    'create_solana_analyzer',
    'create_algorand_analyzer',
    'create_dogecoin_analyzer',
]
