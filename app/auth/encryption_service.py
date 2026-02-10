import base64

from cryptography.fernet import Fernet
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from fastapi import HTTPException


class EncryptionService:
    def __init__(self, password: str = None, salt: bytes = None):
        if password is None:
            raise ValueError("Encryption key must be provided")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend()
        )

        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        token = self.cipher.encrypt(plaintext.encode())
        return token.decode()

    def decrypt(self, token: str) -> str:
        plaintext = self.cipher.decrypt(token.encode())
        return plaintext.decode()

def get_encryption_service() -> EncryptionService:
    key = os.getenv("ENCRYPTION_KEY")
    if key is None:
        raise HTTPException(status_code=500, detail="No encryption key provided")
    
    return EncryptionService(key, salt=b'\x00' * 16)
