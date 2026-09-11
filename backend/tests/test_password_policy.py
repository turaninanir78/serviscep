"""Sifre gucu politikasi testleri.

app/password_policy.py::validate_password_strength saf fonksiyon
testleri + bu kuralin GERCEKTEN uygulandigi her sifre olusturma/degistirme
noktasinda (eski email+sifre kaydi, telefon+OTP kaydi, profilden sifre
degistirme) HTTP uzerinden dogrulanmasi.

Bu projede su an bir sifre-sifirlama (unuttum) akisi YOK - eklenirse ayni
validate_password_strength'i kullanmali (bkz. gorev ozeti).
"""
import random
import string
import uuid

import pytest
import requests
from fastapi import HTTPException

from app.db import SessionLocal
from app.models import Tenant, User
from app.password_policy import validate_password_strength
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _unique_email() -> str:
    return f"password-policy-test-{uuid.uuid4().hex}@example.com"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


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


# --- Saf fonksiyon testleri ---


def test_too_short_password_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_password_strength("Ab1!")
    assert exc_info.value.status_code == 400
    assert "en az 6 karakter" in exc_info.value.detail


def test_password_without_uppercase_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_password_strength("abcde1!")
    assert "büyük harf" in exc_info.value.detail


def test_password_without_lowercase_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_password_strength("ABCDE1!")
    assert "küçük harf" in exc_info.value.detail


def test_password_without_special_character_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        validate_password_strength("Abcdef1")
    assert "özel karakter" in exc_info.value.detail


def test_password_satisfying_all_rules_is_accepted():
    validate_password_strength("Abcde1!")  # exception firlatmamali


# --- Kayit (eski email+sifre akisi) ---


def test_register_rejects_weak_password():
    email = _unique_email()
    try:
        res = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "tenant_name": "Weak Password Tenant",
                "email": email,
                "password": "weakpw",
                "accepted_terms": True,
            },
        )
        assert res.status_code == 400
        assert "büyük harf" in res.json()["detail"]

        db = SessionLocal()
        try:
            assert db.query(User).filter(User.email == email).first() is None
        finally:
            db.close()
    finally:
        _cleanup_by_email(email)


def test_register_accepts_strong_password():
    email = _unique_email()
    try:
        res = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "tenant_name": "Strong Password Tenant",
                "email": email,
                "password": "Str0ng!pw",
                "accepted_terms": True,
            },
        )
        assert res.status_code == 201
    finally:
        _cleanup_by_email(email)


# --- Kayit (telefon + OTP akisi) ---


def test_register_complete_rejects_weak_password():
    phone_raw = _random_phone_raw()
    try:
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
                "tenant_name": "Weak Password Phone Tenant",
                "password": "weakpw",
                "accepted_terms": True,
            },
        )
        assert complete_res.status_code == 400
        assert "büyük harf" in complete_res.json()["detail"]

        normalized = normalize_phone(COUNTRY_CODE, phone_raw)
        db = SessionLocal()
        try:
            assert db.query(User).filter(User.phone == normalized).first() is None
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)


# --- Profilden sifre degistirme ---


def _register_and_get_session(email: str, password: str) -> requests.Session:
    session = requests.Session()
    res = session.post(
        f"{BASE_URL}/auth/register",
        json={
            "tenant_name": "Change Password Tenant",
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert res.status_code == 201, res.text
    return session


def test_change_password_rejects_weak_new_password():
    email = _unique_email()
    try:
        session = _register_and_get_session(email, "Origina1!")
        res = session.post(
            f"{BASE_URL}/auth/profile/change-password",
            json={"current_password": "Origina1!", "new_password": "weak"},
        )
        assert res.status_code == 400
    finally:
        _cleanup_by_email(email)


def test_change_password_rejects_wrong_current_password():
    email = _unique_email()
    try:
        session = _register_and_get_session(email, "Origina1!")
        res = session.post(
            f"{BASE_URL}/auth/profile/change-password",
            json={"current_password": "NotTheRight1!", "new_password": "NewStr0ng!"},
        )
        assert res.status_code == 401
    finally:
        _cleanup_by_email(email)


def test_change_password_succeeds_and_old_password_stops_working():
    email = _unique_email()
    try:
        session = _register_and_get_session(email, "Origina1!")
        res = session.post(
            f"{BASE_URL}/auth/profile/change-password",
            json={"current_password": "Origina1!", "new_password": "NewStr0ng!"},
        )
        assert res.status_code == 204

        old_login = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": email, "password": "Origina1!"},
        )
        assert old_login.status_code == 401

        new_login = requests.post(
            f"{BASE_URL}/auth/login",
            json={"email_or_phone": email, "password": "NewStr0ng!"},
        )
        assert new_login.status_code == 200
    finally:
        _cleanup_by_email(email)


def test_change_password_requires_authentication():
    res = requests.post(
        f"{BASE_URL}/auth/profile/change-password",
        json={"current_password": "whatever", "new_password": "NewStr0ng!"},
    )
    assert res.status_code == 401
