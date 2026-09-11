"""SMS ve e-posta gonderimi - MOCK implementasyon.

Gercek Netgsm (SMS) ve SMTP (e-posta) entegrasyonu HENUZ YOK. Bu iki
fonksiyon, gercek bir saglayici baglanana kadar mesaji gondermek yerine
backend logina yaziyor - gelistirme/test sirasinda kod, terminaldeki
(veya `docker compose logs backend`) log satirindan okunabilir.

GUVENLIK (bkz. gorev ozeti - Duzeltme 1): `message`/`body` OTP kodu gibi
GIZLI bilgi tasiyabilir - ENVIRONMENT=production'da bu asla loglanmaz,
sadece gonderim OLAYI (hedef, opsiyonel konu) loglanir. Bu ayrim SADECE
`debug_code` API alanini (bkz. app/otp.py::OTP_DEBUG_ECHO_ENABLED)
kapatmakla YETINMEZ - production ortaminda kod, log dosyasina erisebilen
biri icin de tamamen gorunmez olmali.

ILERIDE GERCEK SAGLAYICIYA GECERKEN: sadece bu iki fonksiyonun GOVDESI
degismeli - imzalari ((to, message) / (to, subject, body)) sabit tutulursa
cagiran taraf (app/otp.py) hic degismez.
"""
import logging

from app.security import ENVIRONMENT

logger = logging.getLogger("app.notifications")


def send_sms(to: str, message: str) -> None:
    """MOCK: gercek Netgsm cagrisi yerine logina yazar (production'da
    mesaj METNI HARIC)."""
    if ENVIRONMENT == "production":
        logger.info("MOCK SMS gonderildi -> %s", to)
    else:
        logger.info("MOCK SMS -> %s: %s", to, message)


def send_email(to: str, subject: str, body: str) -> None:
    """MOCK: gercek SMTP cagrisi yerine logina yazar (production'da govde
    METNI HARIC - konu basligi gizli bilgi tasimadigi icin loglanmaya
    devam eder)."""
    if ENVIRONMENT == "production":
        logger.info("MOCK EMAIL gonderildi -> %s | subject=%s", to, subject)
    else:
        logger.info("MOCK EMAIL -> %s | subject=%s | %s", to, subject, body)
