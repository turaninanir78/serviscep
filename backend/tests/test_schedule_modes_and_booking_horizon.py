"""GOREV: Calisma Plani (standart/esnek randevu modu + tarihe ozel
istisna) + randevu acik kalma suresi testleri.

Gercek kayitli bir owner hesabi + gercek HTTP istekleriyle, diger auth
sonrasi testlerle ayni yaklasim.
"""
import random
import string
from datetime import date, time, timedelta

import requests

from app.db import SessionLocal
from app.models import AvailabilityRule, Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"

# 2026-11-02 bir Pazartesi (weekday()==0) - testler boyunca sabit tutulan
# referans tarih.
MONDAY = date(2026, 11, 2)
NEXT_MONDAY = MONDAY + timedelta(days=7)


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _register_owner() -> tuple[requests.Session, str]:
    phone_raw = _random_phone_raw()
    session = requests.Session()
    otp_res = session.post(
        f"{BASE_URL}/auth/register/request-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
    )
    assert otp_res.status_code == 200, otp_res.text
    code = otp_res.json()["debug_code"]

    verify_res = session.post(
        f"{BASE_URL}/auth/register/verify-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw, "code": code},
    )
    registration_token = verify_res.json()["registration_token"]

    complete_res = session.post(
        f"{BASE_URL}/auth/register/complete",
        json={
            "registration_token": registration_token,
            "tenant_name": "Çalışma Planı Test İşletmesi",
            "password": "Owner-pw1!",
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


class _OwnerWithStaffAndService:
    def __init__(self):
        self.session, self.phone_raw = _register_owner()
        staff_list = self.session.get(f"{BASE_URL}/staff_members").json()
        self.staff_id = staff_list[0]["id"]
        service_res = self.session.post(
            f"{BASE_URL}/services", json={"name": "Kısa Hizmet", "duration_minutes": 15}
        )
        self.service_id = service_res.json()["id"]
        customer_res = self.session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905559990001"}
        )
        self.customer_id = customer_res.json()["id"]

    def cleanup(self) -> None:
        _cleanup_by_phone(self.phone_raw)


def _create_rule(ctx: _OwnerWithStaffAndService, **overrides) -> requests.Response:
    body = {
        "staff_id": ctx.staff_id,
        "weekday": MONDAY.weekday(),
        "start_time": "09:00:00",
        "end_time": "12:00:00",
    }
    body.update(overrides)
    return ctx.session.post(f"{BASE_URL}/availability_rules", json=body)


# --- Standart mod ---


def test_standard_mode_uses_fixed_slot_duration_regardless_of_service():
    ctx = _OwnerWithStaffAndService()
    try:
        rule_res = _create_rule(
            ctx, mode="standard", slot_duration_minutes=60, gap_minutes=10
        )
        assert rule_res.status_code == 201, rule_res.text

        slots_res = ctx.session.get(
            f"{BASE_URL}/availability/slots",
            params={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,  # 15 dk'lik kisa hizmet
                "date": MONDAY.isoformat(),
            },
        )
        assert slots_res.status_code == 200
        slots = slots_res.json()["slots"]
        # 09:00-12:00 (180 dk), 60+10=70 dk adimlarla: 09:00 (biter 10:00),
        # 10:10 (biter 11:10) - bir sonraki aday 11:20 olurdu ama
        # 11:20+60=12:20 pencereyi (12:00) astigi icin gecersiz -> 2 slot.
        assert len(slots) == 2
        assert "09:00:00" in slots[0]
        assert "10:10:00" in slots[1]
    finally:
        ctx.cleanup()


def test_standard_mode_requires_slot_duration_minutes():
    ctx = _OwnerWithStaffAndService()
    try:
        res = _create_rule(ctx, mode="standard", slot_duration_minutes=None)
        assert res.status_code == 422
    finally:
        ctx.cleanup()


def test_standard_mode_appointment_occupies_full_fixed_slot_not_service_duration():
    """15 dk'lik hizmet standart modda (60 dk slot) rezerve edilirse,
    randevu GERCEK hizmet suresi degil SABIT slot suresi kadar isgal
    etmeli - aksi halde ayni "slot"a ikinci bir randevu sigar ve "saatte
    bir randevu" kurali bozulur."""
    ctx = _OwnerWithStaffAndService()
    try:
        rule_res = _create_rule(ctx, mode="standard", slot_duration_minutes=60, gap_minutes=10)
        assert rule_res.status_code == 201

        create_res = ctx.session.post(
            f"{BASE_URL}/appointments",
            json={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,
                "customer_id": ctx.customer_id,
                "start_at": f"{MONDAY.isoformat()}T09:00:00",
            },
        )
        assert create_res.status_code == 201, create_res.text
        appointment = create_res.json()
        # end_at 09:00 (yerel) + 60 dk = 10:00 yerel = 07:00 UTC olmali
        # (hizmetin gercek suresi olan 15 dk DEGIL - API yanitlari UTC
        # donuyor, bkz. appointment["start_at"] de ayni sekilde -3 saat).
        assert "07:00:00" in appointment["end_at"]
        assert appointment["buffer_minutes"] == 10

        # Ayni "mantiksal slot" icinde (09:15 gibi, hizmetin gercek suresi
        # bitmis olsa bile) baska bir randevu olusturmaya calisilirsa
        # cakisma olarak reddedilmeli.
        conflict_res = ctx.session.post(
            f"{BASE_URL}/appointments",
            json={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,
                "customer_id": ctx.customer_id,
                "start_at": f"{MONDAY.isoformat()}T09:15:00",
            },
        )
        assert conflict_res.status_code == 409
    finally:
        ctx.cleanup()


def test_flexible_mode_is_default_and_unchanged():
    ctx = _OwnerWithStaffAndService()
    try:
        rule_res = _create_rule(ctx)  # mode belirtilmedi -> varsayilan flexible
        assert rule_res.status_code == 201
        assert rule_res.json()["mode"] == "flexible"

        slots_res = ctx.session.get(
            f"{BASE_URL}/availability/slots",
            params={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,  # 15 dk
                "date": MONDAY.isoformat(),
            },
        )
        slots = slots_res.json()["slots"]
        # 09:00-12:00 (180 dk), 15 dk'lik hizmet, buffer 0 -> 12 slot.
        assert len(slots) == 12
    finally:
        ctx.cleanup()


# --- Tarihe ozel istisna ---


def test_date_override_takes_precedence_over_weekly_rule_only_for_that_date():
    ctx = _OwnerWithStaffAndService()
    try:
        _create_rule(ctx)  # haftalik: her Pazartesi 09:00-12:00, flexible

        override_res = ctx.session.post(
            f"{BASE_URL}/availability_overrides",
            json={
                "staff_id": ctx.staff_id,
                "date": MONDAY.isoformat(),
                "start_time": "14:00:00",
                "end_time": "16:00:00",
                "mode": "flexible",
            },
        )
        assert override_res.status_code == 201, override_res.text

        overridden_day = ctx.session.get(
            f"{BASE_URL}/availability/slots",
            params={"staff_id": ctx.staff_id, "service_id": ctx.service_id, "date": MONDAY.isoformat()},
        ).json()["slots"]
        assert all("T14:" in s or "T15:" in s for s in overridden_day)

        # Bir sonraki Pazartesi (ayni haftanin gunu ama farkli tarih) hala
        # haftalik sablonu (09:00-12:00) kullanmali - istisna SADECE o
        # tarihe ozel.
        next_monday_slots = ctx.session.get(
            f"{BASE_URL}/availability/slots",
            params={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,
                "date": NEXT_MONDAY.isoformat(),
            },
        ).json()["slots"]
        assert all("T09:" in s or "T10:" in s or "T11:" in s for s in next_monday_slots)
    finally:
        ctx.cleanup()


def test_applying_override_to_weekly_template_changes_future_occurrences_too():
    ctx = _OwnerWithStaffAndService()
    try:
        _create_rule(ctx)  # haftalik: 09:00-12:00

        override_res = ctx.session.post(
            f"{BASE_URL}/availability_overrides",
            json={
                "staff_id": ctx.staff_id,
                "date": MONDAY.isoformat(),
                "start_time": "14:00:00",
                "end_time": "16:00:00",
                "apply_to_weekly_template": True,
            },
        )
        assert override_res.status_code == 201, override_res.text

        # Bir sonraki Pazartesi de artik 14:00-16:00 kullanmali (kalici
        # yapildi).
        next_monday_slots = ctx.session.get(
            f"{BASE_URL}/availability/slots",
            params={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,
                "date": NEXT_MONDAY.isoformat(),
            },
        ).json()["slots"]
        assert len(next_monday_slots) > 0
        assert all("T14:" in s or "T15:" in s for s in next_monday_slots)

        rules = ctx.session.get(f"{BASE_URL}/availability_rules").json()
        monday_rules = [r for r in rules if r["weekday"] == MONDAY.weekday()]
        assert len(monday_rules) == 1
        assert monday_rules[0]["start_time"] == "14:00:00"
    finally:
        ctx.cleanup()


def test_removing_override_reverts_date_to_weekly_template():
    ctx = _OwnerWithStaffAndService()
    try:
        _create_rule(ctx)  # 09:00-12:00

        override_res = ctx.session.post(
            f"{BASE_URL}/availability_overrides",
            json={
                "staff_id": ctx.staff_id,
                "date": MONDAY.isoformat(),
                "start_time": "14:00:00",
                "end_time": "16:00:00",
            },
        )
        override_id = override_res.json()["id"]

        remove_res = ctx.session.post(f"{BASE_URL}/availability_overrides/{override_id}/remove")
        assert remove_res.status_code == 204

        slots = ctx.session.get(
            f"{BASE_URL}/availability/slots",
            params={"staff_id": ctx.staff_id, "service_id": ctx.service_id, "date": MONDAY.isoformat()},
        ).json()["slots"]
        assert all("T09:" in s or "T10:" in s or "T11:" in s for s in slots)
    finally:
        ctx.cleanup()


# --- Randevu acik kalma suresi ---


def test_booking_horizon_hides_slots_beyond_limit_and_dynamically_shifts():
    ctx = _OwnerWithStaffAndService()
    try:
        settings_res = ctx.session.patch(
            f"{BASE_URL}/tenants/me/booking-settings", json={"max_advance_booking_days": 2}
        )
        assert settings_res.status_code == 200
        assert settings_res.json()["max_advance_booking_days"] == 2

        tenant_id = ctx.session.get(f"{BASE_URL}/tenants/me").json()["id"]
        today = date.today()
        within_horizon = today + timedelta(days=1)
        beyond_horizon = today + timedelta(days=5)

        db = SessionLocal()
        try:
            # within_horizon ve beyond_horizon farkli haftanin gunlerine
            # denk gelebilir - ikisi icin de ayri ayri "tum gun acik" kural
            # ekleniyor ki tek fark gercekten randevu acik kalma suresi olsun.
            for target_date in (within_horizon, beyond_horizon):
                db.add(
                    AvailabilityRule(
                        tenant_id=tenant_id,
                        staff_id=ctx.staff_id,
                        weekday=target_date.weekday(),
                        start_time=time(0, 0),
                        end_time=time(23, 59),
                    )
                )
            db.commit()
        finally:
            db.close()

        within_res = ctx.session.get(
            f"{BASE_URL}/availability/slots",
            params={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,
                "date": within_horizon.isoformat(),
            },
        )
        assert len(within_res.json()["slots"]) > 0

        beyond_res = ctx.session.get(
            f"{BASE_URL}/availability/slots",
            params={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,
                "date": beyond_horizon.isoformat(),
            },
        )
        assert beyond_res.json()["slots"] == []

        # Ayarı gevşetince (dinamik - "bugün + N gün" olarak yeniden
        # hesaplanır, ek bir işlem gerekmez) aynı tarih artık açık olmalı.
        ctx.session.patch(
            f"{BASE_URL}/tenants/me/booking-settings", json={"max_advance_booking_days": 30}
        )
        beyond_res_after = ctx.session.get(
            f"{BASE_URL}/availability/slots",
            params={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,
                "date": beyond_horizon.isoformat(),
            },
        )
        assert len(beyond_res_after.json()["slots"]) > 0
    finally:
        ctx.cleanup()


def test_creating_appointment_beyond_booking_horizon_is_rejected():
    ctx = _OwnerWithStaffAndService()
    try:
        ctx.session.patch(
            f"{BASE_URL}/tenants/me/booking-settings", json={"max_advance_booking_days": 1}
        )
        beyond_horizon = date.today() + timedelta(days=10)

        res = ctx.session.post(
            f"{BASE_URL}/appointments",
            json={
                "staff_id": ctx.staff_id,
                "service_id": ctx.service_id,
                "customer_id": ctx.customer_id,
                "start_at": f"{beyond_horizon.isoformat()}T09:00:00",
            },
        )
        assert res.status_code == 409
    finally:
        ctx.cleanup()


def test_booking_settings_reject_non_positive_value():
    ctx = _OwnerWithStaffAndService()
    try:
        res = ctx.session.patch(
            f"{BASE_URL}/tenants/me/booking-settings", json={"max_advance_booking_days": 0}
        )
        assert res.status_code == 422
    finally:
        ctx.cleanup()


def test_booking_settings_accept_null_for_unlimited():
    ctx = _OwnerWithStaffAndService()
    try:
        ctx.session.patch(
            f"{BASE_URL}/tenants/me/booking-settings", json={"max_advance_booking_days": 3}
        )
        res = ctx.session.patch(
            f"{BASE_URL}/tenants/me/booking-settings", json={"max_advance_booking_days": None}
        )
        assert res.status_code == 200
        assert res.json()["max_advance_booking_days"] is None
    finally:
        ctx.cleanup()
