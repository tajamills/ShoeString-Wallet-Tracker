"""
EVM Chain Analyzer (Ethereum, Polygon, Arbitrum, BSC)
"""
import os
import requests
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from .base import BaseChainAnalyzer

logger = logging.getLogger(__name__)


class EVMChainAnalyzer(BaseChainAnalyzer):
    """Analyzer for EVM-compatible chains using Alchemy API"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.alchemy_api_key = os.environ.get('ALCHEMY_API_KEY')
        self.alchemy_url = config.get('alchemy_url', '').replace(
            '{API_KEY}', self.alchemy_api_key or ''
        )
    
    def validate_address(self, address: str) -> bool:
        """EVM addresses must start with 0x and be 42 characters"""
        return address.startswith('0x') and len(address) == 42
    
    def get_address_validation_error(self, address: str) -> Optional[str]:
        if not address.startswith('0x'):
            return f"This appears to be a non-EVM address. For {self.name}, use an address starting with 0x."
        if len(address) != 42:
            return f"Invalid address length. EVM addresses should be 42 characters."
        return None
    
    def analyze_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze EVM wallet using Alchemy API"""
        try:
            address = address.lower()
            
            # Fetch outgoing transactions
            outgoing_txs = self._fetch_transfers(address, 'from')
            
            # Fetch incoming transactions
            incoming_txs = self._fetch_transfers(address, 'to')
            
            # Get current balance
            current_balance = self._get_balance(address)
            
            # Calculate gas fees for outgoing transactions
            total_gas = self._calculate_gas_fees(outgoing_txs[:100])
            
            # Process transactions
            total_sent, tokens_sent = self._sum_transfers(outgoing_txs, self.symbol)
            total_received, tokens_received = self._sum_transfers(incoming_txs, self.symbol)
            
            # Build recent transactions list with running balance
            recent_transactions = self._build_recent_transactions(
                outgoing_txs, incoming_txs, current_balance
            )
            
            return self.format_analysis_result(
                address=address,
                chain=self.config.get('chain_id', 'ethereum'),
                total_sent=total_sent,
                total_received=total_received,
                current_balance=current_balance,
                gas_fees=total_gas,
                outgoing_count=len(outgoing_txs),
                incoming_count=len(incoming_txs),
                tokens_sent=tokens_sent,
                tokens_received=tokens_received,
                recent_transactions=recent_transactions
            )
            
        except Exception as e:
            logger.error(f"Error analyzing {self.name} wallet: {str(e)}")
            raise Exception(f"Failed to analyze {self.name} wallet: {str(e)}")
    
    def _fetch_transfers(self, address: str, direction: str) -> List[Dict]:
        """Fetch asset transfers from Alchemy with pagination for large wallets"""
        all_transfers = []
        page_key = None
        max_pages = 10  # Up to 10,000 transfers
        
        for _ in range(max_pages):
            params = {
                "fromBlock": "0x0",
                "toBlock": "latest",
                f"{direction}Address": address,
                "category": ["external", "internal", "erc20"],
                "withMetadata": True,
                "excludeZeroValue": False,
                "maxCount": "0x3e8"
            }
            if page_key:
                params["pageKey"] = page_key
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "alchemy_getAssetTransfers",
                "params": [params]
            }
            
            response = requests.post(self.alchemy_url, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json().get('result', {})
            transfers = result.get('transfers', [])
            all_transfers.extend(transfers)
            
            page_key = result.get('pageKey')
            if not page_key or not transfers:
                break
        
        logger.info(f"{self.name}: Fetched {len(all_transfers)} {direction} transfers")
        return all_transfers
    
    def _get_balance(self, address: str) -> float:
        """Get current native token balance"""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_getBalance",
            "params": [address, "latest"]
        }
        
        response = requests.post(self.alchemy_url, json=payload, timeout=30)
        response.raise_for_status()
        balance_hex = response.json().get('result', '0x0')
        return int(balance_hex, 16) / 1e18
    
    def _calculate_gas_fees(self, transactions: List[Dict]) -> float:
        """
        Calculate total gas fees using batch RPC instead of individual calls.
        For large wallets, use estimation to avoid thousands of RPC calls.
        """
        if not transactions:
            return 0.0
        
        # For large tx sets, batch the first 50 receipts and estimate the rest
        batch_size = min(len(transactions), 50)
        tx_hashes = []
        for tx in transactions[:batch_size]:
            tx_hash = tx.get('hash')
            if tx_hash and tx.get('asset') == self.symbol:
                tx_hashes.append(tx_hash)
        
        if not tx_hashes:
            return 0.0
        
        total_gas = 0.0
        sampled_count = 0
        
        # Batch RPC: send all receipt requests in one call
        batch_payload = []
        for i, tx_hash in enumerate(tx_hashes[:20]):  # Sample up to 20 for estimation
            batch_payload.append({
                "jsonrpc": "2.0",
                "id": i,
                "method": "eth_getTransactionReceipt",
                "params": [tx_hash]
            })
        
        try:
            response = requests.post(self.alchemy_url, json=batch_payload, timeout=30)
            results = response.json() if response.status_code == 200 else []
            
            for result in results:
                receipt = result.get('result', {})
                if receipt:
                    gas_used = int(receipt.get('gasUsed', '0x0'), 16)
                    gas_price = int(receipt.get('effectiveGasPrice', '0x0'), 16)
                    total_gas += (gas_used * gas_price) / 1e18
                    sampled_count += 1
        except Exception as e:
            logger.warning(f"Batch gas fee calculation failed: {e}")
            return 0.0
        
        # Extrapolate for remaining transactions
        if sampled_count > 0:
            native_tx_count = sum(1 for tx in transactions if tx.get('asset') == self.symbol)
            avg_gas = total_gas / sampled_count
            total_gas = avg_gas * native_tx_count
        
        return total_gas
    
    def _sum_transfers(self, transfers: List[Dict], native_symbol: str) -> tuple:
        """Sum transfer values, separating native token and ERC20s"""
        total_native = 0.0
        tokens = {}
        
        for tx in transfers:
            value = tx.get('value')
            if value is None:
                continue
            
            if tx.get('asset') == native_symbol:
                total_native += float(value)
            else:
                token = tx.get('asset', 'UNKNOWN')
                tokens[token] = tokens.get(token, 0) + float(value)
        
        return total_native, tokens
    
    def _build_recent_transactions(
        self,
        outgoing: List[Dict],
        incoming: List[Dict],
        current_balance: float
    ) -> List[Dict]:
        """Build transaction list from ALL transfers for tax calculations"""
        all_txs = []
        
        # Process ALL outgoing (not just 10)
        for tx in outgoing:
            metadata = tx.get('metadata', {})
            block_time = metadata.get('blockTimestamp', '')
            timestamp = 0
            if block_time:
                try:
                    dt = datetime.fromisoformat(block_time.replace('Z', '+00:00'))
                    timestamp = int(dt.timestamp())
                except Exception:
                    pass
            
            all_txs.append({
                "hash": tx.get('hash', ''),
                "type": "sent",
                "value": float(tx.get('value', 0) or 0),
                "asset": tx.get('asset', self.symbol),
                "to": tx.get('to', ''),
                "to_label": metadata.get('exchangeName') or metadata.get('contractName'),
                "blockNum": tx.get('blockNum', ''),
                "blockTime": timestamp,
                "timestamp": timestamp,
                "category": tx.get('category', '')
            })
        
        # Process ALL incoming
        for tx in incoming:
            metadata = tx.get('metadata', {})
            block_time = metadata.get('blockTimestamp', '')
            timestamp = 0
            if block_time:
                try:
                    dt = datetime.fromisoformat(block_time.replace('Z', '+00:00'))
                    timestamp = int(dt.timestamp())
                except Exception:
                    pass
            
            all_txs.append({
                "hash": tx.get('hash', ''),
                "type": "received",
                "value": float(tx.get('value', 0) or 0),
                "asset": tx.get('asset', self.symbol),
                "from": tx.get('from', ''),
                "from_label": metadata.get('exchangeName') or metadata.get('contractName'),
                "blockNum": tx.get('blockNum', ''),
                "blockTime": timestamp,
                "timestamp": timestamp,
                "category": tx.get('category', '')
            })
        
        # Sort by block (oldest first for balance calc)
        all_txs.sort(key=lambda x: self.safe_parse_block_num(x['blockNum']))
        
        # Calculate running balance (work backwards) on the most recent subset
        display_txs = sorted(all_txs, key=lambda x: self.safe_parse_block_num(x['blockNum']), reverse=True)
        running = current_balance
        for tx in display_txs[:50]:  # Running balance for display
            if tx['type'] == 'sent':
                running += float(tx['value'])
            else:
                running -= float(tx['value'])
            tx['running_balance'] = running
        
        logger.info(f"{self.name}: Built {len(all_txs)} total transactions")
        return all_txs


