from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

# .env file load karo
load_dotenv()

class SecurityManager:
    """AWS credentials encrypt aur decrypt karta hai"""

    def __init__(self):
        # .env se encryption key lo
        key = os.getenv('ENCRYPTION_KEY')

        if not key:
            raise ValueError("ENCRYPTION_KEY .env file mein nahi hai!")

        # Fernet object banao - ye encrypt/decrypt karega
        self.cipher = Fernet(key.encode())
        print("✅ SecurityManager ready!")

    def encrypt(self, plain_text):
        """Plain text ko encrypted text mein badlo"""
        if not plain_text:
            return None
        # String → bytes → encrypt → string
        return self.cipher.encrypt(plain_text.encode()).decode()

    def decrypt(self, encrypted_text):
        """Encrypted text ko wapas plain text mein badlo"""
        if not encrypted_text:
            return None
        try:
            # String → bytes → decrypt → string
            return self.cipher.decrypt(encrypted_text.encode()).decode()
        except Exception as e:
            print(f"❌ Decryption failed: {e}")
            return None


# Test - seedha ye file run karo to check hoga
if __name__ == '__main__':
    sm = SecurityManager()

    original = "AKIAIOSFODNN7EXAMPLE"
    print(f"Original:  {original}")

    encrypted = sm.encrypt(original)
    print(f"Encrypted: {encrypted}")

    decrypted = sm.decrypt(encrypted)
    print(f"Decrypted: {decrypted}")

    if original == decrypted:
        print("\n✅ Encryption working perfectly!")
    else:
        print("\n❌ Something wrong!")
