import logging
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.appointment_state import can_reschedule, can_transition_to
from app.core.availability import (
    BookedInterval,
    WorkingWindow,
    compute_available_slots,
    has_conflict,
)
from app.integrations.whatsapp import send_whatsapp_message
from app.models import (
    Appointment,
    AvailabilityOverride,
    AvailabilityRule,
    Customer,
    Service,
    StaffMember,
    Tenant,
)

logger = logging.getLogger(__name__)

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
    # Bir onceki gunden gelen bir randevunun buffer'i yeni gune tasabilir
    # (ör. 23:50'de biten + 30 dk buffer -> ertesi gunun 00:20'sine kadar
    # isgal). Sadece `end_at > day_start` kontrolu bu randevuyu kacirir -
    # etkin bitisi (`end_at + buffer_minutes`) kullanilmali, aksi halde bu
    # gunun ilk dakikalari yanlislikla bos gorunur (DB'deki EXCLUDE
    # constraint yine de dogru reddeder, ama kullanici once "bos" gorur).
    effective_end_at = Appointment.end_at + func.make_interval(
        0, 0, 0, 0, 0, Appointment.buffer_minutes
    )
    rows = query.filter(
        Appointment.start_at < day_end,
        effective_end_at > day_start,
    ).all()
    return [
        BookedInterval(start_at=row.start_at, end_at=row.end_at, buffer_minutes=row.buffer_minutes)
        for row in rows
    ]


def _within_booking_horizon(tenant: Tenant, target_date: date) -> bool:
    """Randevu acik kalma suresi (bkz. app/models.py::
    Tenant.max_advance_booking_days) - HER ZAMAN "bugun + N gun" olarak
    DINAMIK hesaplanir, sabit bir tarih hic saklanmaz - deger
    degistiginde veya gun ilerledikce pencere otomatik kayar (bkz. gorev
    ozeti: "o anlık tarihe göre plan açılmalı")."""
    if tenant.max_advance_booking_days is None:
        return True
    today_local = datetime.now(ZoneInfo(tenant.timezone)).date()
    return target_date <= today_local + timedelta(days=tenant.max_advance_booking_days)


def _rule_rows_for_date(
    db: Session, tenant_id: int, staff_id: int, target_date: date
) -> list[AvailabilityRule | AvailabilityOverride]:
    """O tarihe ozel bir istisna (AvailabilityOverride) varsa haftalik
    sablon YERINE onu, yoksa haftalik AvailabilityRule'u doner - bkz.
    app/models.py::AvailabilityOverride docstring'i. Bu oncelik sirasi
    get_available_slots ile randevu olusturma/erteleme arasinda TUTARLI
    olmali, aksi halde "musait" gorunen bir slot olusturma anda farkli
    bir kurala tabi olabilir."""
    overrides = (
        db.query(AvailabilityOverride)
        .filter(
            AvailabilityOverride.tenant_id == tenant_id,
            AvailabilityOverride.staff_id == staff_id,
            AvailabilityOverride.date == target_date,
        )
        .all()
    )
    if overrides:
        return overrides

    weekday = target_date.weekday()
    return (
        db.query(AvailabilityRule)
        .filter(
            AvailabilityRule.tenant_id == tenant_id,
            AvailabilityRule.staff_id == staff_id,
            AvailabilityRule.weekday == weekday,
        )
        .all()
    )


def _standard_override_from_rows(
    rule_rows: list[AvailabilityRule | AvailabilityOverride],
) -> tuple[int, int] | None:
    """Satirlar arasinda "standard" modda olan varsa (slot_duration_minutes,
    gap_minutes) dondurur, hepsi "flexible" ise (veya hic satir yoksa) None -
    bu durumda cagiran taraf KENDI mevcut varsayilan (hizmet suresi/buffer)
    mantigini DEGISTIRMEDEN kullanmaya devam eder (bkz. gorev ozeti: mevcut
    kurallar bundan hic etkilenmemeli). Birden fazla satir varsa (ayni gun
    icin coklu pencere) ilk "standard" satirin degerleri kullanilir - bu
    gunun TEK bir moda sahip oldugu varsayimina dayanir (UI, ayni gunun tum
    pencerelerini ayni modda tutacak sekilde tasarlandi)."""
    standard_row = next((r for r in rule_rows if r.mode == "standard"), None)
    if standard_row is None:
        return None
    return standard_row.slot_duration_minutes, standard_row.gap_minutes