# Pre-configured chain analyzers
def create_ethereum_analyzer():
    api_key = os.environ.get('ALCHEMY_API_KEY', '')
    return EVMChainAnalyzer({
        'chain_id': 'ethereum',
        'name': 'Ethereum',
        'symbol': 'ETH',
        'decimals': 18,
        'alchemy_url': f"https://eth-mainnet.g.alchemy.com/v2/{api_key}",
        'explorer': 'https://etherscan.io'
    })

def create_polygon_analyzer():
    api_key = os.environ.get('ALCHEMY_API_KEY', '')
    return EVMChainAnalyzer({
        'chain_id': 'polygon',
        'name': 'Polygon',
        'symbol': 'MATIC',
        'decimals': 18,
        'alchemy_url': f"https://polygon-mainnet.g.alchemy.com/v2/{api_key}",
        'explorer': 'https://polygonscan.com'
    })

def create_arbitrum_analyzer():
    api_key = os.environ.get('ALCHEMY_API_KEY', '')
    return EVMChainAnalyzer({
        'chain_id': 'arbitrum',
        'name': 'Arbitrum',
        'symbol': 'ETH',
        'decimals': 18,
        'alchemy_url': f"https://arb-mainnet.g.alchemy.com/v2/{api_key}",
        'explorer': 'https://arbiscan.io'
    })

