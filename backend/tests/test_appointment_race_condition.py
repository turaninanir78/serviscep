"""Iki es zamanli randevu olusturma istegi gercekten ayni anda tetiklenirse,
sadece biri basarili olmali, digeri 409 Conflict almali.

Bu test, calisan uygulama sunucusuna (http://localhost:8000) gercek,
paralel HTTP istekleri atar - yani docker compose stack'i AYAKTA olmali.
Uygulama seviyesindeki `has_conflict` on-kontrolu tek basina bu yarisi
kapatamaz (iki istek de commit'ten once "cakisma yok" gorebilir); asil
guvence migration 0003'teki EXCLUDE constraint'idir.
"""
import json
import threading
import urllib.error
import urllib.request

from app.db import SessionLocal
from app.models import Customer, Service, StaffMember, Tenant
from app.security import ACCESS_TOKEN_COOKIE_NAME, create_access_token

BASE_URL = "http://localhost:8000"


def _setup_fixtures() -> tuple[int, int, int, int]:
    db = SessionLocal()
    try:
        tenant = Tenant(name="Race Test Tenant")
        db.add(tenant)
        db.flush()

        staff = StaffMember(tenant_id=tenant.id, name="Race Test Staff")
        service = Service(tenant_id=tenant.id, name="Race Test Service", duration_minutes=30)
        customer = Customer(tenant_id=tenant.id, whatsapp_number="905550000000")
        db.add_all([staff, service, customer])
        db.commit()
        db.refresh(staff)
        db.refresh(service)
        db.refresh(customer)

        return tenant.id, staff.id, service.id, customer.id
    finally:
        db.close()


def _teardown_tenant(tenant_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(Tenant).filter(Tenant.id == tenant_id).delete()
        db.commit()
    finally:
        db.close()


def _post_appointment(
    token: str, payload: dict, results: list, barrier: threading.Barrier
) -> None:
    barrier.wait()  # iki thread'in mumkun oldugunca ayni anda istek atmasini saglar
    req = urllib.request.Request(
        f"{BASE_URL}/appointments",
        data=json.dumps(payload).encode(),
        method="POST",
        headers={
            # Auth artik httpOnly cookie ile tasiniyor (bkz. app/security.py) -
            # Authorization header'i backend tarafindan artik okunmuyor.
            "Cookie": f"{ACCESS_TOKEN_COOKIE_NAME}={token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            results.append((resp.status, json.loads(resp.read())))
    except urllib.error.HTTPError as exc:
        results.append((exc.code, json.loads(exc.read())))


def test_concurrent_appointment_requests_only_one_succeeds():
    tenant_id, staff_id, service_id, customer_id = _setup_fixtures()
    token = create_access_token(user_id=0, tenant_id=tenant_id)
    payload = {
        "staff_id": staff_id,
        "service_id": service_id,
        "customer_id": customer_id,
        "start_at": "2026-10-05T09:00:00",
    }

    results: list[tuple[int, dict]] = []
    barrier = threading.Barrier(2)

    try:
        threads = [
            threading.Thread(target=_post_appointment, args=(token, payload, results, barrier))
            for _ in range(2)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)

        assert len(results) == 2, f"iki yanit da donmedi: {results}"
        status_codes = sorted(code for code, _ in results)
        assert status_codes == [201, 409], f"beklenmeyen sonuc: {results}"
    finally:
        _teardown_tenant(tenant_id)