def get_available_slots(
    db: Session, tenant_id: int, staff_id: int, service_id: int, target_date: date
) -> list[datetime]:
    tenant = _get_tenant(db, tenant_id)
    _get_staff_or_404(db, staff_id, tenant_id)
    service = _get_service_or_404(db, service_id, tenant_id)

    if not _within_booking_horizon(tenant, target_date):
        return []

    tz = ZoneInfo(tenant.timezone)

    rule_rows = _rule_rows_for_date(db, tenant_id, staff_id, target_date)
    working_windows = [
        WorkingWindow(start_time=r.start_time, end_time=r.end_time) for r in rule_rows
    ]
    override = _standard_override_from_rows(rule_rows)
    if override is not None:
        duration_minutes, buffer_minutes = override
    else:
        duration_minutes, buffer_minutes = service.duration_minutes, service.default_buffer_minutes

    booked = _booked_intervals_for_staff_day(db, tenant_id, staff_id, target_date, tz)

    # Henuz olusturulmamis bir randevu icin buffer override bilinemez -
    # bu yuzden hizmetin varsayilan buffer'i kullanilir (standard modda
    # zaten sabit gap_minutes kullanilir, cagiranin override'i gecersiz
    # sayilir - bkz. _resolve_slot_duration_and_buffer). Gercek randevu
    # olusturulurken flexible modda bu deger override edilebilir (bkz.
    # create_appointment); bu durumda musait gorunen bir slot, override
    # sonrasi farkli bir cakisma durumuna yol acabilir - bu bilincli ve
    # tutarli bir varsayimdir.
    return compute_available_slots(
        target_date=target_date,
        working_windows=working_windows,
        booked_intervals=booked,
        duration_minutes=duration_minutes,
        buffer_minutes=buffer_minutes,
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
    customer = _get_customer_or_404(db, customer_id, tenant_id)

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

    if not _within_booking_horizon(tenant, start_at.date()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Randevular en fazla {tenant.max_advance_booking_days} gün öncesinden alınabilir.",
        )

    override = _standard_override_from_rows(
        _rule_rows_for_date(db, tenant_id, staff_id, start_at.date())
    )
    if override is not None:
        duration_minutes, effective_buffer_minutes = override
    else:
        duration_minutes = service.duration_minutes
        effective_buffer_minutes = (
            buffer_minutes if buffer_minutes is not None else service.default_buffer_minutes
        )
    end_at = start_at + timedelta(minutes=duration_minutes)

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

    _notify_appointment_created(db, tenant, customer, appointment)

    return appointment


def _format_local_datetime(appointment: Appointment, tenant: Tenant) -> str:
    tz = ZoneInfo(tenant.timezone)
    local_start = appointment.start_at.astimezone(tz)
    return local_start.strftime("%d.%m.%Y %H:%M")


def _notify_appointment_created(
    db: Session, tenant: Tenant, customer: Customer, appointment: Appointment
) -> None:
    if not (
        tenant.whatsapp_phone_number_id
        and tenant.whatsapp_access_token_encrypted
        and customer.whatsapp_number
    ):
        return

    text = f"Randevunuz onaylandı: {_format_local_datetime(appointment, tenant)}"
    try:
        send_whatsapp_message(db, tenant, customer.whatsapp_number, text, customer_id=customer.id)
    except Exception:
        # send_whatsapp_message zaten kendi icinde tum hatalari yutar ve
        # exception firlatmaz; bu try/except, ileride o sozlesme bozulursa
        # bile randevu akisinin ASLA etkilenmemesini garanti eden ikinci
        # bir savunma katmani.
        logger.exception(
            "WhatsApp onay bildirimi gonderilemedi (appointment_id=%s)", appointment.id
        )


def _notify_appointment_cancelled(
    db: Session, tenant: Tenant, customer: Customer, appointment: Appointment
) -> None:
    if not (
        tenant.whatsapp_phone_number_id
        and tenant.whatsapp_access_token_encrypted
        and customer.whatsapp_number
    ):
        return

    text = f"Randevunuz iptal edildi: {_format_local_datetime(appointment, tenant)}"
    try:
        send_whatsapp_message(db, tenant, customer.whatsapp_number, text, customer_id=customer.id)
    except Exception:
        logger.exception(
            "WhatsApp iptal bildirimi gonderilemedi (appointment_id=%s)", appointment.id
        )


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

    if not _within_booking_horizon(tenant, new_start_at.date()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Randevular en fazla {tenant.max_advance_booking_days} gün öncesinden alınabilir.",
        )

    override = _standard_override_from_rows(
        _rule_rows_for_date(db, tenant_id, new_staff_id, new_start_at.date())
    )
    if override is not None:
        new_duration_minutes, new_buffer_minutes = override
    else:
        new_duration_minutes = service.duration_minutes
    new_end_at = new_start_at + timedelta(minutes=new_duration_minutes)

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


def confirm_appointment(db: Session, tenant_id: int, appointment_id: int) -> Appointment:
    return _transition_appointment_status(db, tenant_id, appointment_id, "confirmed")


def cancel_appointment(db: Session, tenant_id: int, appointment_id: int) -> Appointment:
    appointment = _transition_appointment_status(db, tenant_id, appointment_id, "cancelled")

    tenant = _get_tenant(db, tenant_id)
    customer = _get_customer_or_404(db, appointment.customer_id, tenant_id)
    _notify_appointment_cancelled(db, tenant, customer, appointment)

    return appointment


def complete_appointment(db: Session, tenant_id: int, appointment_id: int) -> Appointment:
    return _transition_appointment_status(db, tenant_id, appointment_id, "completed")


def mark_appointment_no_show(db: Session, tenant_id: int, appointment_id: int) -> Appointment:
    return _transition_appointment_status(db, tenant_id, appointment_id, "no_show")
