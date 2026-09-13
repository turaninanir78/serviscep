"""Kayitta otomatik varsayilan hizmet kaydi testleri.

test_register_auto_staff_member.py ile ayni yaklasim (calisan sunucuya
gercek HTTP istekleri, DB temizligi tenant uzerinden manuel). Hem yeni
(telefon+OTP) kayit akisinin varsayilan bir Service olusturdugunu, bu
kaydin normal bir Service gibi duzenlenip silinebildigini, mevcut (hic
hizmeti olmayan) tenant'lar icin backfill migration'inin dogru
calistigini, ve kayit sonrasi hicbir elle kurulum adimi olmadan
(POST /staff_members veya POST /services hic cagrilmadan) dogrudan
randevu olusturulabildigini dogrular - gorevin asil amaci tam da bu
sonuncusu.
"""
import random
import string
import uuid

import requests
from sqlalchemy import text

from app.db import SessionLocal
from app.models import Service, Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _unique_email() -> str:
    return f"auto-service-test-{uuid.uuid4().hex}@example.com"


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


def test_phone_otp_register_flow_creates_a_default_service():
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
                "tenant_name": "Auto Service Phone Flow Tenant",
                "password": "Str0ng!pw",
                "accepted_terms": True,
            },
        )
        assert complete_res.status_code == 201

        normalized = normalize_phone(COUNTRY_CODE, phone_raw)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone == normalized).first()
            services = db.query(Service).filter(Service.tenant_id == user.tenant_id).all()
            assert len(services) == 1
            assert services[0].name == "Genel Hizmet"
            assert services[0].duration_minutes == 30
            assert services[0].price is None
            assert services[0].is_active is True
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)


def test_auto_created_service_is_not_protected_and_can_be_edited():
    phone_raw = _random_phone_raw()
    try:
        session = requests.Session()
        otp_res = session.post(
            f"{BASE_URL}/auth/register/request-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
        )
        code = otp_res.json()["debug_code"]
        verify_res = session.post(
            f"{BASE_URL}/auth/register/verify-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": phone_raw, "code": code},
        )
        registration_token = verify_res.json()["registration_token"]
        register_res = session.post(
            f"{BASE_URL}/auth/register/complete",
            json={
                "registration_token": registration_token,
                "tenant_name": "Auto Service Edit Tenant",
                "password": "Str0ng!pw",
                "accepted_terms": True,
            },
        )
        assert register_res.status_code == 201

        service_list = session.get(f"{BASE_URL}/services").json()
        assert len(service_list) == 1
        service_id = service_list[0]["id"]

        edit_res = session.patch(
            f"{BASE_URL}/services/{service_id}",
            json={"name": "Saç Kesimi", "duration_minutes": 45, "price": "150.00"},
        )
        assert edit_res.status_code == 200, edit_res.text
        assert edit_res.json()["name"] == "Saç Kesimi"
        assert edit_res.json()["duration_minutes"] == 45

        deactivate_res = session.patch(
            f"{BASE_URL}/services/{service_id}", json={"is_active": False}
        )
        assert deactivate_res.status_code == 200
        assert deactivate_res.json()["is_active"] is False
    finally:
        _cleanup_by_phone(phone_raw)


