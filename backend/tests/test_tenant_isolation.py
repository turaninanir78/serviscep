"""İki farklı tenant (A ve B) arasında veri izolasyonunu doğrulayan
sistematik negatif testler.

Amaç: mevcut tenant_id filtrelemesinin (her API dosyasında ayrı ayrı
uygulanan `.filter(Model.tenant_id == auth.tenant_id)` deseni) KORUNDUĞUNU
garanti eden bir regresyon ağı - ileride biri yanlışlıkla bir filtreyi
kaldırırsa (veya yeni bir endpoint eklerken unutursa) bu dosya kırılmalı.

Her ana kaynak türü (appointment, customer, service, staff_member,
availability_rule) için: Tenant A'nın kimliğiyle, Tenant B'nin kaynak
ID'sini vererek GET/PATCH/aksiyon denemesi 404 dönmeli (mevcut kod tabanının
her yerde kullandığı pattern - bkz. app/api/*.py, hiçbiri 403 kullanmıyor),
ve Tenant A'nın liste endpoint'i hiçbir Tenant B kaydı İÇERMEMELİ.

customers ve availability_rules'ün PATCH/GET-tekil endpoint'i yok (bkz.
ilgili app/api/*.py dosyaları) - bu kaynaklar için sadece var olan
endpoint'ler test ediliyor. Hiçbir kaynak türünde DELETE endpoint'i yok
(bu API'de hiç DELETE yok) - test edilecek bir şey yok.

test_mobile_auth.py ile aynı yaklaşım: token'i gövdede alıp Authorization:
Bearer ile gönderen mobil endpoint'ler kullanılıyor (kurulum HTTP
üzerinden gerçek bir sunucuya - test edilen izolasyon tenant_id
filtrelemesi, auth yöntemi değil).
"""
import uuid
from dataclasses import dataclass

import pytest
import requests

from app.db import SessionLocal
from app.models import Tenant, User

BASE_URL = "http://localhost:8000"