def create_bsc_analyzer():
    api_key = os.environ.get('ALCHEMY_API_KEY', '')
    return EVMChainAnalyzer({
        'chain_id': 'bsc',
        'name': 'BNB Smart Chain',
        'symbol': 'BNB',
        'decimals': 18,
        'alchemy_url': f"https://bnb-mainnet.g.alchemy.com/v2/{api_key}",
        'explorer': 'https://bscscan.com'
    })

def create_avalanche_analyzer():
    api_key = os.environ.get('ALCHEMY_API_KEY', '')
    return EVMChainAnalyzer({
        'chain_id': 'avalanche',
        'name': 'Avalanche C-Chain',
        'symbol': 'AVAX',
        'decimals': 18,
        'alchemy_url': f"https://avax-mainnet.g.alchemy.com/v2/{api_key}",
        'explorer': 'https://snowtrace.io'
    })

def create_optimism_analyzer():
    api_key = os.environ.get('ALCHEMY_API_KEY', '')
    return EVMChainAnalyzer({
        'chain_id': 'optimism',
        'name': 'Optimism',
        'symbol': 'ETH',
        'decimals': 18,
        'alchemy_url': f"https://opt-mainnet.g.alchemy.com/v2/{api_key}",
        'explorer': 'https://optimistic.etherscan.io'
    })

def create_base_analyzer():
    api_key = os.environ.get('ALCHEMY_API_KEY', '')
    return EVMChainAnalyzer({
        'chain_id': 'base',
        'name': 'Base',
        'symbol': 'ETH',
        'decimals': 18,
        'alchemy_url': f"https://base-mainnet.g.alchemy.com/v2/{api_key}",
        'explorer': 'https://basescan.org'
    })

def create_fantom_analyzer():
    api_key = os.environ.get('ALCHEMY_API_KEY', '')
    return EVMChainAnalyzer({
        'chain_id': 'fantom',
        'name': 'Fantom',
        'symbol': 'FTM',
        'decimals': 18,
        'alchemy_url': f"https://fantom-mainnet.g.alchemy.com/v2/{api_key}",
        'explorer': 'https://ftmscan.com'
    })

