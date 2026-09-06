"""Randevu olusturma/iptal, WhatsApp gonderim fonksiyonunu tetiklemeli -
ama gonderim basarisiz olsa (hatta exception firlatsa) bile randevu
islemi ETKILENMEMELI.

send_whatsapp_message, kullanildigi yerde (appointment_service modulunun
kendi namespace'inde) mock'lanir - "patch where it's used" pratigi.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from app.crypto import encrypt_token
from app.db import SessionLocal
from app.models import Customer, Service, StaffMember, Tenant
from app.services.appointment_service import cancel_appointment, create_appointment


@pytest.fixture
def whatsapp_connected_fixtures():
    db = SessionLocal()
    tenant = Tenant(
        name="Notify Test Tenant",
        whatsapp_phone_number_id="9998887776",
        whatsapp_access_token_encrypted=encrypt_token("fake-test-token"),
    )
    db.add(tenant)
    db.flush()

    staff = StaffMember(tenant_id=tenant.id, name="Notify Staff")
    service = Service(tenant_id=tenant.id, name="Notify Service", duration_minutes=30)
    customer = Customer(tenant_id=tenant.id, whatsapp_number="905551112222")
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


def test_create_appointment_triggers_whatsapp_notification(whatsapp_connected_fixtures):
    db, tenant_id, staff_id, service_id, customer_id = whatsapp_connected_fixtures

    with patch("app.services.appointment_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = True
        appointment = create_appointment(
            db,
            tenant_id=tenant_id,
            staff_id=staff_id,
            service_id=service_id,
            customer_id=customer_id,
            start_at=datetime(2026, 9, 7, 9, 0),
        )

    mock_send.assert_called_once()
    call = mock_send.call_args
    assert call.args[2] == "905551112222"  # to_number
    assert "Randevunuz onaylandı" in call.args[3]  # text
    assert appointment.status == "pending"


def test_send_whatsapp_message_failure_does_not_break_appointment_creation(
    whatsapp_connected_fixtures,
):
    db, tenant_id, staff_id, service_id, customer_id = whatsapp_connected_fixtures

    with patch(
        "app.services.appointment_service.send_whatsapp_message",
        side_effect=RuntimeError("boom"),
    ):
        appointment = create_appointment(
            db,
            tenant_id=tenant_id,
            staff_id=staff_id,
            service_id=service_id,
            customer_id=customer_id,
            start_at=datetime(2026, 9, 7, 10, 0),
        )

    assert appointment.id is not None
    assert appointment.status == "pending"


def test_cancel_appointment_triggers_whatsapp_notification(whatsapp_connected_fixtures):
    db, tenant_id, staff_id, service_id, customer_id = whatsapp_connected_fixtures

    appointment = create_appointment(
        db,
        tenant_id=tenant_id,
        staff_id=staff_id,
        service_id=service_id,
        customer_id=customer_id,
        start_at=datetime(2026, 9, 7, 11, 0),
    )

    with patch("app.services.appointment_service.send_whatsapp_message") as mock_send:
        mock_send.return_value = True
        cancel_appointment(db, tenant_id=tenant_id, appointment_id=appointment.id)

    mock_send.assert_called_once()
    call = mock_send.call_args
    assert call.args[2] == "905551112222"
    assert "iptal edildi" in call.args[3]


def test_send_whatsapp_message_failure_does_not_break_cancellation(whatsapp_connected_fixtures):
    db, tenant_id, staff_id, service_id, customer_id = whatsapp_connected_fixtures

    appointment = create_appointment(
        db,
        tenant_id=tenant_id,
        staff_id=staff_id,
        service_id=service_id,
        customer_id=customer_id,
        start_at=datetime(2026, 9, 7, 12, 0),
    )

    with patch(
        "app.services.appointment_service.send_whatsapp_message",
        side_effect=RuntimeError("boom"),
    ):
        cancelled = cancel_appointment(db, tenant_id=tenant_id, appointment_id=appointment.id)

    assert cancelled.status == "cancelled"
