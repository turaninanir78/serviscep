"""Mobil auth (POST /auth/mobile/register, /auth/mobile/login) ve
Authorization: Bearer destegi testleri.

Web'in httpOnly cookie akisindan farkli olarak, mobil client'lar token'i
govdede alip Authorization: Bearer header'iyla gonderiyor - bu dosya hem
yeni mobil endpoint'lerin dogru davrandigini hem de bu degisikligin
web'in cookie akisini BOZMADIGINI dogruluyor.

test_auth_cookie.py ile ayni yaklasim: calisan uygulama sunucusuna
(http://localhost:8000) gercek HTTP istekleri atilir.
"""
import uuid

import requests

from app.db import SessionLocal
from app.models import Tenant, User

BASE_URL = "http://localhost:8000"


def _unique_email() -> str:
    return f"mobile-auth-test-{uuid.uuid4().hex}@example.com"


def _cleanup_by_email(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
            db.commit()
    finally:
        db.close()


def test_mobile_register_returns_token_in_body_not_cookie():
    email = _unique_email()
    try:
        res = requests.post(
            f"{BASE_URL}/auth/mobile/register",
            json={"tenant_name": "Mobile Test Tenant", "email": email, "password": "s3cret-pw"},
        )
        assert res.status_code == 201
        body = res.json()
        assert isinstance(body["access_token"], str) and body["access_token"] != ""
        assert body["token_type"] == "bearer"
        assert "set-cookie" not in {k.lower() for k in res.headers}
    finally:
        _cleanup_by_email(email)


def test_mobile_login_returns_token_in_body_not_cookie():
    email = _unique_email()
    try:
        requests.post(
            f"{BASE_URL}/auth/mobile/register",
            json={"tenant_name": "Mobile Test Tenant", "email": email, "password": "correct-pw"},
        )

        res = requests.post(
            f"{BASE_URL}/auth/mobile/login", json={"email": email, "password": "correct-pw"}
        )
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body["access_token"], str) and body["access_token"] != ""
        assert "set-cookie" not in {k.lower() for k in res.headers}
    finally:
        _cleanup_by_email(email)


def test_mobile_login_with_wrong_password_returns_401_and_no_token():
    email = _unique_email()
    try:
        requests.post(
            f"{BASE_URL}/auth/mobile/register",
            json={"tenant_name": "Mobile Test Tenant", "email": email, "password": "correct-pw"},
        )

        res = requests.post(
            f"{BASE_URL}/auth/mobile/login", json={"email": email, "password": "wrong-pw"}
        )
        assert res.status_code == 401
        assert "access_token" not in res.text
    finally:
        _cleanup_by_email(email)


def test_bearer_token_from_mobile_login_grants_access_to_protected_route():
    email = _unique_email()
    try:
        register_res = requests.post(
            f"{BASE_URL}/auth/mobile/register",
            json={"tenant_name": "Mobile Bearer Tenant", "email": email, "password": "s3cret-pw"},
        )
        token = register_res.json()["access_token"]

        me = requests.get(
            f"{BASE_URL}/tenants/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert me.status_code == 200
        assert me.json()["name"] == "Mobile Bearer Tenant"
    finally:
        _cleanup_by_email(email)


def test_missing_bearer_token_and_missing_cookie_returns_401():
    res = requests.get(f"{BASE_URL}/tenants/me")
    assert res.status_code == 401


def test_invalid_bearer_token_returns_401():
    res = requests.get(
        f"{BASE_URL}/tenants/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert res.status_code == 401


def test_bearer_token_works_for_a_mutating_endpoint_too():
    """Sadece GET degil, appointments listesi gibi normal bir kaynak
    okuma/yazma endpoint'i de Bearer token ile calismali - get_current_tenant
    her router'da ayni dependency oldugu icin bu tek bir yerde test edilse
    yeterli olsa da, gercek bir mobil ekranin (randevu listesi) kullanacagi
    endpoint uzerinden ekstra bir dogrulama."""
    email = _unique_email()
    try:
        register_res = requests.post(
            f"{BASE_URL}/auth/mobile/register",
            json={"tenant_name": "Mobile Appointments Tenant", "email": email, "password": "s3cret-pw"},
        )
        token = register_res.json()["access_token"]

        res = requests.get(
            f"{BASE_URL}/appointments", headers={"Authorization": f"Bearer {token}"}
        )
        assert res.status_code == 200
        assert res.json() == []
    finally:
        _cleanup_by_email(email)


def test_web_cookie_flow_is_unaffected_by_bearer_support():
    """Bu degisiklikten ONCE de gecen test_auth_cookie.py testleriyle
    ayni seyi dogruluyor - get_current_tenant'a Bearer fallback eklemenin
    web'in cookie akisini BOZMADIGININ ek bir guvence katmani."""
    email = _unique_email()
    session = requests.Session()
    try:
        session.post(
            f"{BASE_URL}/auth/register",
            json={"tenant_name": "Web Cookie Still Works Tenant", "email": email, "password": "s3cret-pw"},
        )
        assert session.cookies.get("access_token") is not None

        me = session.get(f"{BASE_URL}/tenants/me")
        assert me.status_code == 200
        assert me.json()["name"] == "Web Cookie Still Works Tenant"
    finally:
        _cleanup_by_email(email)


def test_cookie_takes_precedence_when_both_cookie_and_bearer_header_present():
    """get_current_tenant once cookie'ye bakiyor - gecerli bir cookie
    varken YANLIS/gecersiz bir Authorization header'i gonderilse bile
    istek cookie uzerinden basarili olmali (Bearer fallback'e hic
    dusulmemeli)."""
    email = _unique_email()
    session = requests.Session()
    try:
        session.post(
            f"{BASE_URL}/auth/register",
            json={"tenant_name": "Precedence Test Tenant", "email": email, "password": "s3cret-pw"},
        )

        me = session.get(
            f"{BASE_URL}/tenants/me",
            headers={"Authorization": "Bearer this-is-garbage-and-should-be-ignored"},
        )
        assert me.status_code == 200
        assert me.json()["name"] == "Precedence Test Tenant"
    finally:
        _cleanup_by_email(email)
