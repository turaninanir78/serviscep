import hashlib
import hmac
import os

from cryptography.fernet import Fernet

WHATSAPP_TOKEN_ENCRYPTION_KEY = os.environ["WHATSAPP_TOKEN_ENCRYPTION_KEY"]
_whatsapp_fernet = Fernet(WHATSAPP_TOKEN_ENCRYPTION_KEY.encode())


def encrypt_token(plaintext: str) -> str:
    return _whatsapp_fernet.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    return _whatsapp_fernet.decrypt(ciphertext.encode()).decode()


# Musteri kisisel verisi (isim, telefon) icin WhatsApp erisim token'indan
# AYRI bir anahtar - iki farkli hassasiyet sinifi (ucuncu taraf entegrasyon
# sirri vs. musteri KVKK verisi) ayni anahtari paylasirsa, biri sizarsa
# digeri de acik hale gelir. Ayri anahtarlar bu riski izole eder.
PII_ENCRYPTION_KEY = os.environ["PII_ENCRYPTION_KEY"]
_pii_fernet = Fernet(PII_ENCRYPTION_KEY.encode())


def encrypt_pii(plaintext: str) -> str:
    return _pii_fernet.encrypt(plaintext.encode()).decode()


def decrypt_pii(ciphertext: str) -> str:
    return _pii_fernet.decrypt(ciphertext.encode()).decode()


def hash_pii_lookup(plaintext: str) -> str:
    """Hassas bir alanda ESITLIK arama/index icin deterministik hash.

    Fernet (yukaridaki encrypt_pii) KASITLI OLARAK non-deterministik - ayni
    girdi her cagrida FARKLI ciphertext uretir (rastgele bir IV/nonce icerir),
    bu da veri hirsizligina karsi guclu bir ozellik ama ayni zamanda
    `WHERE encrypted_column = ?` gibi bir esitlik sorgusunu imkansiz kilar
    (bkz. app/db_types.py::EncryptedString docstring'i).

    Bu fonksiyon, PII_ENCRYPTION_KEY'den turetilen bir HMAC anahtariyla
    deterministik bir digest uretir - ayni girdi HER ZAMAN ayni hash'i
    verir, boylece bu hash ayri, indexlenebilir bir sutunda (orn.
    Customer.whatsapp_number_hash) saklanip esitlik/tekillik sorgulari icin
    kullanilabilir; asil hassas deger hala sadece sifreli formda saklanir.

    Anahtarsiz duz SHA-256 yerine HMAC kullanilmasinin sebebi: anahtarsiz
    bir hash, DB'ye erisen ama PII_ENCRYPTION_KEY'i bilmeyen birinin bile
    bilinen numaralari SHA-256'layip DB'deki hash'lerle karsilastirarak
    (rainbow table/brute-force) hangi telefon numaralarinin kayitli
    oldugunu cikarabilmesine izin verirdi. HMAC'in gizli anahtari bu riski
    ortadan kaldirir.
    """
    return hmac.new(PII_ENCRYPTION_KEY.encode(), plaintext.encode(), hashlib.sha256).hexdigest()
