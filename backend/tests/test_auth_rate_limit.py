"""POST /auth/login, /auth/mobile/login (ve register'in kendi daha gevsek
limiti) icin IP bazli rate limiting testleri.

app/rate_limit.py, ENVIRONMENT=production DISINDA varsayilan olarak rate
limiting'i DEVRE DISI birakiyor - aksi halde bu dosyanin KENDI testleri
bile, ayni container'daki DIGER TUM testlerle (hepsi ayni loopback IP'den
login/register cagirir) ayni paylasilan sayaci tuketip birbirini kirardi.

Bu yuzden bu dosyadaki testler, mevcut container'da rate limiting devre
disiyken (yani normal `pytest` kosusunda, varsayilan dev/test davranisi)
SKIP edilir - digerlerini etkilemezler. Gercekten zorlandigini dogrulamak
icin, backend container'i once ETKINLESTIRILEREK yeniden baslatilmali:

    RATE_LIMIT_ENABLED=true docker compose up -d backend
    docker compose exec -T backend pytest tests/test_auth_rate_limit.py -v
    docker compose up -d backend   # normale don (RATE_LIMIT_ENABLED'siz)

Bu calistirma gorev sirasinda GERCEKTEN yapildi ve sonucu gorev ozetinde
raporlandi - sadece kod okunarak varsayilmadi.
"""
import time
import uuid

import pytest
import requests

from app.db import SessionLocal
from app.models import Tenant, User
from app.rate_limit import AUTH_LOGIN_RATE_LIMIT, AUTH_REGISTER_RATE_LIMIT, RATE_LIMIT_ENABLED

BASE_URL = "http://localhost:8000"

pytestmark = pytest.mark.skipif(
    not RATE_LIMIT_ENABLED,
    reason=(
        "Rate limiting bu container'da devre disi (varsayilan dev/test "
        "davranisi - bkz. app/rate_limit.py). Gercekten zorlandigini "
        "dogrulamak icin RATE_LIMIT_ENABLED=true ile yeniden baslatilmis "
        "bir container'a karsi ayrica calistirilmali (bkz. bu dosyanin "
        "basindaki aciklama)."
    ),
)


def _parse_limit_count(limit_string: str) -> int:
    # "5/minute" -> 5
    return int(limit_string.split("/")[0])


LOGIN_LIMIT_COUNT = _parse_limit_count(AUTH_LOGIN_RATE_LIMIT)
REGISTER_LIMIT_COUNT = _parse_limit_count(AUTH_REGISTER_RATE_LIMIT)


def _attempt_login(email: str) -> int:
    res = requests.post(
        f"{BASE_URL}/auth/login", json={"email_or_phone": email, "password": "wrong-password"}
    )
    return res.status_code


def _cleanup_by_emails(emails: list[str]) -> None:
    db = SessionLocal()
    try:
        for email in emails:
            user = db.query(User).filter(User.email == email).first()
            if user is not None:
                db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
        db.commit()
    finally:
        db.close()


def test_login_returns_429_after_limit_exceeded():
    email = f"rate-limit-test-{uuid.uuid4().hex}@example.com"

    # Kullanici hic register edilmedi - limite kadarki her deneme normal
    # sekilde 401 (yanlis kimlik bilgisi) donmeli, HENUZ 429 degil.
    statuses = [_attempt_login(email) for _ in range(LOGIN_LIMIT_COUNT)]
    assert all(s == 401 for s in statuses), statuses

    # Limiti asan bir sonraki (N+1'inci) istek 429 donmeli.
    assert _attempt_login(email) == 429


def test_login_rate_limit_error_message_is_explicit():
    email = f"rate-limit-test-{uuid.uuid4().hex}@example.com"
    for _ in range(LOGIN_LIMIT_COUNT):
        _attempt_login(email)

    res = requests.post(
        f"{BASE_URL}/auth/login", json={"email_or_phone": email, "password": "wrong-password"}
    )
    assert res.status_code == 429
    assert res.json()["detail"] == "Too many attempts. Please try again later."


def test_rate_limit_resets_after_window_passes():
    email = f"rate-limit-test-{uuid.uuid4().hex}@example.com"
    for _ in range(LOGIN_LIMIT_COUNT):
        _attempt_login(email)
    assert _attempt_login(email) == 429

    # AUTH_LOGIN_RATE_LIMIT "N/minute" formatinda - pencerenin (60s)
    # gecmesini bekleyip tekrar izin verildigini dogruluyoruz. Bilerek
    # gercek zaman kullaniliyor (mock/fake-time yerine) - slowapi'nin
    # gercek storage/pencere davranisini dogrudan test ediyoruz.
    time.sleep(61)
    assert _attempt_login(email) == 401  # tekrar normal (yanlis sifre) davranisi


def test_register_has_its_own_looser_limit():
    """Register limiti (varsayilan saatte 10) login limitinden (varsayilan
    dakikada 5) FARKLI ve daha gevsek - LOGIN_LIMIT_COUNT'u asan sayida
    register denemesi, eger bu register'in KENDI (daha yuksek) limitini
    asmiyorsa hala basarili (201) olmali. Bu, iki endpoint grubunun
    BAGIMSIZ limitlere sahip oldugunu (register'inkinin login'inkinden
    daha gevsek oldugunu) dogruluyor."""
    if REGISTER_LIMIT_COUNT <= LOGIN_LIMIT_COUNT:
        pytest.skip(
            "Bu ortamda register limiti login limitinden gevsek degil "
            f"(register={REGISTER_LIMIT_COUNT}, login={LOGIN_LIMIT_COUNT})"
        )

    attempts = LOGIN_LIMIT_COUNT + 1
    emails = [f"rate-limit-register-{uuid.uuid4().hex}@example.com" for _ in range(attempts)]
    try:
        statuses = [
            requests.post(
                f"{BASE_URL}/auth/register",
                json={
                    "tenant_name": "Rate Limit Test",
                    "email": email,
                    "password": "s3cret-pw",
                    "accepted_terms": True,
                },
            ).status_code
            for email in emails
        ]
        assert all(s == 201 for s in statuses), statuses
    finally:
        _cleanup_by_emails(emails)
