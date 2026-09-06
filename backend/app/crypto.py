import os

from cryptography.fernet import Fernet

WHATSAPP_TOKEN_ENCRYPTION_KEY = os.environ["WHATSAPP_TOKEN_ENCRYPTION_KEY"]
_fernet = Fernet(WHATSAPP_TOKEN_ENCRYPTION_KEY.encode())


def encrypt_token(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()