def test_new_tenant_can_create_an_appointment_immediately_without_manual_setup():
    """Gorevin asil amaci: kayit sonrasi, hicbir "Personel Ekle" veya
    "Hizmet Ekle" adimi atlanmadan (POST /staff_members ve POST /services
    hic cagrilmadan) dogrudan randevu olusturulabilmeli."""
    phone_raw = _random_phone_raw()
    try:
        session = requests.Session()
        otp_res = session.post(
            f"{BASE_URL}/auth/register/request-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
        )
        code = otp_res.json()["debug_code"]
        verify_res = session.post(
            f"{BASE_URL}/auth/register/verify-otp",
            json={"country_code": COUNTRY_CODE, "phone_number": phone_raw, "code": code},
        )
        registration_token = verify_res.json()["registration_token"]
        register_res = session.post(
            f"{BASE_URL}/auth/register/complete",
            json={
                "registration_token": registration_token,
                "tenant_name": "Auto Setup Appointment Tenant",
                "password": "Str0ng!pw",
                "accepted_terms": True,
            },
        )
        assert register_res.status_code == 201

        # KASITLI OLARAK POST /staff_members veya POST /services HIC
        # cagrilmiyor - sadece otomatik olusan kayitlar okunuyor.
        staff_list = session.get(f"{BASE_URL}/staff_members").json()
        assert len(staff_list) == 1
        staff_id = staff_list[0]["id"]

        service_list = session.get(f"{BASE_URL}/services").json()
        assert len(service_list) == 1
        service_id = service_list[0]["id"]

        customer_res = session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905559990001"}
        )
        assert customer_res.status_code == 201
        customer_id = customer_res.json()["id"]

        appointment_res = session.post(
            f"{BASE_URL}/appointments",
            json={
                "staff_id": staff_id,
                "service_id": service_id,
                "customer_id": customer_id,
                "start_at": "2026-10-07T09:00:00Z",
            },
        )
        assert appointment_res.status_code == 201, appointment_res.text
    finally:
        _cleanup_by_phone(phone_raw)


def test_backfill_migration_only_adds_service_to_tenants_without_one():
    """0013_backfill_default_service migration'inin upgrade() mantigini
    (SELECT ... WHERE s.id IS NULL) dogrudan tekrar calistirarak dogrular -
    hic hizmeti olmayan bir tenant'a ekleniyor, mevcut hizmeti olan bir
    tenant'a DOKUNULMUYOR (mukerrer kayit eklenmiyor)."""
    db = SessionLocal()
    try:
        tenant_without_service = Tenant(name="Backfill No Service Tenant")
        tenant_with_service = Tenant(name="Backfill Has Service Tenant")
        db.add_all([tenant_without_service, tenant_with_service])
        db.flush()

        existing_service = Service(
            tenant_id=tenant_with_service.id,
            name="Zaten Var Olan Hizmet",
            duration_minutes=60,
        )
        db.add(existing_service)
        db.commit()

        # Migration'daki AYNI SQL - iki tenant'i da kapsayan bir alt kumeye
        # daraltiyoruz ki test, projedeki BASKA (bu testten once/sonra
        # olusmus) tenant'lardan etkilenmesin.
        tenant_ids = (tenant_without_service.id, tenant_with_service.id)
        rows = db.execute(
            text(
                "SELECT t.id FROM tenants t "
                "LEFT JOIN services s ON s.tenant_id = t.id "
                "WHERE s.id IS NULL AND t.id = ANY(:tenant_ids)"
            ),
            {"tenant_ids": list(tenant_ids)},
        ).fetchall()
        missing_ids = {row.id for row in rows}

        assert missing_ids == {tenant_without_service.id}

        for tenant_id in missing_ids:
            db.execute(
                text(
                    "INSERT INTO services (tenant_id, name, duration_minutes, is_active, default_buffer_minutes) "
                    "VALUES (:tenant_id, 'Genel Hizmet', 30, true, 0)"
                ),
                {"tenant_id": tenant_id},
            )
        db.commit()

        services_without = (
            db.query(Service).filter(Service.tenant_id == tenant_without_service.id).all()
        )
        services_with = (
            db.query(Service).filter(Service.tenant_id == tenant_with_service.id).all()
        )
        assert len(services_without) == 1
        assert services_without[0].name == "Genel Hizmet"
        # Mevcut hizmet DOKUNULMADAN, tek basina kaldi - mukerrer eklenmedi.
        assert len(services_with) == 1
        assert services_with[0].name == "Zaten Var Olan Hizmet"
    finally:
        db.query(Tenant).filter(
            Tenant.id.in_([tenant_without_service.id, tenant_with_service.id])
        ).delete(synchronize_session=False)
        db.commit()
        db.close()
