from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.availability import (
    BookedInterval,
    WorkingWindow,
    compute_available_slots,
    has_conflict,
)
from app.models import Appointment, AvailabilityRule, Customer, Service, StaffMember, Tenant

# migration 0003_appointment_overlap_exclusion.py ile eklenen constraint adi.
_OVERLAP_EXCLUSION_CONSTRAINT_NAME = "excl_appointments_staff_time_overlap"


def _get_tenant(db: Session, tenant_id: int) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def _get_staff_or_404(db: Session, staff_id: int, tenant_id: int) -> StaffMember:
    staff = (
        db.query(StaffMember)
        .filter(StaffMember.id == staff_id, StaffMember.tenant_id == tenant_id)
        .first()
    )
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
    return staff


def _get_service_or_404(db: Session, service_id: int, tenant_id: int) -> Service:
    service = (
        db.query(Service)
        .filter(Service.id == service_id, Service.tenant_id == tenant_id)
        .first()
    )
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


def _get_customer_or_404(db: Session, customer_id: int, tenant_id: int) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    return customer


def _day_bounds(target_date: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=tz)
    return start, start + timedelta(days=1)


def _booked_intervals_for_staff_day(
    db: Session, tenant_id: int, staff_id: int, target_date: date, tz: ZoneInfo
) -> list[BookedInterval]:
    day_start, day_end = _day_bounds(target_date, tz)
    rows = (
        db.query(Appointment)
        .filter(
            Appointment.tenant_id == tenant_id,
            Appointment.staff_id == staff_id,
            Appointment.status != "cancelled",
            Appointment.start_at < day_end,
            Appointment.end_at > day_start,
        )
        .all()
    )
    return [BookedInterval(start_at=row.start_at, end_at=row.end_at) for row in rows]


def get_available_slots(
    db: Session, tenant_id: int, staff_id: int, service_id: int, target_date: date
) -> list[datetime]:
    tenant = _get_tenant(db, tenant_id)
    _get_staff_or_404(db, staff_id, tenant_id)
    service = _get_service_or_404(db, service_id, tenant_id)

    tz = ZoneInfo(tenant.timezone)
    weekday = target_date.weekday()

    rules = (
        db.query(AvailabilityRule)
        .filter(
            AvailabilityRule.tenant_id == tenant_id,
            AvailabilityRule.staff_id == staff_id,
            AvailabilityRule.weekday == weekday,
        )
        .all()
    )
    working_windows = [
        WorkingWindow(start_time=r.start_time, end_time=r.end_time) for r in rules
    ]

    booked = _booked_intervals_for_staff_day(db, tenant_id, staff_id, target_date, tz)

    return compute_available_slots(
        target_date=target_date,
        working_windows=working_windows,
        booked_intervals=booked,
        duration_minutes=service.duration_minutes,
        timezone=tenant.timezone,
    )


def create_appointment(
    db: Session,
    tenant_id: int,
    staff_id: int,
    service_id: int,
    customer_id: int,
    start_at: datetime,
) -> Appointment:
    tenant = _get_tenant(db, tenant_id)
    _get_staff_or_404(db, staff_id, tenant_id)
    service = _get_service_or_404(db, service_id, tenant_id)
    _get_customer_or_404(db, customer_id, tenant_id)

    tz = ZoneInfo(tenant.timezone)

    # Kural: offset icermeyen (naive) start_at, tenant'in saat dilimi olarak
    # yorumlanir. Offset iceren start_at ise ONCE tenant'in saat dilimine
    # cevrilir, sonra islenir - aksi halde asagidaki `.date()` cagrisi, gun
    # sinirina yakin randevularda (ornegin tenant UTC+3 iken UTC ile tenant
    # yerel takvimi farkli gune denk dusuyorsa) yanlis gunun mevcut
    # randevularini sorgulayip cakismayi kacirabilir.
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=tz)
    else:
        start_at = start_at.astimezone(tz)

    end_at = start_at + timedelta(minutes=service.duration_minutes)

    booked = _booked_intervals_for_staff_day(db, tenant_id, staff_id, start_at.date(), tz)
    for interval in booked:
        if has_conflict(start_at, end_at, interval.start_at, interval.end_at):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Time slot conflicts with an existing appointment",
            )

    appointment = Appointment(
        tenant_id=tenant_id,
        customer_id=customer_id,
        service_id=service_id,
        staff_id=staff_id,
        start_at=start_at,
        end_at=end_at,
        created_via="dashboard",
    )
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        # Uygulama seviyesindeki on-kontrolu (yukarida) es zamanli iki
        # istegin ikisi de gecebilir (biri commit etmeden diger okuma
        # yapabilir) - asil guvence excl_appointments_staff_time_overlap
        # constraint'idir (bkz. migration 0003). Buraya dusmek, on-kontrolun
        # yarisi kacirdigi ama DB'nin yakaladigi anlamina gelir.
        #
        # Sadece BU constraint'in ihlalini 409'a ceviriyoruz - baska bir
        # IntegrityError (ornegin beklenmedik bir kisitlama ihlali) burada
        # yutulup yanlislikla "cakisma" olarak raporlanmasin diye oldugu
        # gibi yeniden firlatilir (500 doner - beklenmeyen bir DB hatasi
        # oldugunu dogru yansitir).
        if _OVERLAP_EXCLUSION_CONSTRAINT_NAME not in str(exc.orig):
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Time slot conflicts with an existing appointment (detected by database constraint)",
        )
    db.refresh(appointment)
    return appointment
