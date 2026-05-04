from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class SecurityManager:
    """Handles encryption and decryption of AWS credentials"""

    def __init__(self):
        # Load encryption key from environment variable
        key = os.getenv('ENCRYPTION_KEY')

        if not key:
            raise ValueError("ENCRYPTION_KEY is missing from .env file!")

        # Initialize Fernet cipher for encryption/decryption
        self.cipher = Fernet(key.encode())
        print("SecurityManager ready!")

    def encrypt(self, plain_text):
        """Encrypt plain text and return encrypted string"""
        if not plain_text:
            return None
        # String -> bytes -> encrypt -> string
        return self.cipher.encrypt(plain_text.encode()).decode()

    def decrypt(self, encrypted_text):
        """Decrypt encrypted text and return plain string"""
        if not encrypted_text:
            return None
        try:
            # String -> bytes -> decrypt -> string
            return self.cipher.decrypt(encrypted_text.encode()).decode()
        except Exception as e:
            print(f"Decryption failed: {e}")
            return None


# Run this file directly to test encryption
if __name__ == '__main__':
    sm = SecurityManager()

    original = "AKIAIOSFODNN7EXAMPLE"
    print(f"Original:  {original}")

    encrypted = sm.encrypt(original)
    print(f"Encrypted: {encrypted}")

    decrypted = sm.decrypt(encrypted)
    print(f"Decrypted: {decrypted}")

    if original == decrypted:
        print("\nEncryption working perfectly!")
    else:
        print("\nSomething went wrong!")
