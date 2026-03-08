"""
Chain of Custody Service
Traces the origin of cryptocurrency by following the transaction graph backwards.
Helps establish accurate cost basis by finding the original acquisition point.
"""
import os
import requests
import logging
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)


# Known exchange hot wallet addresses (partial list - can be expanded)
KNOWN_EXCHANGE_ADDRESSES = {
    # Binance
    '0x28c6c06298d514db089934071355e5743bf21d60': 'Binance',
    '0x21a31ee1afc51d94c2efccaa2092ad1028285549': 'Binance',
    '0xdfd5293d8e347dfe59e90efd55b2956a1343963d': 'Binance',
    '0x56eddb7aa87536c09ccc2793473599fd21a8b17f': 'Binance',
    '0x9696f59e4d72e237be84ffd425dcad154bf96976': 'Binance',
    # Coinbase
    '0x71660c4005ba85c37ccec55d0c4493e66fe775d3': 'Coinbase',
    '0x503828976d22510aad0201ac7ec88293211d23da': 'Coinbase',
    '0xddfabcdc4d8ffc6d5beaf154f18b778f892a0740': 'Coinbase',
    '0x3cd751e6b0078be393132286c442345e5dc49699': 'Coinbase',
    '0xb5d85cbf7cb3ee0d56b3bb207d5fc4b82f43f511': 'Coinbase',
    # Kraken
    '0x2910543af39aba0cd09dbb2d50200b3e800a63d2': 'Kraken',
    '0x0a869d79a7052c7f1b55a8ebabbea3420f0d1e13': 'Kraken',
    # Gemini
    '0xd24400ae8bfebb18ca49be86258a3c749cf46853': 'Gemini',
    '0x6fc82a5fe25a5cdb58bc74600a40a69c065263f8': 'Gemini',
    # FTX (historical)
    '0x2faf487a4414fe77e2327f0bf4ae2a264a776ad2': 'FTX',
    # Bitfinex
    '0x876eabf441b2ee5b5b0554fd502a8e0600950cfa': 'Bitfinex',
    '0x742d35cc6634c0532925a3b844bc454e4438f44e': 'Bitfinex',
    # KuCoin
    '0x2b5634c42055806a59e9107ed44d43c426e58258': 'KuCoin',
    '0x689c56aef474df92d44a1b70850f808488f9769c': 'KuCoin',
    # Huobi
    '0xab5c66752a9e8167967685f1450532fb96d5d24f': 'Huobi',
    '0x6748f50f686bfbca6fe8ad62b22228b87f31ff2b': 'Huobi',
    # OKX
    '0x6cc5f688a315f3dc28a7781717a9a798a59fda7b': 'OKX',
    # Crypto.com
    '0x6262998ced04146fa42253a5c0af90ca02dfd2a3': 'Crypto.com',
    '0x46340b20830761efd32832a74d7169b29feb9758': 'Crypto.com',
}

# DEX router addresses
KNOWN_DEX_ADDRESSES = {
    '0x7a250d5630b4cf539739df2c5dacb4c659f2488d': 'Uniswap V2 Router',
    '0xe592427a0aece92de3edee1f18e0157c05861564': 'Uniswap V3 Router',
    '0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45': 'Uniswap V3 Router 2',
    '0xd9e1ce17f2641f24ae83637ab66a2cca9c378b9f': 'SushiSwap Router',
    '0x1111111254fb6c44bac0bed2854e76f90643097d': '1inch Router',
    '0x881d40237659c251811cec9c364ef91dc08d300c': 'Metamask Swap Router',
}


