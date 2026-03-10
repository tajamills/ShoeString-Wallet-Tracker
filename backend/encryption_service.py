"""
Encryption Service for Secure API Key Storage
Uses Fernet symmetric encryption for storing sensitive credentials.
"""
import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.
    Uses Fernet symmetric encryption with a key derived from an environment variable.
    """
    
    def __init__(self):
        self._fernet = None
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize the Fernet cipher with a derived key."""
        # Get the master key from environment (or generate one)
        master_key = os.environ.get('ENCRYPTION_KEY')
        
        if not master_key:
            # For development, generate a key (in production, this MUST be set)
            logger.warning(
                "ENCRYPTION_KEY not set in environment. "
                "Generating temporary key. SET THIS IN PRODUCTION!"
            )
            master_key = Fernet.generate_key().decode()
            os.environ['ENCRYPTION_KEY'] = master_key
        
        # Derive a proper Fernet key from the master key
        # This allows using any string as the master key
        try:
            # If it's already a valid Fernet key, use it directly
            self._fernet = Fernet(master_key.encode() if isinstance(master_key, str) else master_key)
        except Exception:
            # Derive a key from the master key using PBKDF2
            salt = b'crypto_bag_tracker_salt_v1'  # Static salt (could be per-user for more security)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
            self._fernet = Fernet(key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""
        
        try:
            encrypted = self._fernet.encrypt(plaintext.encode())
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError("Failed to encrypt data")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: The encrypted string to decrypt
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ""
        
        try:
            decrypted = self._fernet.decrypt(ciphertext.encode())
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Failed to decrypt data - key may have changed")
    
    def encrypt_dict(self, data: dict, fields_to_encrypt: list) -> dict:
        """
        Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing data
            fields_to_encrypt: List of field names to encrypt
            
        Returns:
            New dictionary with specified fields encrypted
        """
        result = data.copy()
        for field in fields_to_encrypt:
            if field in result and result[field]:
                result[field] = self.encrypt(str(result[field]))
        return result
    
    def decrypt_dict(self, data: dict, fields_to_decrypt: list) -> dict:
        """
        Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            fields_to_decrypt: List of field names to decrypt
            
        Returns:
            New dictionary with specified fields decrypted
        """
        result = data.copy()
        for field in fields_to_decrypt:
            if field in result and result[field]:
                try:
                    result[field] = self.decrypt(str(result[field]))
                except ValueError:
                    # Field might not be encrypted (legacy data)
                    logger.warning(f"Could not decrypt field {field}, using as-is")
        return result
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.
        Use this to generate ENCRYPTION_KEY for production.
        
        Returns:
            A new Fernet key as a string
        """
        return Fernet.generate_key().decode()


# Global service instance
encryption_service = EncryptionService()


# Utility function to generate a new key (run once for production setup)
if __name__ == "__main__":
    print("New encryption key for ENCRYPTION_KEY environment variable:")
    print(EncryptionService.generate_key())
