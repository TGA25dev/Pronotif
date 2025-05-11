from cryptography.fernet import Fernet
import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class EncryptionManager:
    """Manages encryption/decryption operations for sensitive data"""
    
    def __init__(self):
        self.cipher_suite = None
        self.initialize_encryption()
    
    def initialize_encryption(self) -> None:
        """Initialize encryption key - either load existing or generate new one"""
        
        # Load variables
        load_dotenv()
        key_var = os.getenv('ENCRYPTION_KEY')
        
        if not key_var:
            logger.warning("No encryption key found in environment. Generating a new one.")
            key = Fernet.generate_key()
            logger.critical(key.decode())
            self.cipher_suite = Fernet(key)
            return
        
        try:
            # If stored as a string, encode it
            if isinstance(key_var, str):
                key_var = key_var.encode()
            self.cipher_suite = Fernet(key_var)
            logger.info("Encryption system initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing encryption key: {e}")
            raise
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext data"""
        if not plaintext:
            return None
        
        if not self.cipher_suite:
            raise ValueError("Encryption system not initialized")
        
        try:
            if isinstance(plaintext, str):
                plaintext = plaintext.encode('utf-8')
            
            return self.cipher_suite.encrypt(plaintext).decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            raise
    
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext data"""
        if not ciphertext:
            return None
        
        if not self.cipher_suite:
            raise ValueError("Encryption system not initialized")
        
        try:
            if isinstance(ciphertext, str):
                ciphertext = ciphertext.encode('utf-8')
            
            return self.cipher_suite.decrypt(ciphertext).decode('utf-8')
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            raise

# Create a singleton instance
encryption_manager = EncryptionManager()

# Export functions for use
encrypt = encryption_manager.encrypt
decrypt = encryption_manager.decrypt