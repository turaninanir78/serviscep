"""Telefon + OTP ile kayit (request-otp -> verify-otp -> complete), esnek
giris (email VEYA telefon) ve profilden e-posta ekleme testleri.

Diger auth test dosyalariyla ayni yaklasim: calisan sunucuya
(http://localhost:8000) gercek HTTP istekleri, DB temizligi email/phone
uzerinden manuel (bkz. test_mobile_auth.py, test_auth_cookie.py).

OTP kodu, bu test ortaminda (ENVIRONMENT != production, varsayilan)
response'taki "debug_code" alanindan okunuyor - bkz.
app/otp.py::OTP_DEBUG_ECHO_ENABLED. Gercek MOCK SMS/EMAIL log satirlarinin
gorevin GERCEK kabul kriteri oldugu manuel/tarayici E2E dogrulamasi ayrica
`docker compose logs backend` ile yapildi (bkz. gorev ozeti) - otomatik
testler icin log-scraping yerine debug_code kullanmak gerekliydi, cunku
gercek bir SMS/e-posta saglayicisi yok.
"""
import random
import string
import uuid
from datetime import datetime, timedelta, timezone

import requests

from app.db import SessionLocal
from app.models import OtpCode, Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _unique_email() -> str:
    return f"phone-auth-test-{uuid.uuid4().hex}@example.com"


def _cleanup_by_phone(phone_raw: str) -> None:
    normalized = normalize_phone(COUNTRY_CODE, phone_raw)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone == normalized).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
            db.commit()
    finally:
        db.close()


def _cleanup_by_email(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
            db.commit()
    finally:
        db.close()


def _request_otp(phone_raw: str) -> dict:
    res = requests.post(
        f"{BASE_URL}/auth/register/request-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _verify_otp(phone_raw: str, code: str) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/auth/register/verify-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw, "code": code},
    )


def _wrong_code(correct_code: str) -> str:
    return "000000" if correct_code != "000000" else "111111"


def _register_full_flow(phone_raw: str, tenant_name: str, password: str, session: requests.Session):
    otp_body = _request_otp(phone_raw)
    verify_res = _verify_otp(phone_raw, otp_body["debug_code"])
    assert verify_res.status_code == 200, verify_res.text
    registration_token = verify_res.json()["registration_token"]

    return session.post(
        f"{BASE_URL}/auth/register/complete",
        json={
            "registration_token": registration_token,
            "tenant_name": tenant_name,
            "password": password,
            "accepted_terms": True,
        },
    )


def test_full_register_flow_creates_account_with_phone_and_null_email():
    phone_raw = _random_phone_raw()
    try:
        session = requests.Session()
        complete_res = _register_full_flow(phone_raw, "Telefon Test Tenant", "S3cret-pw!", session)
        assert complete_res.status_code == 201
        assert session.cookies.get("access_token") is not None

        me = session.get(f"{BASE_URL}/auth/me")
        assert me.status_code == 200
        body = me.json()
        assert body["phone"] == normalize_phone(COUNTRY_CODE, phone_raw)
        assert body["email"] is None
        assert body["role"] == "owner"
    finally:
        _cleanup_by_phone(phone_raw)


def test_wrong_otp_code_is_rejected_and_does_not_issue_token():
    phone_raw = _random_phone_raw()
    try:
        otp_body = _request_otp(phone_raw)
        res = _verify_otp(phone_raw, _wrong_code(otp_body["debug_code"]))
        assert res.status_code == 400
    finally:
        _cleanup_by_phone(phone_raw)


def test_expired_code_is_rejected():
    phone_raw = _random_phone_raw()
    try:
        otp_body = _request_otp(phone_raw)
        normalized = normalize_phone(COUNTRY_CODE, phone_raw)

        db = SessionLocal()
        try:
            otp = (
                db.query(OtpCode)
                .filter(OtpCode.purpose == "register_phone", OtpCode.target == normalized)
                .order_by(OtpCode.created_at.desc())
                .first()
            )
            otp.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        finally:
            db.close()

        res = _verify_otp(phone_raw, otp_body["debug_code"])
        assert res.status_code == 400
    finally:
        _cleanup_by_phone(phone_raw)


def test_requesting_otp_twice_quickly_hits_resend_cooldown():
    phone_raw = _random_phone_raw()
    try:
        first = requests.post(
            f"{BASE_URL}/auth/register/request-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
        )
        assert first.status_code == 200

        second = requests.post(
            f"{BASE_URL}/auth/register/request-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
        )
        assert second.status_code == 429
    finally:
        _cleanup_by_phone(phone_raw)


def test_exceeding_max_attempts_locks_out_even_the_correct_code():
    phone_raw = _random_phone_raw()
    try:
        otp_body = _request_otp(phone_raw)
        correct_code = otp_body["debug_code"]
        wrong_code = _wrong_code(correct_code)

        for _ in range(5):
            res = _verify_otp(phone_raw, wrong_code)
            assert res.status_code == 400

        # 5 yanlis denemeden sonra artik DOGRU kod bile kabul edilmemeli -
        # yeni kod istenmesi gerekiyor.
        res = _verify_otp(phone_raw, correct_code)
        assert res.status_code == 400
    finally:
        _cleanup_by_phone(phone_raw)


def test_login_with_phone_works_regardless_of_leading_zero():
    phone_raw = _random_phone_raw()
    try:
        session = requests.Session()
        complete_res = _register_full_flow(phone_raw, "Login Phone Tenant", "S3cret-pw!", session)
        assert complete_res.status_code == 201

        without_zero = phone_raw.lstrip("0")
        res = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": without_zero, "password": "S3cret-pw!"},
        )
        assert res.status_code == 200
    finally:
        _cleanup_by_phone(phone_raw)


