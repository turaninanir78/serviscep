"""Profilden e-posta/telefon DEGISTIRME testleri.

E-posta icin mevcut ekleme akisi (POST /auth/profile/request-email-otp ->
verify-email) zaten kosulsuzca user.email'i UZERINE YAZIYOR - yani ayni
endpoint hem "ilk kez ekleme" hem "degistirme" icin calisiyor, bu dosya
ozellikle DEGISTIRME senaryosunu (email zaten doluyken tekrar cagirma) ve
eski degerin artik ise yaramadigini dogruluyor.

Telefon icin YENI eklenen POST /auth/profile/request-phone-otp ->
verify-phone-otp akisini test ediyor - ayni deseni (dogru/yanlis kod,
baska hesapta kayitli deger, eski deger artik gecersiz) telefon icin de
kapsiyor.
"""
import random
import string
import uuid

import requests

from app.db import SessionLocal
from app.models import Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _unique_email() -> str:
    return f"profile-update-test-{uuid.uuid4().hex}@example.com"


def _register_phone_session(tenant_name: str) -> tuple[requests.Session, str]:
    phone_raw = _random_phone_raw()
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

    session = requests.Session()
    complete_res = session.post(
        f"{BASE_URL}/auth/register/complete",
        json={
            "registration_token": registration_token,
            "tenant_name": tenant_name,
            "password": "S3cret-pw!",
            "accepted_terms": True,
        },
    )
    assert complete_res.status_code == 201, complete_res.text
    return session, phone_raw


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


def _set_email(session: requests.Session, email: str) -> requests.Response:
    otp_res = session.post(f"{BASE_URL}/auth/profile/request-email-otp", json={"email": email})
    assert otp_res.status_code == 200, otp_res.text
    code = otp_res.json()["debug_code"]
    return session.post(
        f"{BASE_URL}/auth/profile/verify-email", json={"email": email, "code": code}
    )


# --- E-posta degistirme ---


def test_changing_email_updates_it_and_old_email_stops_working():
    session, phone_raw = _register_phone_session("Email Change Tenant")
    email_a = _unique_email()
    email_b = _unique_email()
    try:
        assert _set_email(session, email_a).status_code == 200

        login_a = requests.post(
            f"{BASE_URL}/auth/login", json={"email_or_phone": email_a, "password": "S3cret-pw!"}
        )
        assert login_a.status_code == 200

        # Ayni akis ("ekleme" ile "degistirme" arasinda backend seviyesinde
        # fark yok) ile farkli bir email'e GECIS yapiliyor.
        assert _set_email(session, email_b).status_code == 200

        old_login = requests.post(
            f"{BASE_URL}/auth/login", json={"email_or_phone": email_a, "password": "S3cret-pw!"}
        )
        assert old_login.status_code == 401

        new_login = requests.post(
            f"{BASE_URL}/auth/login", json={"email_or_phone": email_b, "password": "S3cret-pw!"}
        )
        assert new_login.status_code == 200
    finally:
        _cleanup_by_phone(phone_raw)


def test_changing_email_to_one_already_registered_returns_409():
    session_a, phone_a = _register_phone_session("Email Conflict Tenant A")
    session_b, phone_b = _register_phone_session("Email Conflict Tenant B")
    email_a = _unique_email()
    try:
        assert _set_email(session_a, email_a).status_code == 200

        conflict_res = session_b.post(
            f"{BASE_URL}/auth/profile/request-email-otp", json={"email": email_a}
        )
        assert conflict_res.status_code == 409
    finally:
        _cleanup_by_phone(phone_a)
        _cleanup_by_phone(phone_b)


def test_wrong_code_for_email_change_is_rejected():
    session, phone_raw = _register_phone_session("Email Wrong Code Tenant")
    email = _unique_email()
    try:
        req_res = session.post(
            f"{BASE_URL}/auth/profile/request-email-otp", json={"email": email}
        )
        assert req_res.status_code == 200

        res = session.post(
            f"{BASE_URL}/auth/profile/verify-email", json={"email": email, "code": "000000"}
        )
        assert res.status_code == 400
    finally:
        _cleanup_by_phone(phone_raw)


# --- Telefon degistirme ---


def test_changing_phone_updates_it_and_old_phone_stops_working():
    session, phone_raw = _register_phone_session("Phone Change Tenant")
    new_phone_raw = _random_phone_raw()
    try:
        otp_res = session.post(
            f"{BASE_URL}/auth/profile/request-phone-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": new_phone_raw},
        )
        assert otp_res.status_code == 200, otp_res.text
        code = otp_res.json()["debug_code"]

        verify_res = session.post(
            f"{BASE_URL}/auth/profile/verify-phone-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": new_phone_raw, "code": code},
        )
        assert verify_res.status_code == 200, verify_res.text

        old_login = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": phone_raw.lstrip("0"), "password": "S3cret-pw!"},
        )
        assert old_login.status_code == 401

        new_login = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": new_phone_raw.lstrip("0"), "password": "S3cret-pw!"},
        )
        assert new_login.status_code == 200
    finally:
        _cleanup_by_phone(new_phone_raw)
        _cleanup_by_phone(phone_raw)


def test_changing_phone_to_one_already_registered_returns_409():
    session_a, phone_a = _register_phone_session("Phone Conflict Tenant A")
    session_b, phone_b = _register_phone_session("Phone Conflict Tenant B")
    try:
        res = session_b.post(
            f"{BASE_URL}/auth/profile/request-phone-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": phone_a},
        )
        assert res.status_code == 409
    finally:
        _cleanup_by_phone(phone_a)
        _cleanup_by_phone(phone_b)


def test_wrong_code_for_phone_change_is_rejected():
    session, phone_raw = _register_phone_session("Phone Wrong Code Tenant")
    new_phone_raw = _random_phone_raw()
    try:
        req_res = session.post(
            f"{BASE_URL}/auth/profile/request-phone-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": new_phone_raw},
        )
        assert req_res.status_code == 200

        res = session.post(
            f"{BASE_URL}/auth/profile/verify-phone-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": new_phone_raw, "code": "000000"},
        )
        assert res.status_code == 400
    finally:
        _cleanup_by_phone(phone_raw)
        _cleanup_by_phone(new_phone_raw)


def test_profile_phone_endpoints_require_authentication():
    res = requests.post(
        f"{BASE_URL}/auth/profile/request-phone-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": "5551234567"},
    )
    assert res.status_code == 401
