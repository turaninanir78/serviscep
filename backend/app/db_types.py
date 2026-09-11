from sqlalchemy.types import Text, TypeDecorator

from app.crypto import decrypt_pii, encrypt_pii


class EncryptedString(TypeDecorator):
    """Uygulama katmaninda SIRADAN bir string kolonu gibi davranan, ama
    DB'de HER ZAMAN Fernet-sifreli (ciphertext) saklanan bir SQLAlchemy tipi.

    Bir modeldeki tek degisiklik `Column(String(...))` -> `Column(EncryptedString)`
    olmasi - geri kalan tum uygulama kodu (Pydantic semalari, servisler,
    webhook isleyicileri) HICBIR SEY DEGISTIRMEDEN calismaya devam eder:
    okurken otomatik desifre edilir (API yanitlari hala duz metin doner),
    yazarken otomatik sifrelenir.

    ONEMLI: Fernet KASITLI OLARAK non-deterministik (ayni girdi her
    seferinde farkli ciphertext uretir) - bu yuzden bu tipteki bir kolonda
    esitlik sorgusu (`WHERE col = ?`, dolayisiyla `Model.col == value` ORM
    filtresi de) ASLA eslesmez. Esitlik/arama/tekillik gerekiyorsa (bkz.
    Customer.whatsapp_number_hash), AYRI, deterministik bir hash sutunu
    (app.crypto.hash_pii_lookup) kullanilmali.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_pii(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt_pii(value)
