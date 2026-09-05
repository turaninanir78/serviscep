"""API kurali: offset icermeyen (naive) start_at, tenant'in saat dilimi
olarak yorumlanir. Offset iceren start_at ise once tenant'in saat dilimine
cevrilir, sonra islenir.

Bu, gun sinirina yakin randevularda onemli: tenant Europe/Istanbul (UTC+3)
iken, UTC'de "bugun" gorunen bir an, tenant'in yerel takviminde "yarin"
olabilir. Cakisma kontrolu gun bazli sorgu yaptigi icin (bkz.
appointment_service._booked_intervals_for_staff_day), yanlis gune
cevirirse mevcut bir randevuyla cakismayi kacirabilir.
"""
from datetime import datetime, time, timedelta
from datetime import timezone as dt_timezone

import pytest
from fastapi import HTTPException

from app.db import SessionLocal
from app.models import AvailabilityRule, Customer, Service, StaffMember, Tenant
from app.services.appointment_service import create_appointment


@pytest.fixture
def tz_fixtures():
    db = SessionLocal()
    tenant = Tenant(name="TZ Test Tenant", timezone="Europe/Istanbul")
    db.add(tenant)
    db.flush()

    staff = StaffMember(tenant_id=tenant.id, name="TZ Test Staff")
    service = Service(tenant_id=tenant.id, name="TZ Test Service", duration_minutes=30)
    customer = Customer(tenant_id=tenant.id, whatsapp_number="905550000001")
    db.add_all([staff, service, customer])
    db.flush()

    # 2026-09-08 bir Sali (date.weekday() == 1). Gece yarisina yakin
    # randevulari test edebilmek icin genis (00:00-03:00) bir pencere.
    rule = AvailabilityRule(
        tenant_id=tenant.id,
        staff_id=staff.id,
        weekday=1,
        start_time=time(0, 0),
        end_time=time(3, 0),
    )
    db.add(rule)
    db.commit()

    yield db, tenant.id, staff.id, service.id, customer.id

    db.query(Tenant).filter(Tenant.id == tenant.id).delete()
    db.commit()
    db.close()


def test_naive_start_at_is_interpreted_as_tenant_local_time(tz_fixtures):
    db, tenant_id, staff_id, service_id, customer_id = tz_fixtures

    # Naive "01:00" -> Istanbul yerel saati (UTC+3) sayilmali, yani UTC'de
    # bir onceki gunun 22:00'i olarak saklanmali.
    appointment = create_appointment(
        db,
        tenant_id=tenant_id,
        staff_id=staff_id,
        service_id=service_id,
        customer_id=customer_id,
        start_at=datetime(2026, 9, 8, 1, 0),
    )

    assert appointment.start_at == datetime(2026, 9, 7, 22, 0, tzinfo=dt_timezone.utc)
    assert appointment.end_at == datetime(2026, 9, 7, 22, 30, tzinfo=dt_timezone.utc)


def test_offset_start_at_crossing_midnight_is_converted_to_tenant_day_before_conflict_check(
    tz_fixtures,
):
    db, tenant_id, staff_id, service_id, customer_id = tz_fixtures

    # Ilk randevu: Istanbul yerel saatiyle 01:00-01:30 (naive girdi).
    create_appointment(
        db,
        tenant_id=tenant_id,
        staff_id=staff_id,
        service_id=service_id,
        customer_id=customer_id,
        start_at=datetime(2026, 9, 8, 1, 0),
    )

    # Ikinci randevu: AYNI zaman araligiyla cakisan, ama UTC offset'iyle
    # gonderilen ve UTC takviminde ONCEKI gune (2026-09-07) denk dusen bir
    # girdi (2026-09-07T22:15Z = 2026-09-08T01:15+03:00). Dogru davranis:
    # bu, tenant'in yerel takviminde 08 Eylul'e ait sayilmali ve cakisma
    # UYGULAMA SEVIYESINDEKI on-kontrolde yakalanmali - DB'nin
    # EXCLUDE constraint'ine (migration 0003) hic dusmeden. Duzeltme
    # olmasaydi, `.date()` UTC'nin "07 Eylul"unu alir, yanlis gunun
    # randevularini sorgular ve bu cakismayi KACIRIRDI (409'u yalnizca
    # DB seviyesindeki constraint verirdi - farkli hata mesajiyla).
    with pytest.raises(HTTPException) as exc_info:
        create_appointment(
            db,
            tenant_id=tenant_id,
            staff_id=staff_id,
            service_id=service_id,
            customer_id=customer_id,
            start_at=datetime(2026, 9, 7, 22, 15, tzinfo=dt_timezone.utc),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Time slot conflicts with an existing appointment"


def test_offset_start_at_not_crossing_midnight_is_unaffected(tz_fixtures):
    db, tenant_id, staff_id, service_id, customer_id = tz_fixtures

    # +03:00 offset'iyle gonderilen, zaten Istanbul yerel saatiyle ayni olan
    # bir girdi - donusum sonucu degismemeli, sadece normalize edilmeli.
    plus_three = dt_timezone(timedelta(hours=3))
    appointment = create_appointment(
        db,
        tenant_id=tenant_id,
        staff_id=staff_id,
        service_id=service_id,
        customer_id=customer_id,
        start_at=datetime(2026, 9, 8, 1, 0, tzinfo=plus_three),
    )
    assert appointment.start_at == datetime(2026, 9, 7, 22, 0, tzinfo=dt_timezone.utc)
