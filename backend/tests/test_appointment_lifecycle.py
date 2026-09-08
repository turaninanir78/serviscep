"""Reschedule / cancel / complete / no-show yasam dongusu testleri.

app/core/appointment_state.py'deki durum makinesinin ve
appointment_service.py'deki reschedule/cancel/complete/no_show
fonksiyonlarinin gercek DB'ye karsi dogru calistigini dogrular.
"""
from datetime import datetime

import pytest
from fastapi import HTTPException

from app.db import SessionLocal
from app.models import Customer, Service, StaffMember, Tenant
from app.services.appointment_service import (
    cancel_appointment,
    complete_appointment,
    confirm_appointment,
    create_appointment,
    reschedule_appointment,
)


@pytest.fixture
def fixtures():
    db = SessionLocal()
    tenant = Tenant(name="Lifecycle Test Tenant")
    db.add(tenant)
    db.flush()

    staff = StaffMember(tenant_id=tenant.id, name="Lifecycle Staff")
    service = Service(tenant_id=tenant.id, name="Lifecycle Service", duration_minutes=30)
    customer = Customer(tenant_id=tenant.id, whatsapp_number="905550001234")
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


def test_reschedule_ignores_own_record_but_still_catches_other_conflicts(fixtures):
    db, tenant_id, staff_id, service_id, customer_id = fixtures

    a = create_appointment(
        db, tenant_id=tenant_id, staff_id=staff_id, service_id=service_id,
        customer_id=customer_id, start_at=datetime(2026, 9, 7, 9, 0),
    )
    create_appointment(
        db, tenant_id=tenant_id, staff_id=staff_id, service_id=service_id,
        customer_id=customer_id, start_at=datetime(2026, 9, 7, 10, 0),
    )

    # A'yi ayni saate "tasimak" - kendi kaydiyla cakisma sayilmamali.
    rescheduled = reschedule_appointment(
        db, tenant_id=tenant_id, appointment_id=a.id,
        start_at=datetime(2026, 9, 7, 9, 0),
    )
    assert rescheduled.id == a.id

    # A'yi B'nin saatine (10:00) tasimaya calismak GERCEK bir cakisma.
    with pytest.raises(HTTPException) as exc_info:
        reschedule_appointment(
            db, tenant_id=tenant_id, appointment_id=a.id,
            start_at=datetime(2026, 9, 7, 10, 0),
        )
    assert exc_info.value.status_code == 409


def test_db_exclude_constraint_permits_updating_same_row_in_place(fixtures):
    db, tenant_id, staff_id, service_id, customer_id = fixtures

    a = create_appointment(
        db, tenant_id=tenant_id, staff_id=staff_id, service_id=service_id,
        customer_id=customer_id, start_at=datetime(2026, 9, 7, 15, 0),
    )

    # Uygulama seviyesindeki on-kontrolu (has_conflict / exclude_appointment_id)
    # HIC calistirmadan, dogrudan ORM uzerinden ayni randevunun buffer'ini
    # degistirip commit ediyoruz. Bu, DB'deki EXCLUDE constraint'in kendi
    # (guncellenen) satirini otomatik disladigini izole olarak kanitlar -
    # aksi halde bu UPDATE kendi eski haliyle "cakisir" ve reddedilirdi.
    a.buffer_minutes = 5
    db.commit()
    db.refresh(a)
    assert a.buffer_minutes == 5


def test_cancelled_appointment_slot_can_be_rebooked(fixtures):
    db, tenant_id, staff_id, service_id, customer_id = fixtures

    a = create_appointment(
        db, tenant_id=tenant_id, staff_id=staff_id, service_id=service_id,
        customer_id=customer_id, start_at=datetime(2026, 9, 7, 11, 0),
    )
    cancel_appointment(db, tenant_id=tenant_id, appointment_id=a.id)

    # Ayni slot artik baska bir randevu icin kullanilabilmeli.
    b = create_appointment(
        db, tenant_id=tenant_id, staff_id=staff_id, service_id=service_id,
        customer_id=customer_id, start_at=datetime(2026, 9, 7, 11, 0),
    )
    assert b.id is not None
    assert b.status == "pending"


def test_confirm_transitions_pending_to_confirmed(fixtures):
    db, tenant_id, staff_id, service_id, customer_id = fixtures

    a = create_appointment(
        db, tenant_id=tenant_id, staff_id=staff_id, service_id=service_id,
        customer_id=customer_id, start_at=datetime(2026, 9, 7, 16, 0),
    )
    assert a.status == "pending"

    confirmed = confirm_appointment(db, tenant_id=tenant_id, appointment_id=a.id)
    assert confirmed.id == a.id
    assert confirmed.status == "confirmed"


def test_confirming_already_confirmed_appointment_returns_409(fixtures):
    db, tenant_id, staff_id, service_id, customer_id = fixtures

    a = create_appointment(
        db, tenant_id=tenant_id, staff_id=staff_id, service_id=service_id,
        customer_id=customer_id, start_at=datetime(2026, 9, 7, 17, 0),
    )
    confirm_appointment(db, tenant_id=tenant_id, appointment_id=a.id)

    with pytest.raises(HTTPException) as exc_info:
        confirm_appointment(db, tenant_id=tenant_id, appointment_id=a.id)
    assert exc_info.value.status_code == 409


def test_confirming_terminal_appointment_returns_409(fixtures):
    db, tenant_id, staff_id, service_id, customer_id = fixtures

    a = create_appointment(
        db, tenant_id=tenant_id, staff_id=staff_id, service_id=service_id,
        customer_id=customer_id, start_at=datetime(2026, 9, 7, 18, 0),
    )
    cancel_appointment(db, tenant_id=tenant_id, appointment_id=a.id)

    with pytest.raises(HTTPException) as exc_info:
        confirm_appointment(db, tenant_id=tenant_id, appointment_id=a.id)
    assert exc_info.value.status_code == 409


def test_invalid_status_transitions_return_409(fixtures):
    db, tenant_id, staff_id, service_id, customer_id = fixtures

    a = create_appointment(
        db, tenant_id=tenant_id, staff_id=staff_id, service_id=service_id,
        customer_id=customer_id, start_at=datetime(2026, 9, 7, 13, 0),
    )
    complete_appointment(db, tenant_id=tenant_id, appointment_id=a.id)

    with pytest.raises(HTTPException) as exc_info:
        cancel_appointment(db, tenant_id=tenant_id, appointment_id=a.id)
    assert exc_info.value.status_code == 409

    with pytest.raises(HTTPException) as exc_info:
        reschedule_appointment(
            db, tenant_id=tenant_id, appointment_id=a.id,
            start_at=datetime(2026, 9, 7, 14, 0),
        )
    assert exc_info.value.status_code == 409