def _unique_email(label: str) -> str:
    return f"tenant-isolation-{label}-{uuid.uuid4().hex}@example.com"


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _cleanup_by_email(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
            db.commit()
    finally:
        db.close()


@dataclass
class TenantContext:
    headers: dict
    staff_id: int
    service_id: int
    customer_id: int
    rule_id: int
    appointment_id: int


def _setup_tenant(label: str, whatsapp_number: str) -> tuple[str, TenantContext]:
    email = _unique_email(label)
    res = requests.post(
        f"{BASE_URL}/auth/mobile/register",
        json={
            "tenant_name": f"Isolation Test Tenant {label}",
            "email": email,
            "password": "S3cret-pw!",
            "accepted_terms": True,
        },
    )
    assert res.status_code == 201, res.text
    headers = _auth_headers(res.json()["access_token"])

    staff_res = requests.post(
        f"{BASE_URL}/staff_members", json={"name": f"Staff {label}"}, headers=headers
    )
    assert staff_res.status_code == 201, staff_res.text
    staff_id = staff_res.json()["id"]

    service_res = requests.post(
        f"{BASE_URL}/services",
        json={"name": f"Service {label}", "duration_minutes": 30},
        headers=headers,
    )
    assert service_res.status_code == 201, service_res.text
    service_id = service_res.json()["id"]

    customer_res = requests.post(
        f"{BASE_URL}/customers",
        json={"whatsapp_number": whatsapp_number},
        headers=headers,
    )
    assert customer_res.status_code == 201, customer_res.text
    customer_id = customer_res.json()["id"]

    rule_res = requests.post(
        f"{BASE_URL}/availability_rules",
        json={"staff_id": staff_id, "weekday": 0, "start_time": "09:00:00", "end_time": "18:00:00"},
        headers=headers,
    )
    assert rule_res.status_code == 201, rule_res.text
    rule_id = rule_res.json()["id"]

    # create_appointment calisma saati/musaitlik kurali dogrulamasi yapmiyor
    # (bkz. app/services/appointment_service.py::create_appointment) - sadece
    # staff/service/customer'in bu tenant'a ait oldugunu ve cakisma
    # olmadigini kontrol ediyor, bu yuzden yukaridaki kural sadece kendi
    # kaynak turu icin test edilebilir bir ID uretmek amacli.
    appointment_res = requests.post(
        f"{BASE_URL}/appointments",
        json={
            "staff_id": staff_id,
            "service_id": service_id,
            "customer_id": customer_id,
            "start_at": "2026-09-15T10:00:00",
        },
        headers=headers,
    )
    assert appointment_res.status_code == 201, appointment_res.text
    appointment_id = appointment_res.json()["id"]

    return email, TenantContext(headers, staff_id, service_id, customer_id, rule_id, appointment_id)


@pytest.fixture
def two_tenants():
    email_a, ctx_a = _setup_tenant("A", "905550000001")
    email_b, ctx_b = _setup_tenant("B", "905550000002")

    yield ctx_a, ctx_b

    _cleanup_by_email(email_a)
    _cleanup_by_email(email_b)


# --- staff_members ---


def test_get_other_tenants_staff_member_returns_404(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.get(f"{BASE_URL}/staff_members/{ctx_b.staff_id}", headers=ctx_a.headers)
    assert res.status_code == 404


def test_patch_other_tenants_staff_member_returns_404(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.patch(
        f"{BASE_URL}/staff_members/{ctx_b.staff_id}",
        json={"name": "Hacked"},
        headers=ctx_a.headers,
    )
    assert res.status_code == 404


def test_staff_members_list_excludes_other_tenant(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.get(f"{BASE_URL}/staff_members", headers=ctx_a.headers)
    assert res.status_code == 200
    ids = {item["id"] for item in res.json()}
    assert ctx_a.staff_id in ids
    assert ctx_b.staff_id not in ids


# --- services ---


def test_get_other_tenants_service_returns_404(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.get(f"{BASE_URL}/services/{ctx_b.service_id}", headers=ctx_a.headers)
    assert res.status_code == 404


def test_patch_other_tenants_service_returns_404(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.patch(
        f"{BASE_URL}/services/{ctx_b.service_id}",
        json={"is_active": False},
        headers=ctx_a.headers,
    )
    assert res.status_code == 404


def test_services_list_excludes_other_tenant(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.get(f"{BASE_URL}/services", headers=ctx_a.headers)
    assert res.status_code == 200
    ids = {item["id"] for item in res.json()}
    assert ctx_a.service_id in ids
    assert ctx_b.service_id not in ids


# --- customers (GET listesi/tekil var, PATCH yok) ---


def test_get_other_tenants_customer_returns_404(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.get(f"{BASE_URL}/customers/{ctx_b.customer_id}", headers=ctx_a.headers)
    assert res.status_code == 404


def test_customers_list_excludes_other_tenant(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.get(f"{BASE_URL}/customers", headers=ctx_a.headers)
    assert res.status_code == 200
    ids = {item["id"] for item in res.json()}
    assert ctx_a.customer_id in ids
    assert ctx_b.customer_id not in ids


# --- availability_rules (tekil GET yok, sadece liste + PATCH) ---


def test_patch_other_tenants_availability_rule_returns_404(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.patch(
        f"{BASE_URL}/availability_rules/{ctx_b.rule_id}",
        json={"start_time": "10:00:00"},
        headers=ctx_a.headers,
    )
    assert res.status_code == 404


def test_availability_rules_list_excludes_other_tenant(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.get(f"{BASE_URL}/availability_rules", headers=ctx_a.headers)
    assert res.status_code == 200
    ids = {item["id"] for item in res.json()}
    assert ctx_a.rule_id in ids
    assert ctx_b.rule_id not in ids


# --- appointments (en zengin endpoint kumesi: GET, PATCH, aksiyonlar) ---


def test_get_other_tenants_appointment_returns_404(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.get(f"{BASE_URL}/appointments/{ctx_b.appointment_id}", headers=ctx_a.headers)
    assert res.status_code == 404


def test_patch_other_tenants_appointment_returns_404(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.patch(
        f"{BASE_URL}/appointments/{ctx_b.appointment_id}",
        json={"start_at": "2026-09-16T11:00:00"},
        headers=ctx_a.headers,
    )
    assert res.status_code == 404


def test_confirm_other_tenants_appointment_returns_404(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.post(
        f"{BASE_URL}/appointments/{ctx_b.appointment_id}/confirm", headers=ctx_a.headers
    )
    assert res.status_code == 404

    # B'nin randevusu, A'nin basarisiz denemesinden ETKILENMEMIS olmali -
    # hala kendi tenant'inin kimligiyle normal sekilde erisilebilir ve
    # durumu degismemis (hala "pending").
    still_pending = requests.get(
        f"{BASE_URL}/appointments/{ctx_b.appointment_id}", headers=ctx_b.headers
    )
    assert still_pending.status_code == 200
    assert still_pending.json()["status"] == "pending"


def test_appointments_list_excludes_other_tenant(two_tenants):
    ctx_a, ctx_b = two_tenants
    res = requests.get(f"{BASE_URL}/appointments", headers=ctx_a.headers)
    assert res.status_code == 200
    ids = {item["id"] for item in res.json()}
    assert ctx_a.appointment_id in ids
    assert ctx_b.appointment_id not in ids
