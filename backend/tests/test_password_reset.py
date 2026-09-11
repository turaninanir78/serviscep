"""GOREV: Sifremi Unuttum - Telefon+OTP ile Sifre Sifirlama (Kanal Secimli)
testleri.

Kayittaki OTP mekanizmasi (app/otp.py::create_otp/verify_otp) AYNEN
yeniden kullaniliyor, sadece purpose="password_reset" ile ayirt ediliyor -
bkz. app/api/auth.py'deki ilgili endpoint'lerin ustundeki yorum.

Diger auth test dosyalariyla ayni yaklasim: calisan sunucuya
(http://localhost:8000) gercek HTTP istekleri, DB temizligi telefon
uzerinden manuel (bkz. test_phone_auth.py).
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
    return f"password-reset-test-{uuid.uuid4().hex}@example.com"


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


def _register_phone_only_user(phone_raw: str, tenant_name: str, password: str) -> None:
    otp_res = requests.post(
        f"{BASE_URL}/auth/register/request-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
    )
    assert otp_res.status_code == 200, otp_res.text
    code = otp_res.json()["debug_code"]

    verify_res = requests.post(
        f"{BASE_URL}/auth/register/verify-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw, "code": code},
    )
    assert verify_res.status_code == 200, verify_res.text
    registration_token = verify_res.json()["registration_token"]

    complete_res = requests.post(
        f"{BASE_URL}/auth/register/complete",
        json={
            "registration_token": registration_token,
            "tenant_name": tenant_name,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert complete_res.status_code == 201, complete_res.text


def _register_phone_and_email_user(
    phone_raw: str, tenant_name: str, password: str, email: str
) -> None:
    _register_phone_only_user(phone_raw, tenant_name, password)

    session = requests.Session()
    login_res = session.post(
        f"{BASE_URL}/auth/login",
        json={"email_or_phone": phone_raw.lstrip("0"), "password": password},
    )
    assert login_res.status_code == 200, login_res.text

    req_res = session.post(f"{BASE_URL}/auth/profile/request-email-otp", json={"email": email})
    assert req_res.status_code == 200, req_res.text
    code = req_res.json()["debug_code"]

    verify_res = session.post(
        f"{BASE_URL}/auth/profile/verify-email", json={"email": email, "code": code}
    )
    assert verify_res.status_code == 200, verify_res.text


def _request_reset_otp(phone_raw: str, channel: str | None = None) -> requests.Response:
    body = {"country_code": COUNTRY_CODE, "phone_number": phone_raw}
    if channel is not None:
        body["channel"] = channel
    return requests.post(f"{BASE_URL}/auth/password-reset/request-otp", json=body)


def _verify_reset_otp(phone_raw: str, code: str) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/auth/password-reset/verify-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw, "code": code},
    )


def _complete_reset(reset_token: str, new_password: str) -> requests.Response:
    return requests.post(
        f"{BASE_URL}/auth/password-reset/complete",
        json={"reset_token": reset_token, "new_password": new_password},
    )


# --- Kanal secimi ---


def test_phone_only_user_gets_automatic_sms_with_code_immediately():
    phone_raw = _random_phone_raw()
    try:
        _register_phone_only_user(phone_raw, "Reset SMS Only Tenant", "S3cret-pw!")

        res = _request_reset_otp(phone_raw)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["channel_choice_required"] is False
        assert body["available_channels"] == ["sms"]
        assert body["debug_code"] is not None
    finally:
        _cleanup_by_phone(phone_raw)


def test_user_with_verified_email_is_offered_channel_choice_without_sending_code():
    phone_raw = _random_phone_raw()
    email = _unique_email()
    try:
        _register_phone_and_email_user(phone_raw, "Reset Channel Choice Tenant", "S3cret-pw!", email)

        res = _request_reset_otp(phone_raw)
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["channel_choice_required"] is True
        assert sorted(body["available_channels"]) == ["email", "sms"]
        # Kanal henuz secilmedigi icin GERCEK bir kod uretilmemis olmali.
        assert body["debug_code"] is None

        normalized = normalize_phone(COUNTRY_CODE, phone_raw)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone == normalized).first()
            otp_count = (
                db.query(OtpCode)
                .filter(OtpCode.purpose == "password_reset", OtpCode.target == f"user:{user.id}")
                .count()
            )
            assert otp_count == 0
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)


def test_user_with_verified_email_can_pick_sms_channel():
    phone_raw = _random_phone_raw()
    email = _unique_email()
    try:
        _register_phone_and_email_user(phone_raw, "Reset Pick Sms Tenant", "S3cret-pw!", email)

        res = _request_reset_otp(phone_raw, channel="sms")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["channel_choice_required"] is False
        assert body["debug_code"] is not None
    finally:
        _cleanup_by_phone(phone_raw)


def test_user_with_verified_email_can_pick_email_channel():
    phone_raw = _random_phone_raw()
    email = _unique_email()
    try:
        _register_phone_and_email_user(phone_raw, "Reset Pick Email Tenant", "S3cret-pw!", email)

        res = _request_reset_otp(phone_raw, channel="email")
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["channel_choice_required"] is False
        assert body["debug_code"] is not None

        # Secilen kanaldan bagimsiz olarak dogru kod HER ZAMAN dogrulanabilmeli.
        verify_res = _verify_reset_otp(phone_raw, body["debug_code"])
        assert verify_res.status_code == 200, verify_res.text
    finally:
        _cleanup_by_phone(phone_raw)


def test_unregistered_phone_does_not_leak_via_request_otp():
    """Kayitsiz bir numara icin de, telefon-sadece bir kullaniciyla AYNI
    yanit sekli donmeli (bkz. otp-security-fixes gorev ozeti - Duzeltme 3
    ile ayni desen) - gercek bir kod uretilmez."""
    phone_raw = _random_phone_raw()
    res = _request_reset_otp(phone_raw)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["channel_choice_required"] is False
    assert body["available_channels"] == ["sms"]
    assert body["debug_code"] is None


def test_verify_otp_for_unregistered_phone_returns_generic_error():
    phone_raw = _random_phone_raw()
    res = _verify_reset_otp(phone_raw, "123456")
    assert res.status_code == 400
    assert res.json()["detail"] == "Kod bulunamadi veya suresi dolmus. Yeni kod isteyin."


# --- Dogru/yanlis/suresi dolmus kod ---


def test_wrong_reset_code_is_rejected():
    phone_raw = _random_phone_raw()
    try:
        _register_phone_only_user(phone_raw, "Reset Wrong Code Tenant", "S3cret-pw!")
        otp_res = _request_reset_otp(phone_raw)
        correct_code = otp_res.json()["debug_code"]
        wrong_code = "000000" if correct_code != "000000" else "111111"

        res = _verify_reset_otp(phone_raw, wrong_code)
        assert res.status_code == 400
    finally:
        _cleanup_by_phone(phone_raw)


def test_expired_reset_code_is_rejected():
    phone_raw = _random_phone_raw()
    try:
        _register_phone_only_user(phone_raw, "Reset Expired Tenant", "S3cret-pw!")
        otp_res = _request_reset_otp(phone_raw)
        code = otp_res.json()["debug_code"]
        normalized = normalize_phone(COUNTRY_CODE, phone_raw)

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone == normalized).first()
            otp = (
                db.query(OtpCode)
                .filter(OtpCode.purpose == "password_reset", OtpCode.target == f"user:{user.id}")
                .order_by(OtpCode.created_at.desc())
                .first()
            )
            otp.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        finally:
            db.close()

        res = _verify_reset_otp(phone_raw, code)
        assert res.status_code == 400
    finally:
        _cleanup_by_phone(phone_raw)


# --- Uctan uca akis + tek kullanimlik token ---


def test_full_reset_flow_changes_password_and_old_password_stops_working():
    phone_raw = _random_phone_raw()
    try:
        _register_phone_only_user(phone_raw, "Reset E2E Tenant", "Old-pw1!")

        otp_res = _request_reset_otp(phone_raw)
        code = otp_res.json()["debug_code"]

        verify_res = _verify_reset_otp(phone_raw, code)
        assert verify_res.status_code == 200, verify_res.text
        reset_token = verify_res.json()["reset_token"]

        complete_res = _complete_reset(reset_token, "New-pw1!")
        assert complete_res.status_code == 204, complete_res.text

        national = phone_raw.lstrip("0")
        old_login = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": national, "password": "Old-pw1!"},
        )
        assert old_login.status_code == 401

        new_login = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": national, "password": "New-pw1!"},
        )
        assert new_login.status_code == 200
    finally:
        _cleanup_by_phone(phone_raw)


def test_reset_token_is_single_use():
    phone_raw = _random_phone_raw()
    try:
        _register_phone_only_user(phone_raw, "Reset Single Use Tenant", "Old-pw1!")

        otp_res = _request_reset_otp(phone_raw)
        code = otp_res.json()["debug_code"]
        verify_res = _verify_reset_otp(phone_raw, code)
        reset_token = verify_res.json()["reset_token"]

        first = _complete_reset(reset_token, "New-pw1!")
        assert first.status_code == 204, first.text

        # AYNI reset_token ikinci kez kullanilmaya calisilirsa reddedilmeli -
        # sifre zaten degisti, token'in parmak izi artik eskimis olmali.
        second = _complete_reset(reset_token, "Another-pw1!")
        assert second.status_code == 400

        # Ikinci deneme basarisiz oldugu icin sifre HALA ilk yeni sifre olmali.
        national = phone_raw.lstrip("0")
        login_with_first_new_password = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": national, "password": "New-pw1!"},
        )
        assert login_with_first_new_password.status_code == 200
    finally:
        _cleanup_by_phone(phone_raw)


def test_weak_new_password_is_rejected_by_password_policy():
    phone_raw = _random_phone_raw()
    try:
        _register_phone_only_user(phone_raw, "Reset Weak Password Tenant", "Old-pw1!")

        otp_res = _request_reset_otp(phone_raw)
        code = otp_res.json()["debug_code"]
        verify_res = _verify_reset_otp(phone_raw, code)
        reset_token = verify_res.json()["reset_token"]

        res = _complete_reset(reset_token, "weak")
        assert res.status_code == 400

        # Basarisiz oldugu icin eski sifre hala calismali.
        national = phone_raw.lstrip("0")
        login_res = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": national, "password": "Old-pw1!"},
        )
        assert login_res.status_code == 200
    finally:
        _cleanup_by_phone(phone_raw)