class ChainOfCustodyService:
    """
    Service to trace the chain of custody for cryptocurrency assets.
    Follows transactions backwards to find the original acquisition point.
    """
    
    def __init__(self):
        self.alchemy_api_key = os.environ.get('ALCHEMY_API_KEY')
        self.alchemy_urls = {
            'ethereum': f"https://eth-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
            'polygon': f"https://polygon-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
            'arbitrum': f"https://arb-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
            'bsc': f"https://bnb-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
            'base': f"https://base-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
            'optimism': f"https://opt-mainnet.g.alchemy.com/v2/{self.alchemy_api_key}",
        }
        # Default dormancy threshold (days without movement)
        self.dormancy_threshold_days = 365
    
    def analyze_chain_of_custody(
        self,
        address: str,
        chain: str = 'ethereum',
        max_depth: int = 10,
        dormancy_days: int = 365
    ) -> Dict[str, Any]:
        """
        Analyze the chain of custody for a wallet address.
        Traces backwards through transactions to find origin points.
        
        Args:
            address: The wallet address to analyze
            chain: The blockchain to analyze on
            max_depth: Maximum number of hops to trace (0 = unlimited)
            dormancy_days: Consider asset dormant if no movement for this many days
            
        Returns:
            Dict containing custody chain, origin points, and analysis
        """
        if chain not in self.alchemy_urls:
            raise ValueError(f"Chain {chain} not supported for custody analysis")
        
        self.dormancy_threshold_days = dormancy_days
        address = address.lower()
        
        # Results storage
        custody_chain = []
        origin_points = []
        visited_addresses = set()
        exchange_endpoints = []
        dex_endpoints = []
        
        # BFS queue: (address, depth, path)
        queue = deque([(address, 0, [])])
        visited_addresses.add(address)
        
        while queue:
            current_address, depth, path = queue.popleft()
            
            # Check depth limit (0 = unlimited)
            if max_depth > 0 and depth >= max_depth:
                continue
            
            try:
                # Fetch incoming transactions for this address
                incoming_txs = self._fetch_incoming_transfers(current_address, chain)
                
                if not incoming_txs:
                    # No incoming transactions - this could be an origin point
                    origin_points.append({
                        'address': current_address,
                        'type': 'no_incoming_transactions',
                        'depth': depth,
                        'path': path,
                        'reason': 'No incoming transactions found - possible mining/staking origin'
                    })
                    continue
                
                for tx in incoming_txs:
                    from_address = tx.get('from', '').lower()
                    tx_value = float(tx.get('value', 0) or 0)
                    tx_hash = tx.get('hash', '')
                    block_num = tx.get('blockNum', '')
                    timestamp = self._get_block_timestamp(block_num, chain)
                    
                    if not from_address or from_address in visited_addresses:
                        continue
                    
                    # Record this link in the custody chain
                    custody_link = {
                        'from': from_address,
                        'to': current_address,
                        'tx_hash': tx_hash,
                        'value': tx_value,
                        'asset': tx.get('asset', 'ETH'),
                        'block': block_num,
                        'timestamp': timestamp,
                        'depth': depth + 1
                    }
                    
                    # Check if from_address is a known exchange
                    if from_address in KNOWN_EXCHANGE_ADDRESSES:
                        exchange_name = KNOWN_EXCHANGE_ADDRESSES[from_address]
                        custody_link['origin_type'] = 'exchange'
                        custody_link['exchange_name'] = exchange_name
                        custody_chain.append(custody_link)
                        exchange_endpoints.append({
                            'address': from_address,
                            'exchange': exchange_name,
                            'tx_hash': tx_hash,
                            'value': tx_value,
                            'timestamp': timestamp,
                            'depth': depth + 1,
                            'path': path + [current_address]
                        })
                        continue  # Don't trace further - exchange is origin
                    
                    # Check if from_address is a DEX
                    if from_address in KNOWN_DEX_ADDRESSES:
                        dex_name = KNOWN_DEX_ADDRESSES[from_address]
                        custody_link['origin_type'] = 'dex_swap'
                        custody_link['dex_name'] = dex_name
                        custody_chain.append(custody_link)
                        dex_endpoints.append({
                            'address': from_address,
                            'dex': dex_name,
                            'tx_hash': tx_hash,
                            'value': tx_value,
                            'timestamp': timestamp,
                            'depth': depth + 1,
                            'path': path + [current_address]
                        })
                        continue  # DEX swap - could trace further but this is a conversion point
                    
                    # Check dormancy
                    if timestamp and self._is_dormant(timestamp):
                        custody_link['origin_type'] = 'dormant'
                        custody_chain.append(custody_link)
                        origin_points.append({
                            'address': from_address,
                            'type': 'dormant',
                            'last_activity': timestamp,
                            'depth': depth + 1,
                            'path': path + [current_address],
                            'reason': f'No activity for {self.dormancy_threshold_days}+ days'
                        })
                        continue  # Dormant address - treat as origin
                    
                    # Normal transfer - add to chain and continue tracing
                    custody_link['origin_type'] = 'transfer'
                    custody_chain.append(custody_link)
                    
                    # Add to queue for further exploration
                    visited_addresses.add(from_address)
                    queue.append((from_address, depth + 1, path + [current_address]))
                    
            except Exception as e:
                logger.error(f"Error analyzing address {current_address}: {str(e)}")
                continue
        
        # Calculate statistics
        total_from_exchanges = sum(ep.get('value', 0) for ep in exchange_endpoints)
        total_from_dex = sum(dp.get('value', 0) for dp in dex_endpoints)
        
        return {
            'analyzed_address': address,
            'chain': chain,
            'analysis_timestamp': datetime.utcnow().isoformat(),
            'settings': {
                'max_depth': max_depth,
                'dormancy_days': dormancy_days
            },
            'summary': {
                'total_links_traced': len(custody_chain),
                'unique_addresses_visited': len(visited_addresses),
                'exchange_origins': len(exchange_endpoints),
                'dex_origins': len(dex_endpoints),
                'dormant_origins': len([o for o in origin_points if o['type'] == 'dormant']),
                'unknown_origins': len([o for o in origin_points if o['type'] == 'no_incoming_transactions']),
                'total_value_from_exchanges': total_from_exchanges,
                'total_value_from_dex': total_from_dex
            },
            'custody_chain': custody_chain[:100],  # Limit for response size
            'exchange_endpoints': exchange_endpoints,
            'dex_endpoints': dex_endpoints,
            'origin_points': origin_points,
            'visited_addresses': list(visited_addresses)[:50]  # Limit for response size
        }
    
    def _fetch_incoming_transfers(self, address: str, chain: str) -> List[Dict]:
        """Fetch incoming transfers for an address"""
        alchemy_url = self.alchemy_urls.get(chain)
        if not alchemy_url:
            return []
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "alchemy_getAssetTransfers",
            "params": [{
                "fromBlock": "0x0",
                "toBlock": "latest",
                "toAddress": address,
                "category": ["external", "internal"],
                "withMetadata": True,
                "excludeZeroValue": True,
                "maxCount": "0x64"  # 100 transactions
            }]
        }
        
        try:
            response = requests.post(alchemy_url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json().get('result', {}).get('transfers', [])
        except Exception as e:
            logger.error(f"Error fetching transfers for {address}: {str(e)}")
            return []
    
    def _get_block_timestamp(self, block_num: str, chain: str) -> Optional[str]:
        """Get timestamp for a block number"""
        if not block_num or block_num == 'pending':
            return None
        
        alchemy_url = self.alchemy_urls.get(chain)
        if not alchemy_url:
            return None
        
        try:
            # Convert block number to hex if needed
            if not block_num.startswith('0x'):
                block_num = hex(int(block_num))
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "eth_getBlockByNumber",
                "params": [block_num, False]
            }
            
            response = requests.post(alchemy_url, json=payload, timeout=10)
            response.raise_for_status()
            block = response.json().get('result', {})
            
            if block and 'timestamp' in block:
                timestamp = int(block['timestamp'], 16)
                return datetime.utcfromtimestamp(timestamp).isoformat()
        except Exception as e:
            logger.debug(f"Error getting block timestamp: {str(e)}")
        
        return None
    
    def _is_dormant(self, timestamp_str: str) -> bool:
        """Check if the timestamp indicates dormancy"""
        if not timestamp_str:
            return False
        
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', ''))
            dormancy_cutoff = datetime.utcnow() - timedelta(days=self.dormancy_threshold_days)
            return timestamp < dormancy_cutoff
        except Exception:
            return False
    
    def get_address_label(self, address: str) -> Optional[str]:
        """Get a label for a known address"""
        address = address.lower()
        
        if address in KNOWN_EXCHANGE_ADDRESSES:
            return f"Exchange: {KNOWN_EXCHANGE_ADDRESSES[address]}"
        
        if address in KNOWN_DEX_ADDRESSES:
            return f"DEX: {KNOWN_DEX_ADDRESSES[address]}"
        
        return None


# Global service instance
custody_service = ChainOfCustodyService()
