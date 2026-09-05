from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.appointment_state import can_reschedule, can_transition_to
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


def _get_appointment_or_404(db: Session, appointment_id: int, tenant_id: int) -> Appointment:
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.tenant_id == tenant_id)
        .first()
    )
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


def _day_bounds(target_date: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(target_date, datetime.min.time(), tzinfo=tz)
    return start, start + timedelta(days=1)


def _booked_intervals_for_staff_day(
    db: Session,
    tenant_id: int,
    staff_id: int,
    target_date: date,
    tz: ZoneInfo,
    exclude_appointment_id: int | None = None,
) -> list[BookedInterval]:
    query = db.query(Appointment).filter(
        Appointment.tenant_id == tenant_id,
        Appointment.staff_id == staff_id,
        Appointment.status != "cancelled",
    )
    if exclude_appointment_id is not None:
        # Reschedule sirasinda randevunun kendisiyle cakisma sayilmamasi
        # icin - DB'deki EXCLUDE constraint UPDATE sirasinda satirin eski
        # halini zaten otomatik disliyor, ama uygulama seviyesindeki
        # on-kontrol (asagida has_conflict ile) bunu kendisi bilmiyor,
        # bu yuzden burada acikca disliyoruz.
        query = query.filter(Appointment.id != exclude_appointment_id)

    day_start, day_end = _day_bounds(target_date, tz)
    rows = query.filter(
        Appointment.start_at < day_end,
        Appointment.end_at > day_start,
    ).all()
    return [
        BookedInterval(start_at=row.start_at, end_at=row.end_at, buffer_minutes=row.buffer_minutes)
        for row in rows
    ]


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

    # Henuz olusturulmamis bir randevu icin buffer override bilinemez -
    # bu yuzden hizmetin varsayilan buffer'i kullanilir. Gercek randevu
    # olusturulurken bu deger override edilebilir (bkz. create_appointment);
    # bu durumda musait gorunen bir slot, override sonrasi farkli bir
    # cakisma durumuna yol acabilir - bu bilincli ve tutarli bir varsayimdir.
    return compute_available_slots(
        target_date=target_date,
        working_windows=working_windows,
        booked_intervals=booked,
        duration_minutes=service.duration_minutes,
        buffer_minutes=service.default_buffer_minutes,
        timezone=tenant.timezone,
    )


def create_appointment(
    db: Session,
    tenant_id: int,
    staff_id: int,
    service_id: int,
    customer_id: int,
    start_at: datetime,
    buffer_minutes: int | None = None,
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
    effective_buffer_minutes = (
        buffer_minutes if buffer_minutes is not None else service.default_buffer_minutes
    )

    booked = _booked_intervals_for_staff_day(db, tenant_id, staff_id, start_at.date(), tz)
    for interval in booked:
        if has_conflict(
            start_at,
            end_at,
            interval.start_at,
            interval.end_at,
            buffer_minutes=effective_buffer_minutes,
            other_buffer_minutes=interval.buffer_minutes,
        ):
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
        buffer_minutes=effective_buffer_minutes,
    )
    db.add(appointment)
    _commit_or_raise_conflict(db)
    db.refresh(appointment)
    return appointment


def _commit_or_raise_conflict(db: Session) -> None:
    """`db.commit()`'i, sadece bizim overlap-exclusion constraint'imizin
    ihlalini 409'a cevirerek calistirir; baska bir IntegrityError (ornegin
    beklenmedik bir kisitlama ihlali) burada yutulup yanlislikla "cakisma"
    olarak raporlanmasin diye oldugu gibi yeniden firlatilir (500 doner -
    beklenmeyen bir DB hatasi oldugunu dogru yansitir).

    Uygulama seviyesindeki on-kontrol (has_conflict ile, cagiran fonksiyonda)
    es zamanli iki istegin ikisi de gecebilir (biri commit etmeden diger
    okuma yapabilir) - asil guvence excl_appointments_staff_time_overlap
    constraint'idir (bkz. migration 0003). Buraya dusmek, on-kontrolun
    yarisi kacirdigi ama DB'nin yakaladigi anlamina gelir.
    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _OVERLAP_EXCLUSION_CONSTRAINT_NAME not in str(exc.orig):
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Time slot conflicts with an existing appointment (detected by database constraint)",
        )


def reschedule_appointment(
    db: Session,
    tenant_id: int,
    appointment_id: int,
    start_at: datetime | None = None,
    service_id: int | None = None,
    staff_id: int | None = None,
    buffer_minutes: int | None = None,
) -> Appointment:
    tenant = _get_tenant(db, tenant_id)
    appointment = _get_appointment_or_404(db, appointment_id, tenant_id)

    if not can_reschedule(appointment.status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot reschedule a {appointment.status!r} appointment",
        )

    new_staff_id = staff_id if staff_id is not None else appointment.staff_id
    new_service_id = service_id if service_id is not None else appointment.service_id
    new_buffer_minutes = (
        buffer_minutes if buffer_minutes is not None else appointment.buffer_minutes
    )

    _get_staff_or_404(db, new_staff_id, tenant_id)
    service = _get_service_or_404(db, new_service_id, tenant_id)

    tz = ZoneInfo(tenant.timezone)
    if start_at is None:
        new_start_at = appointment.start_at
    elif start_at.tzinfo is None:
        new_start_at = start_at.replace(tzinfo=tz)
    else:
        new_start_at = start_at.astimezone(tz)

    new_end_at = new_start_at + timedelta(minutes=service.duration_minutes)

    # Kendi kaydini disla - aksi halde randevu her zaman kendisiyle
    # "cakisirdi". DB'deki EXCLUDE constraint UPDATE sirasinda satirin eski
    # halini zaten otomatik disliyor (bkz. tests/test_appointment_lifecycle.py),
    # ama uygulama seviyesindeki bu on-kontrol bunu kendisi bilmedigi icin
    # acikca disliyoruz.
    booked = _booked_intervals_for_staff_day(
        db, tenant_id, new_staff_id, new_start_at.date(), tz,
        exclude_appointment_id=appointment.id,
    )
    for interval in booked:
        if has_conflict(
            new_start_at,
            new_end_at,
            interval.start_at,
            interval.end_at,
            buffer_minutes=new_buffer_minutes,
            other_buffer_minutes=interval.buffer_minutes,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Time slot conflicts with an existing appointment",
            )

    appointment.staff_id = new_staff_id
    appointment.service_id = new_service_id
    appointment.start_at = new_start_at
    appointment.end_at = new_end_at
    appointment.buffer_minutes = new_buffer_minutes

    _commit_or_raise_conflict(db)
    db.refresh(appointment)
    return appointment


def _transition_appointment_status(
    db: Session, tenant_id: int, appointment_id: int, target_status: str
) -> Appointment:
    appointment = _get_appointment_or_404(db, appointment_id, tenant_id)

    if not can_transition_to(appointment.status, target_status):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot transition appointment from {appointment.status!r} to {target_status!r}",
        )

    appointment.status = target_status
    db.commit()
    db.refresh(appointment)
    return appointment


def cancel_appointment(db: Session, tenant_id: int, appointment_id: int) -> Appointment:
    return _transition_appointment_status(db, tenant_id, appointment_id, "cancelled")


def complete_appointment(db: Session, tenant_id: int, appointment_id: int) -> Appointment:
    return _transition_appointment_status(db, tenant_id, appointment_id, "completed")


def mark_appointment_no_show(db: Session, tenant_id: int, appointment_id: int) -> Appointment:
    return _transition_appointment_status(db, tenant_id, appointment_id, "no_show")
