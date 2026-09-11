"""KVKK unutulma hakki - POST /customers/{id}/request-deletion testleri.

Musterinin kisisel verilerinin (isim, telefon) gercekten anonimlestirildigini,
whatsapp_number_hash'in degistigini (ayni numaradan gelen bir sonraki
webhook mesaji artik eslesmemeli), silinen musterinin normal listede
gorunmedigini, erisim izine kaydedildigini, islemin tenant-izole ve
idempotent (iki kez calistirilamaz) oldugunu dogrular.

Diger testlerle ayni yaklasim: calisan sunucuya gercek HTTP istekleri, DB
temizligi tenant uzerinden manuel.
"""
import random
import string

import requests

from app.db import SessionLocal
from app.models import AccessLog, Customer, Tenant, User
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


def test_request_deletion_anonymizes_personal_fields():
    session, phone_raw = _register_and_get_session("Deletion Test Tenant")
    try:
        create_res = session.post(
            f"{BASE_URL}/customers",
            json={"whatsapp_number": "905558880001", "display_name": "Ali Veli"},
        )
        assert create_res.status_code == 201
        customer_id = create_res.json()["id"]

        delete_res = session.post(f"{BASE_URL}/customers/{customer_id}/request-deletion")
        assert delete_res.status_code == 200, delete_res.text
        body = delete_res.json()
        assert body["display_name"] == "Silinmiş Müşteri"
        assert body["whatsapp_number"] != "905558880001"
        assert body["deleted_at"] is not None
        assert body["deletion_requested_at"] is not None
    finally:
        _cleanup_by_phone(phone_raw)


def test_whatsapp_number_hash_changes_so_new_message_creates_a_new_customer():
    session, phone_raw = _register_and_get_session("Deletion Hash Tenant")
    try:
        create_res = session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905558880002"}
        )
        customer_id = create_res.json()["id"]

        db = SessionLocal()
        try:
            before = db.query(Customer).filter(Customer.id == customer_id).first()
            hash_before_deletion = before.whatsapp_number_hash
        finally:
            db.close()

        session.post(f"{BASE_URL}/customers/{customer_id}/request-deletion")

        db = SessionLocal()
        try:
            after = db.query(Customer).filter(Customer.id == customer_id).first()
            assert after.whatsapp_number_hash != hash_before_deletion
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)


def test_deleted_customer_is_excluded_from_list_but_still_reachable_by_id():
    session, phone_raw = _register_and_get_session("Deletion List Tenant")
    try:
        create_res = session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905558880003"}
        )
        customer_id = create_res.json()["id"]
        session.post(f"{BASE_URL}/customers/{customer_id}/request-deletion")

        list_res = session.get(f"{BASE_URL}/customers")
        assert list_res.status_code == 200
        assert all(c["id"] != customer_id for c in list_res.json())

        get_res = session.get(f"{BASE_URL}/customers/{customer_id}")
        assert get_res.status_code == 200
        assert get_res.json()["display_name"] == "Silinmiş Müşteri"
    finally:
        _cleanup_by_phone(phone_raw)


def test_request_deletion_creates_access_log_entry():
    session, phone_raw = _register_and_get_session("Deletion Access Log Tenant")
    try:
        create_res = session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905558880004"}
        )
        customer_id = create_res.json()["id"]
        session.post(f"{BASE_URL}/customers/{customer_id}/request-deletion")

        db = SessionLocal()
        try:
            logs = (
                db.query(AccessLog)
                .filter(AccessLog.resource_type == "customer", AccessLog.resource_id == customer_id)
                .all()
            )
            assert any(log.action == "DELETE" for log in logs)
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)


def test_requesting_deletion_twice_returns_409():
    session, phone_raw = _register_and_get_session("Deletion Idempotency Tenant")
    try:
        create_res = session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905558880005"}
        )
        customer_id = create_res.json()["id"]

        first = session.post(f"{BASE_URL}/customers/{customer_id}/request-deletion")
        assert first.status_code == 200

        second = session.post(f"{BASE_URL}/customers/{customer_id}/request-deletion")
        assert second.status_code == 409
    finally:
        _cleanup_by_phone(phone_raw)


def test_cannot_request_deletion_of_another_tenants_customer():
    session_a, phone_a = _register_and_get_session("Deletion Isolation Tenant A")
    session_b, phone_b = _register_and_get_session("Deletion Isolation Tenant B")
    try:
        create_res = session_a.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905558880006"}
        )
        customer_id = create_res.json()["id"]

        cross_tenant_res = session_b.post(f"{BASE_URL}/customers/{customer_id}/request-deletion")
        assert cross_tenant_res.status_code == 404

        # Musteri tenant A'da hala silinmemis olmali.
        get_res = session_a.get(f"{BASE_URL}/customers/{customer_id}")
        assert get_res.json()["deleted_at"] is None
    finally:
        _cleanup_by_phone(phone_a)
        _cleanup_by_phone(phone_b)


def test_deleting_nonexistent_customer_returns_404():
    session, phone_raw = _register_and_get_session("Deletion Not Found Tenant")
    try:
        res = session.post(f"{BASE_URL}/customers/999999999/request-deletion")
        assert res.status_code == 404
    finally:
        _cleanup_by_phone(phone_raw)
