"""has_conflict (Python) ile excl_appointments_staff_time_overlap (Postgres
EXCLUDE constraint, migration 0003) AYNI sonucu vermeli - biri "cakisma yok"
derken diger "cakisiyor" derse, kullanici "bos" gordugu bir slotta
beklenmedik bir 409/500 alir. Bu test, has_conflict'in FALSE dedigi bir
ciftin gercekten DB'ye yazilabildigini, TRUE dedigi bir ciftin ise DB
tarafindan da reddedildigini dogrudan kontrol eder.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core.availability import has_conflict
from app.db import SessionLocal
from app.models import Appointment, AvailabilityRule, Customer, Service, StaffMember, Tenant
from app.services.appointment_service import create_appointment, get_available_slots

TZ = ZoneInfo("Europe/Istanbul")


@pytest.fixture
def db_fixtures():
    db = SessionLocal()
    tenant = Tenant(name="Buffer Consistency Tenant")
    db.add(tenant)
    db.flush()

    staff = StaffMember(tenant_id=tenant.id, name="Buffer Test Staff")
    service = Service(tenant_id=tenant.id, name="Buffer Test Service", duration_minutes=30)
    customer = Customer(tenant_id=tenant.id, whatsapp_number="905550009999")
    db.add_all([staff, service, customer])
    db.commit()
    db.refresh(staff)
    db.refresh(service)
    db.refresh(customer)

    yield db, tenant.id, staff.id, service.id, customer.id

    db.rollback()
    db.query(Tenant).filter(Tenant.id == tenant.id).delete()
    db.commit()
    db.close()


def _make_appointment(tenant_id, staff_id, service_id, customer_id, start_at, end_at, buffer_minutes):
    return Appointment(
        tenant_id=tenant_id,
        staff_id=staff_id,
        service_id=service_id,
        customer_id=customer_id,
        start_at=start_at,
        end_at=end_at,
        created_via="dashboard",
        buffer_minutes=buffer_minutes,
    )


def test_has_conflict_matches_db_exclusion_constraint(db_fixtures):
    db, tenant_id, staff_id, service_id, customer_id = db_fixtures

    # Randevu A: 09:00-09:30, buffer=10 -> efektif isgal [09:00, 09:40).
    a_start = datetime(2026, 9, 7, 9, 0, tzinfo=TZ)
    a_end = a_start + timedelta(minutes=30)
    appointment_a = _make_appointment(
        tenant_id, staff_id, service_id, customer_id, a_start, a_end, buffer_minutes=10
    )
    db.add(appointment_a)
    db.commit()

    # --- Durum 1: has_conflict "False" diyor (sinira tam dokunma, 09:40'ta
    # basliyor) -> DB'ye de gercekten yazilabilmeli. ---
    b_start = a_end + timedelta(minutes=10)  # 09:40
    b_end = b_start + timedelta(minutes=20)  # 10:00
    assert (
        has_conflict(
            b_start, b_end, appointment_a.start_at, appointment_a.end_at,
            buffer_minutes=0, other_buffer_minutes=appointment_a.buffer_minutes,
        )
        is False
    )

    appointment_b = _make_appointment(
        tenant_id, staff_id, service_id, customer_id, b_start, b_end, buffer_minutes=0
    )
    db.add(appointment_b)
    db.commit()  # IntegrityError firlatmamali
    assert appointment_b.id is not None

    # --- Durum 2: has_conflict "True" diyor (A'nin buffer penceresi
    # icinde, 09:35'te basliyor) -> DB de reddetmeli. ---
    c_start = a_start + timedelta(minutes=35)  # 09:35
    c_end = c_start + timedelta(minutes=20)  # 09:55
    assert (
        has_conflict(
            c_start, c_end, appointment_a.start_at, appointment_a.end_at,
            buffer_minutes=0, other_buffer_minutes=appointment_a.buffer_minutes,
        )
        is True
    )

    appointment_c = _make_appointment(
        tenant_id, staff_id, service_id, customer_id, c_start, c_end, buffer_minutes=0
    )
    db.add(appointment_c)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_cross_day_buffer_spillover_blocks_next_day_slot(db_fixtures):
    # Onceki gunden gelen bir randevunun buffer'i yeni gune tasabilir.
    # Randevu: 2026-09-07 (Pazartesi) 23:20-23:50, buffer=30 dk -> etkin
    # isgal 2026-09-08 (Sali) 00:20'ye kadar suruyor.
    db, tenant_id, staff_id, service_id, customer_id = db_fixtures

    # 2026-09-08 bir Sali (date.weekday() == 1). Gece yarisindan hemen sonra
    # da musaitlik olsun ki spillover'in etkisini gorebilelim.
    db.add(
        AvailabilityRule(
            tenant_id=tenant_id,
            staff_id=staff_id,
            weekday=1,
            start_time=time(0, 0),
            end_time=time(3, 0),
        )
    )
    db.commit()

    create_appointment(
        db,
        tenant_id=tenant_id,
        staff_id=staff_id,
        service_id=service_id,
        customer_id=customer_id,
        start_at=datetime(2026, 9, 7, 23, 20),  # naive -> tenant yerel saati
        buffer_minutes=30,
    )

    # Ertesi gunun (08 Eylul) 00:00 slotu artik BOS GORUNMEMELI - onceki
    # randevunun buffer'i 00:20'ye kadar isgal ediyor.
    slots = get_available_slots(db, tenant_id, staff_id, service_id, target_date=date(2026, 9, 8))
    assert datetime(2026, 9, 8, 0, 0, tzinfo=TZ) not in slots

    # O saatte randevu olusturma denemesi de engellenmeli.
    with pytest.raises(HTTPException) as exc_info:
        create_appointment(
            db,
            tenant_id=tenant_id,
            staff_id=staff_id,
            service_id=service_id,
            customer_id=customer_id,
            start_at=datetime(2026, 9, 8, 0, 10),
        )
    assert exc_info.value.status_code == 409
