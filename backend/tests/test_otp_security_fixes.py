"""GOREV: KRITIK - OTP Guvenlik Aciklari Paketi testleri.

Dort ayri duzeltmeyi kapsar:
1) notifications.py - production'da OTP kodu LOGLANMAMALI.
2) otp.py::_generate_code - kriptografik olarak guvenli (secrets) uretim.
3) auth.py::register_request_otp - kayitli telefon numarasi enumeration'i
   (bkz. test_phone_auth.py::test_requesting_otp_for_already_registered_phone_does_not_leak_registration_status
   - o test bu paketin bir parcasi, burada tekrarlanmadi).
4) otp.py::create_otp - ayni (purpose, target) icin esZAMANLI istekler
   cooldown'u atlatamamali (TOCTOU race).

Fix 1 ve 2, app/security.py::_validate_cookie_security testlerindeki
("saf fonksiyon, gercek ortami degistirmeden dogrudan/monkeypatch ile
test et") yaklasimi izler. Fix 4, test_appointment_race_condition.py'deki
canli sunucuya gercek paralel HTTP istegi atma yaklasimini izler.
"""
import logging
import random
import string
import threading
import urllib.error
import urllib.request
import json

from app import notifications, otp as otp_module
from app.db import SessionLocal
from app.models import OtpCode, Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _cleanup_by_phone(phone_raw: str) -> None:
    normalized = normalize_phone(COUNTRY_CODE, phone_raw)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone == normalized).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
        db.query(OtpCode).filter(OtpCode.target == normalized).delete()
        db.commit()
    finally:
        db.close()


# --- Duzeltme 1: production'da kod loglanmamali -----------------------


def test_send_sms_hides_code_in_production(monkeypatch, caplog):
    monkeypatch.setattr(notifications, "ENVIRONMENT", "production")
    with caplog.at_level(logging.INFO, logger="app.notifications"):
        notifications.send_sms("+905559998877", "Servisçep dogrulama kodunuz: 445566 (5 dakika gecerli)")
    assert "445566" not in caplog.text
    assert "+905559998877" in caplog.text


def test_send_email_hides_body_in_production_but_keeps_subject(monkeypatch, caplog):
    monkeypatch.setattr(notifications, "ENVIRONMENT", "production")
    with caplog.at_level(logging.INFO, logger="app.notifications"):
        notifications.send_email("user@example.com", "Dogrulama Kodu", "Kodunuz: 654321")
    assert "654321" not in caplog.text
    assert "Dogrulama Kodu" in caplog.text


def test_send_sms_still_shows_code_outside_production(monkeypatch, caplog):
    # Mevcut dev/test davranisi degismemeli - otomatik testler debug_code
    # yerine dogrudan log satirini okusaydi bile calismaya devam etmeli.
    monkeypatch.setattr(notifications, "ENVIRONMENT", "development")
    with caplog.at_level(logging.INFO, logger="app.notifications"):
        notifications.send_sms("+905559998877", "Servisçep dogrulama kodunuz: 445566 (5 dakika gecerli)")
    assert "445566" in caplog.text


def test_send_email_still_shows_body_outside_production(monkeypatch, caplog):
    monkeypatch.setattr(notifications, "ENVIRONMENT", "development")
    with caplog.at_level(logging.INFO, logger="app.notifications"):
        notifications.send_email("user@example.com", "Dogrulama Kodu", "Kodunuz: 654321")
    assert "654321" in caplog.text


# --- Duzeltme 2: kod uretimi kriptografik olarak guvenli olmali -------


def test_generate_code_uses_secrets_module_not_random(monkeypatch):
    calls = {"count": 0}
    real_choice = otp_module.secrets.choice

    def _spy_choice(seq):
        calls["count"] += 1
        return real_choice(seq)

    monkeypatch.setattr(otp_module.secrets, "choice", _spy_choice)

    code = otp_module._generate_code()

    assert calls["count"] == otp_module.OTP_CODE_LENGTH
    assert len(code) == otp_module.OTP_CODE_LENGTH
    assert code.isdigit()


# --- Duzeltme 4: esZamanli istekler cooldown'u atlatamamali -----------


def _post_request_otp(phone_raw: str, results: list, barrier: threading.Barrier) -> None:
    barrier.wait()
    req = urllib.request.Request(
        f"{BASE_URL}/auth/register/request-otp",
        data=json.dumps({"country_code": COUNTRY_CODE, "phone_number": phone_raw}).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as resp:
            results.append((resp.status, json.loads(resp.read())))
    except urllib.error.HTTPError as exc:
        results.append((exc.code, json.loads(exc.read())))


def test_concurrent_otp_requests_for_same_phone_only_one_succeeds():
    """Iki es zamanli /register/request-otp istegi, ayni (yeni) telefon
    numarasi icin ayni anda tetiklenirse: SADECE biri 200 (gercek kod)
    almali, digeri cooldown nedeniyle 429 almali. Duzeltme 4 (advisory
    lock) olmadan, ikisi de commit'ten once "son X saniyede kod yok"
    kontrolunu ayni anda gecip ikisi de 200 donebilir - bu test tam olarak
    o senaryoyu canli sunucuya gercek paralel istekle tetikler."""
    phone_raw = _random_phone_raw()
    try:
        results: list[tuple[int, dict]] = []
        barrier = threading.Barrier(2)

        threads = [
            threading.Thread(target=_post_request_otp, args=(phone_raw, results, barrier))
            for _ in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(results) == 2, f"iki yanit da donmedi: {results}"
        status_codes = sorted(code for code, _ in results)
        assert status_codes == [200, 429], f"beklenmeyen sonuc: {results}"

        normalized = normalize_phone(COUNTRY_CODE, phone_raw)
        db = SessionLocal()
        try:
            otp_count = (
                db.query(OtpCode)
                .filter(OtpCode.purpose == "register_phone", OtpCode.target == normalized)
                .count()
            )
            assert otp_count == 1, "race nedeniyle birden fazla OTP satiri olusmus olmali degil"
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)
