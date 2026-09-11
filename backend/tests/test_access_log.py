"""Basit erisim denetim izi (AccessLog) testleri - tekil bir musteri/randevu
kaydina GET/PATCH ile erisildiginde bir AccessLog satiri olustugunu
dogrular (bkz. app/access_log.py, app/api/customers.py, app/api/appointments.py).
"""
import random
import string

import requests

from app.db import SessionLocal
from app.models import AccessLog, Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _register_and_get_session(tenant_name: str) -> tuple[requests.Session, str]:
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


def test_get_customer_by_id_creates_access_log_entry():
    session, phone_raw = _register_and_get_session("Access Log Customer Tenant")
    try:
        create_res = session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905559991111"}
        )
        assert create_res.status_code == 201
        customer_id = create_res.json()["id"]

        get_res = session.get(f"{BASE_URL}/customers/{customer_id}")
        assert get_res.status_code == 200

        db = SessionLocal()
        try:
            logs = (
                db.query(AccessLog)
                .filter(AccessLog.resource_type == "customer", AccessLog.resource_id == customer_id)
                .all()
            )
            assert len(logs) == 1
            assert logs[0].action == "GET"
            assert logs[0].user_id is not None
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)


def test_reschedule_appointment_creates_access_log_entry():
    session, phone_raw = _register_and_get_session("Access Log Appointment Tenant")
    try:
        staff_res = session.post(f"{BASE_URL}/staff_members", json={"name": "Log Staff"})
        assert staff_res.status_code == 201
        staff_id = staff_res.json()["id"]

        service_res = session.post(
            f"{BASE_URL}/services", json={"name": "Log Service", "duration_minutes": 30}
        )
        assert service_res.status_code == 201
        service_id = service_res.json()["id"]

        customer_res = session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905559992222"}
        )
        assert customer_res.status_code == 201
        customer_id = customer_res.json()["id"]

        create_res = session.post(
            f"{BASE_URL}/appointments",
            json={
                "staff_id": staff_id,
                "service_id": service_id,
                "customer_id": customer_id,
                "start_at": "2026-10-05T09:00:00Z",
            },
        )
        assert create_res.status_code == 201, create_res.text
        appointment_id = create_res.json()["id"]

        reschedule_res = session.patch(
            f"{BASE_URL}/appointments/{appointment_id}",
            json={"start_at": "2026-10-05T10:00:00Z"},
        )
        assert reschedule_res.status_code == 200, reschedule_res.text

        db = SessionLocal()
        try:
            logs = (
                db.query(AccessLog)
                .filter(
                    AccessLog.resource_type == "appointment",
                    AccessLog.resource_id == appointment_id,
                )
                .all()
            )
            assert len(logs) == 1
            assert logs[0].action == "PATCH"
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)
