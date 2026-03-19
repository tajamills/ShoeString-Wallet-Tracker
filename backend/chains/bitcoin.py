"""
Bitcoin Chain Analyzer
"""
import requests
import logging
from typing import Dict, List, Any, Optional
from decimal import Decimal
from .base import BaseChainAnalyzer

logger = logging.getLogger(__name__)


class BitcoinAnalyzer(BaseChainAnalyzer):
    """Analyzer for Bitcoin blockchain"""
    
    def __init__(self):
        super().__init__({
            'chain_id': 'bitcoin',
            'name': 'Bitcoin',
            'symbol': 'BTC',
            'decimals': 8,
            'explorer': 'https://blockchain.info'
        })
        self.api_url = "https://blockchain.info"
        self.blockstream_url = "https://blockstream.info/api"
    
    def validate_address(self, address: str) -> bool:
        """Validate Bitcoin address format"""
        # Legacy (1...), SegWit (3...), Native SegWit (bc1...)
        if address.startswith('1') or address.startswith('3') or address.startswith('bc1'):
            return True
        # xPub/yPub/zPub for HD wallets
        if address.startswith(('xpub', 'ypub', 'zpub')):
            return True
        return False
    
    def get_address_validation_error(self, address: str) -> Optional[str]:
        if address.startswith('0x'):
            return "This appears to be an EVM address (starts with 0x). Try selecting Ethereum instead."
        if not self.validate_address(address):
            return "Invalid Bitcoin address format. Use Legacy (1...), SegWit (3...), Native SegWit (bc1...), or xPub/yPub/zPub."
        return None
    
    def satoshi_to_btc(self, satoshi: int) -> float:
        """Convert Satoshi to BTC"""
        return float(Decimal(satoshi) / Decimal(10**8))
    
    def is_xpub(self, address: str) -> bool:
        """Check if address is an HD wallet extended public key"""
        return address.startswith(('xpub', 'ypub', 'zpub'))
    
    def analyze_wallet(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        user_tier: str = 'free',
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze Bitcoin wallet"""
        if self.is_xpub(address):
            if user_tier != 'pro':
                raise ValueError("xPub/HD wallet analysis is a Pro-only feature")
            return self._analyze_xpub(address, start_date, end_date)
        
        return self._analyze_single_address(address, start_date, end_date)
    
    def _analyze_single_address(
        self,
        address: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze a single Bitcoin address"""
        try:
            # Try Blockstream API first (more reliable)
            url = f"{self.blockstream_url}/address/{address}"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Get transaction history
            txs_url = f"{self.blockstream_url}/address/{address}/txs"
            txs_response = requests.get(txs_url, timeout=30)
            txs_response.raise_for_status()
            transactions = txs_response.json()
            
            # Calculate totals
            chain_stats = data.get('chain_stats', {})
            mempool_stats = data.get('mempool_stats', {})
            
            total_received = self.satoshi_to_btc(
                chain_stats.get('funded_txo_sum', 0) + mempool_stats.get('funded_txo_sum', 0)
            )
            total_sent = self.satoshi_to_btc(
                chain_stats.get('spent_txo_sum', 0) + mempool_stats.get('spent_txo_sum', 0)
            )
            
            tx_count = chain_stats.get('tx_count', 0) + mempool_stats.get('tx_count', 0)
            
            # Current balance
            current_balance = total_received - total_sent
            
            # Process recent transactions
            recent_transactions = self._process_transactions(transactions[:200], address)
            
            return self.format_analysis_result(
                address=address,
                chain='bitcoin',
                total_sent=total_sent,
                total_received=total_received,
                current_balance=current_balance,
                gas_fees=0.0,  # Bitcoin fees are included in sent amount
                outgoing_count=tx_count // 2,  # Approximate
                incoming_count=tx_count // 2,
                recent_transactions=recent_transactions
            )
            
        except requests.exceptions.RequestException:
            # Fallback to blockchain.info
            return self._analyze_via_blockchain_info(address)
        except Exception as e:
            logger.error(f"Error analyzing Bitcoin wallet: {str(e)}")
            raise Exception(f"Failed to analyze Bitcoin wallet: {str(e)}")
    
    def _analyze_via_blockchain_info(self, address: str) -> Dict[str, Any]:
        """Fallback analysis using blockchain.info API"""
        url = f"{self.api_url}/rawaddr/{address}?limit=200"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        total_received = self.satoshi_to_btc(data.get('total_received', 0))
        total_sent = self.satoshi_to_btc(data.get('total_sent', 0))
        current_balance = self.satoshi_to_btc(data.get('final_balance', 0))
        
        transactions = data.get('txs', [])
        recent_transactions = []
        
        for tx in transactions[:10]:
            tx_type = 'received'
            value = 0
            
            # Check inputs
            for inp in tx.get('inputs', []):
                prev_out = inp.get('prev_out', {})
                if prev_out.get('addr') == address:
                    tx_type = 'sent'
                    value += prev_out.get('value', 0)
            
            # Check outputs
            for out in tx.get('out', []):
                if out.get('addr') == address and tx_type != 'sent':
                    value += out.get('value', 0)
            
            recent_transactions.append({
                'hash': tx.get('hash', ''),
                'type': tx_type,
                'value': self.satoshi_to_btc(value),
                'asset': 'BTC',
                'blockNum': str(tx.get('block_height', '')),
                'timestamp': tx.get('time', 0)
            })
        
        return self.format_analysis_result(
            address=address,
            chain='bitcoin',
            total_sent=total_sent,
            total_received=total_received,
            current_balance=current_balance,
            outgoing_count=data.get('n_tx', 0) // 2,
            incoming_count=data.get('n_tx', 0) // 2,
            recent_transactions=recent_transactions
        )
    
    def _process_transactions(self, transactions: List[Dict], address: str) -> List[Dict]:
        """Process raw transactions into standard format"""
        result = []
        
        for tx in transactions:
            tx_type = 'received'
            value = 0
            
            # Check if we're in inputs (sending)
            for vin in tx.get('vin', []):
                if vin.get('prevout', {}).get('scriptpubkey_address') == address:
                    tx_type = 'sent'
                    value += vin.get('prevout', {}).get('value', 0)
            
            # Check outputs
            for vout in tx.get('vout', []):
                if vout.get('scriptpubkey_address') == address:
                    if tx_type != 'sent':
                        value += vout.get('value', 0)
            
            result.append({
                'hash': tx.get('txid', ''),
                'type': tx_type,
                'value': self.satoshi_to_btc(value),
                'asset': 'BTC',
                'blockNum': str(tx.get('status', {}).get('block_height', '')),
                'blockTime': tx.get('status', {}).get('block_time', 0),
                'timestamp': tx.get('status', {}).get('block_time', 0),
                'confirmed': tx.get('status', {}).get('confirmed', False)
            })
        
        return result
    
    def _analyze_xpub(
        self,
        xpub: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze Bitcoin HD wallet using xPub"""
        try:
            from bip32 import BIP32
            
            # Determine address type
            if xpub.startswith('xpub'):
                address_type = 'legacy'
            elif xpub.startswith('ypub'):
                address_type = 'p2sh-segwit'
            elif xpub.startswith('zpub'):
                address_type = 'native-segwit'
            else:
                raise ValueError("Unsupported xPub format")
            
            bip32 = BIP32.from_xpub(xpub)
            
            # Derive and check addresses
            gap_limit = 20
            addresses = []
            
            # External chain (m/0/*)
            for i in range(gap_limit):
                pubkey = bip32.get_pubkey_from_path(f"m/0/{i}")
                addr = self._pubkey_to_address(pubkey, address_type)
                addresses.append({'address': addr, 'path': f"m/0/{i}", 'type': 'external'})
            
            # Internal chain (m/1/*)
            for i in range(gap_limit):
                pubkey = bip32.get_pubkey_from_path(f"m/1/{i}")
                addr = self._pubkey_to_address(pubkey, address_type)
                addresses.append({'address': addr, 'path': f"m/1/{i}", 'type': 'internal'})
            
            # Aggregate balances
            total_received = 0.0
            total_sent = 0.0
            total_balance = 0.0
            all_transactions = []
            active_addresses = []
            
            for addr_info in addresses:
                try:
                    url = f"{self.blockstream_url}/address/{addr_info['address']}"
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        data = response.json()
                        chain_stats = data.get('chain_stats', {})
                        
                        addr_received = self.satoshi_to_btc(chain_stats.get('funded_txo_sum', 0))
                        addr_sent = self.satoshi_to_btc(chain_stats.get('spent_txo_sum', 0))
                        
                        if addr_received > 0 or addr_sent > 0:
                            total_received += addr_received
                            total_sent += addr_sent
                            active_addresses.append({
                                **addr_info,
                                'received': addr_received,
                                'sent': addr_sent,
                                'balance': addr_received - addr_sent
                            })
                            
                except Exception as e:
                    logger.debug(f"Error checking address {addr_info['address']}: {e}")
                    continue
            
            total_balance = total_received - total_sent
            
            result = self.format_analysis_result(
                address=f"HD Wallet ({xpub[:8]}...)",
                chain='bitcoin',
                total_sent=total_sent,
                total_received=total_received,
                current_balance=total_balance,
                outgoing_count=len([a for a in active_addresses if a['sent'] > 0]),
                incoming_count=len([a for a in active_addresses if a['received'] > 0])
            )
            
            # Add HD wallet specific data
            result['is_hd_wallet'] = True
            result['active_addresses'] = active_addresses
            result['total_addresses_checked'] = len(addresses)
            
            return result
            
        except ImportError:
            raise ValueError("xPub analysis requires the bip32 library")
        except Exception as e:
            logger.error(f"Error analyzing xPub: {str(e)}")
            raise Exception(f"Failed to analyze HD wallet: {str(e)}")
    
    def _pubkey_to_address(self, pubkey: bytes, address_type: str) -> str:
        """Convert public key to Bitcoin address"""
        import hashlib
        
        # SHA256 then RIPEMD160
        sha256 = hashlib.sha256(pubkey).digest()
        ripemd160 = hashlib.new('ripemd160', sha256).digest()
        
        if address_type == 'legacy':
            # P2PKH - prefix 0x00
            versioned = b'\x00' + ripemd160
            checksum = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
            return self._base58_encode(versioned + checksum)
        
        elif address_type == 'native-segwit':
            # Bech32 P2WPKH
            return self._bech32_encode('bc', 0, ripemd160)
        
        elif address_type == 'p2sh-segwit':
            # P2SH-P2WPKH
            witness_script = b'\x00\x14' + ripemd160
            script_hash = hashlib.new('ripemd160', hashlib.sha256(witness_script).digest()).digest()
            versioned = b'\x05' + script_hash
            checksum = hashlib.sha256(hashlib.sha256(versioned).digest()).digest()[:4]
            return self._base58_encode(versioned + checksum)
        
        return ""
    
    def _base58_encode(self, data: bytes) -> str:
        """Base58 encoding for Bitcoin addresses"""
        alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        num = int.from_bytes(data, 'big')
        result = ''
        while num > 0:
            num, remainder = divmod(num, 58)
            result = alphabet[remainder] + result
        
        # Handle leading zeros
        for byte in data:
            if byte == 0:
                result = '1' + result
            else:
                break
        
        return result
    
    def _bech32_encode(self, hrp: str, witver: int, witprog: bytes) -> str:
        """Bech32 encoding for native SegWit addresses"""
        CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
        
        def bech32_polymod(values):
            GEN = [0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3]
            chk = 1
            for v in values:
                b = chk >> 25
                chk = ((chk & 0x1ffffff) << 5) ^ v
                for i in range(5):
                    chk ^= GEN[i] if ((b >> i) & 1) else 0
            return chk
        
        def bech32_hrp_expand(hrp):
            return [ord(x) >> 5 for x in hrp] + [0] + [ord(x) & 31 for x in hrp]
        
        def bech32_create_checksum(hrp, data):
            values = bech32_hrp_expand(hrp) + data
            polymod = bech32_polymod(values + [0, 0, 0, 0, 0, 0]) ^ 1
            return [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
        
        def convertbits(data, frombits, tobits, pad=True):
            acc = 0
            bits = 0
            ret = []
            maxv = (1 << tobits) - 1
            for value in data:
                acc = (acc << frombits) | value
                bits += frombits
                while bits >= tobits:
                    bits -= tobits
                    ret.append((acc >> bits) & maxv)
            if pad and bits:
                ret.append((acc << (tobits - bits)) & maxv)
            return ret
        
        data = [witver] + convertbits(witprog, 8, 5)
        combined = data + bech32_create_checksum(hrp, data)
        return hrp + '1' + ''.join([CHARSET[d] for d in combined])


def create_bitcoin_analyzer():
    return BitcoinAnalyzer()