def test_legacy_email_only_account_still_logs_in_with_email():
    """Eski (telefon-oncesi) hesaplarin bozulmadigini dogrulayan regresyon
    testi - /auth/register (eski akis) ile olusan bir hesap, yeni
    email_or_phone alanina email vererek hala giris yapabilmeli."""
    email = _unique_email()
    try:
        register_res = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "tenant_name": "Legacy Email Tenant",
                "email": email,
                "password": "S3cret-pw!",
                "accepted_terms": True,
            },
        )
        assert register_res.status_code == 201

        res = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": email, "password": "S3cret-pw!"},
        )
        assert res.status_code == 200
    finally:
        _cleanup_by_email(email)


def test_profile_add_email_flow_lets_phone_account_gain_email_login():
    phone_raw = _random_phone_raw()
    email = _unique_email()
    try:
        session = requests.Session()
        complete_res = _register_full_flow(phone_raw, "Add Email Tenant", "S3cret-pw!", session)
        assert complete_res.status_code == 201

        req_res = session.post(
            f"{BASE_URL}/auth/profile/request-email-otp", json={"email": email}
        )
        assert req_res.status_code == 200
        code = req_res.json()["debug_code"]

        verify_res = session.post(
            f"{BASE_URL}/auth/profile/verify-email", json={"email": email, "code": code}
        )
        assert verify_res.status_code == 200
        assert verify_res.json()["email"] == email

        # Artik HEM telefon HEM (yeni eklenen) email ile giris yapilabilmeli.
        login_with_email = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": email, "password": "S3cret-pw!"},
        )
        assert login_with_email.status_code == 200

        login_with_phone = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": phone_raw.lstrip("0"), "password": "S3cret-pw!"},
        )
        assert login_with_phone.status_code == 200
    finally:
        _cleanup_by_phone(phone_raw)


def test_profile_email_endpoints_require_authentication():
    res = requests.post(
        f"{BASE_URL}/auth/profile/request-email-otp", json={"email": "someone@example.com"}
    )
    assert res.status_code == 401


def test_requesting_otp_for_already_registered_phone_does_not_leak_registration_status():
    """Guvenlik duzeltmesi: kayitli bir numara icin OTP istemek, kayitsiz
    bir numarayla AYNI 200 yanitini dondurmeli (eskiden 409 donerek
    numaranin kayitli olup olmadigini disariya sizdiriyordu) - ayrica
    gercek/kullanilabilir bir OTP da uretilmemeli (debug_code None)."""
    phone_raw = _random_phone_raw()
    try:
        session = requests.Session()
        complete_res = _register_full_flow(phone_raw, "Duplicate Phone Tenant", "S3cret-pw!", session)
        assert complete_res.status_code == 201

        res = requests.post(
            f"{BASE_URL}/auth/register/request-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
        )
        assert res.status_code == 200
        assert res.json()["debug_code"] is None
    finally:
        _cleanup_by_phone(phone_raw)
