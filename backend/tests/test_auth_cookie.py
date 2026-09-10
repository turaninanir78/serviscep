"""JWT'nin httpOnly cookie olarak tasindigini dogrulayan auth testleri.

test_appointment_race_condition.py ile ayni yaklasim: calisan uygulama
sunucusuna (http://localhost:8000) gercek HTTP istekleri atilir - cunku asil
dogrulanan sey Set-Cookie/httponly davranisinin ve cookie'nin sonraki
isteklere otomatik eklenmesinin gercek bir HTTP round-trip'inde calismasi;
bu servis katmani fonksiyonlarini dogrudan cagirarak test edilemez.
`requests.Session`, tarayicinin cookie jar'ini taklit eder.
"""
import uuid

import requests

from app.db import SessionLocal
from app.models import Tenant, User

BASE_URL = "http://localhost:8000"
COOKIE_NAME = "access_token"


def _unique_email() -> str:
    return f"cookie-test-{uuid.uuid4().hex}@example.com"


def _cleanup_by_email(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
            db.commit()
    finally:
        db.close()


def test_register_sets_httponly_cookie_and_does_not_leak_token_in_body():
    email = _unique_email()
    session = requests.Session()
    try:
        res = session.post(
            f"{BASE_URL}/auth/register",
            json={"tenant_name": "Cookie Test Tenant", "email": email, "password": "s3cret-pw"},
        )
        assert res.status_code == 201
        assert "access_token" not in res.text

        set_cookie_header = res.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie_header
        assert "httponly" in set_cookie_header.lower()

        assert session.cookies.get(COOKIE_NAME) is not None
    finally:
        _cleanup_by_email(email)


def test_cookie_from_register_grants_access_to_protected_route():
    email = _unique_email()
    session = requests.Session()
    try:
        session.post(
            f"{BASE_URL}/auth/register",
            json={"tenant_name": "Cookie Test Tenant", "email": email, "password": "s3cret-pw"},
        )

        me = session.get(f"{BASE_URL}/tenants/me")
        assert me.status_code == 200
        assert me.json()["name"] == "Cookie Test Tenant"
        # Web/mobil, randevu saat/tarihlerini bu alanla goruntuluyor (cihaz
        # saat dilimi yerine) - bkz. app/schemas/tenant.py::TenantOut.
        assert me.json()["timezone"] == "Europe/Istanbul"
    finally:
        _cleanup_by_email(email)


def test_login_with_correct_password_sets_cookie():
    email = _unique_email()
    try:
        requests.post(
            f"{BASE_URL}/auth/register",
            json={"tenant_name": "Cookie Test Tenant", "email": email, "password": "correct-pw"},
        )

        session = requests.Session()
        res = session.post(
            f"{BASE_URL}/auth/login", json={"email": email, "password": "correct-pw"}
        )
        assert res.status_code == 200
        assert "access_token" not in res.text
        assert session.cookies.get(COOKIE_NAME) is not None
        assert session.get(f"{BASE_URL}/tenants/me").status_code == 200
    finally:
        _cleanup_by_email(email)


def test_login_with_wrong_password_returns_401_and_sets_no_cookie():
    email = _unique_email()
    try:
        requests.post(
            f"{BASE_URL}/auth/register",
            json={"tenant_name": "Cookie Test Tenant", "email": email, "password": "correct-pw"},
        )

        session = requests.Session()
        res = session.post(
            f"{BASE_URL}/auth/login", json={"email": email, "password": "wrong-pw"}
        )
        assert res.status_code == 401
        assert session.cookies.get(COOKIE_NAME) is None
    finally:
        _cleanup_by_email(email)


def test_protected_route_without_cookie_returns_401():
    res = requests.get(f"{BASE_URL}/tenants/me")
    assert res.status_code == 401


def test_logout_clears_cookie_and_blocks_further_access():
    email = _unique_email()
    try:
        session = requests.Session()
        session.post(
            f"{BASE_URL}/auth/register",
            json={"tenant_name": "Cookie Test Tenant", "email": email, "password": "correct-pw"},
        )
        assert session.get(f"{BASE_URL}/tenants/me").status_code == 200

        logout_res = session.post(f"{BASE_URL}/auth/logout")
        assert logout_res.status_code == 204
        assert session.cookies.get(COOKIE_NAME) is None

        assert session.get(f"{BASE_URL}/tenants/me").status_code == 401
    finally:
        _cleanup_by_email(email)
