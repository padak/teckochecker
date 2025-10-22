"""Encryption utilities for securing secrets."""

from cryptography.fernet import Fernet
from base64 import urlsafe_b64encode
import hashlib


class EncryptionService:
    """Service for encrypting and decrypting secrets."""

    def __init__(self, secret_key: str):
        """
        Initialize encryption service with a secret key.
        
        Args:
            secret_key: Master secret key for encryption
        """
        # Derive a 32-byte key from the secret key
        key = hashlib.sha256(secret_key.encode()).digest()
        # Fernet requires base64-encoded 32-byte key
        fernet_key = urlsafe_b64encode(key)
        self.fernet = Fernet(fernet_key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string.
        
        Args:
            plaintext: The string to encrypt
            
        Returns:
            Encrypted string (base64-encoded)
        """
        encrypted_bytes = self.fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.
        
        Args:
            ciphertext: The encrypted string (base64-encoded)
            
        Returns:
            Decrypted plaintext string
        """
        decrypted_bytes = self.fernet.decrypt(ciphertext.encode())
        return decrypted_bytes.decode()


# Global encryption service instance
_encryption_service: EncryptionService = None


def init_encryption_service(secret_key: str) -> EncryptionService:
    """Initialize the global encryption service."""
    global _encryption_service
    _encryption_service = EncryptionService(secret_key)
    return _encryption_service


def get_encryption_service() -> EncryptionService:
    """Get the global encryption service instance."""
    if _encryption_service is None:
        raise RuntimeError("Encryption service not initialized")
    return _encryption_service
