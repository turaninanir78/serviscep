"""Kayitta otomatik kendi-personel kaydi testleri.

Hem eski (email+sifre) hem yeni (telefon+OTP) kayit akisinin, hicbir
elle "Personel Ekle" adimi olmadan, yeni tenant icin bir StaffMember
kaydi olusturdugunu; bu kaydin OZEL bir korumasi olmadigini (normal
StaffMember gibi yeniden adlandirilabildigini); ve bu sayede kayit
hemen ardindan (baska hicbir kurulum adimi olmadan) bir randevu
olusturulabildigini dogrular - gorevin asil amaci tam da bu sonuncusu.

Diger testlerle ayni yaklasim: calisan sunucuya gercek HTTP istekleri,
DB temizligi tenant uzerinden manuel.
"""
import random
import string
import uuid

import requests

from app.db import SessionLocal
from app.models import StaffMember, Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _unique_email() -> str:
    return f"auto-staff-test-{uuid.uuid4().hex}@example.com"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _cleanup_by_email(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
            db.commit()
    finally:
        db.close()


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


def test_old_register_flow_creates_a_self_staff_member():
    email = _unique_email()
    try:
        res = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "tenant_name": "Auto Staff Old Flow Tenant",
                "email": email,
                "password": "Str0ng!pw",
                "accepted_terms": True,
            },
        )
        assert res.status_code == 201

        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email).first()
            staff = db.query(StaffMember).filter(StaffMember.tenant_id == user.tenant_id).all()
            assert len(staff) == 1
            assert staff[0].name == "Ben"
            assert staff[0].is_active is True
        finally:
            db.close()
    finally:
        _cleanup_by_email(email)


def test_phone_otp_register_flow_creates_a_self_staff_member():
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
                "tenant_name": "Auto Staff Phone Flow Tenant",
                "password": "Str0ng!pw",
                "accepted_terms": True,
            },
        )
        assert complete_res.status_code == 201

        normalized = normalize_phone(COUNTRY_CODE, phone_raw)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone == normalized).first()
            staff = db.query(StaffMember).filter(StaffMember.tenant_id == user.tenant_id).all()
            assert len(staff) == 1
            assert staff[0].name == "Ben"
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)


def test_auto_created_staff_member_is_not_protected_and_can_be_renamed():
    email = _unique_email()
    try:
        session = requests.Session()
        register_res = session.post(
            f"{BASE_URL}/auth/register",
            json={
                "tenant_name": "Auto Staff Rename Tenant",
                "email": email,
                "password": "Str0ng!pw",
                "accepted_terms": True,
            },
        )
        assert register_res.status_code == 201

        staff_list = session.get(f"{BASE_URL}/staff_members").json()
        assert len(staff_list) == 1
        staff_id = staff_list[0]["id"]

        rename_res = session.patch(
            f"{BASE_URL}/staff_members/{staff_id}", json={"name": "Ahmet Usta"}
        )
        assert rename_res.status_code == 200
        assert rename_res.json()["name"] == "Ahmet Usta"

        deactivate_res = session.patch(
            f"{BASE_URL}/staff_members/{staff_id}", json={"is_active": False}
        )
        assert deactivate_res.status_code == 200
        assert deactivate_res.json()["is_active"] is False
    finally:
        _cleanup_by_email(email)


def test_new_tenant_can_create_an_appointment_immediately_without_adding_staff_manually():
    """Gorevin asil amaci: kayit sonrasi, hicbir "Personel Ekle" adimi
    atlanmadan (POST /staff_members hic cagrilmadan) dogrudan randevu
    olusturulabilmeli."""
    email = _unique_email()
    try:
        session = requests.Session()
        register_res = session.post(
            f"{BASE_URL}/auth/register",
            json={
                "tenant_name": "Auto Staff Appointment Tenant",
                "email": email,
                "password": "Str0ng!pw",
                "accepted_terms": True,
            },
        )
        assert register_res.status_code == 201

        staff_list = session.get(f"{BASE_URL}/staff_members").json()
        assert len(staff_list) == 1
        staff_id = staff_list[0]["id"]

        service_res = session.post(
            f"{BASE_URL}/services", json={"name": "Saç Kesimi", "duration_minutes": 30}
        )
        assert service_res.status_code == 201
        service_id = service_res.json()["id"]

        customer_res = session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905559990000"}
        )
        assert customer_res.status_code == 201
        customer_id = customer_res.json()["id"]

        appointment_res = session.post(
            f"{BASE_URL}/appointments",
            json={
                "staff_id": staff_id,
                "service_id": service_id,
                "customer_id": customer_id,
                "start_at": "2026-10-06T09:00:00Z",
            },
        )
        assert appointment_res.status_code == 201, appointment_res.text
    finally:
        _cleanup_by_email(email)
