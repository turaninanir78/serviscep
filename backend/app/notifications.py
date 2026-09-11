"""SMS ve e-posta gonderimi - MOCK implementasyon.

Gercek Netgsm (SMS) ve SMTP (e-posta) entegrasyonu HENUZ YOK. Bu iki
fonksiyon, gercek bir saglayici baglanana kadar mesaji gondermek yerine
backend logina yaziyor - gelistirme/test sirasinda kod, terminaldeki
(veya `docker compose logs backend`) log satirindan okunabilir.

ILERIDE GERCEK SAGLAYICIYA GECERKEN: sadece bu iki fonksiyonun GOVDESI
degismeli - imzalari ((to, message) / (to, subject, body)) sabit tutulursa
cagiran taraf (app/otp.py) hic degismez.
"""
import logging

logger = logging.getLogger("app.notifications")


def send_sms(to: str, message: str) -> None:
    """MOCK: gercek Netgsm cagrisi yerine logina yazar."""
    logger.info("MOCK SMS -> %s: %s", to, message)


def send_email(to: str, subject: str, body: str) -> None:
    """MOCK: gercek SMTP cagrisi yerine logina yazar."""
    logger.info("MOCK EMAIL -> %s | subject=%s | %s", to, subject, body)
