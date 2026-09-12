from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.access_log import log_access
from app.db import get_db
from app.models import Appointment
from app.permissions import require_own_staff_resource, require_permission
from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentReschedule
from app.security import AuthContext, get_current_tenant
from app.services.appointment_service import (
    cancel_appointment,
    complete_appointment,
    confirm_appointment,
    create_appointment,
    mark_appointment_no_show,
    reschedule_appointment,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])


def _own_appointment_or_404(db: Session, auth: AuthContext, appointment_id: int) -> Appointment:
    """Personel (role="staff"), yetkisi acik olsa bile SADECE KENDI
    staff_id'sine atanmis randevulari gorup yonetebilir - bkz.
    app/permissions.py::require_own_staff_resource. Owner icin normal
    tenant-genelinde arama."""
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.tenant_id == auth.tenant_id)
        .first()
    )
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    require_own_staff_resource(auth, appointment.staff_id)
    return appointment


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment_endpoint(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_permission(auth, "can_create_appointments")
    require_own_staff_resource(auth, payload.staff_id)
    return create_appointment(
        db,
        tenant_id=auth.tenant_id,
        staff_id=payload.staff_id,
        service_id=payload.service_id,
        customer_id=payload.customer_id,
        start_at=payload.start_at,
        buffer_minutes=payload.buffer_minutes,
    )


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_tenant)
):
    # Personelin kendi randevularini GORMESI bir izin anahtariyla
    # korunmuyor (bkz. gorev ozeti - klinik ornegi: hekim en azindan
    # kendi randevularini gorebilmeli) - sadece OTOMATIK olarak kendi
    # staff_id'sine daraltiliyor. Owner her zaman tenant genelini gorur.
    query = db.query(Appointment).filter(Appointment.tenant_id == auth.tenant_id)
    if auth.role == "staff":
        query = query.filter(Appointment.staff_id == auth.staff_member_id)
    return query.all()


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    appointment = _own_appointment_or_404(db, auth, appointment_id)
    log_access(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        resource_type="appointment",
        resource_id=appointment.id,
        action="GET",
    )
    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def reschedule_appointment_endpoint(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_permission(auth, "can_create_appointments")
    _own_appointment_or_404(db, auth, appointment_id)
    if payload.staff_id is not None:
        require_own_staff_resource(auth, payload.staff_id)
    result = reschedule_appointment(
        db,
        tenant_id=auth.tenant_id,
        appointment_id=appointment_id,
        start_at=payload.start_at,
        service_id=payload.service_id,
        staff_id=payload.staff_id,
        buffer_minutes=payload.buffer_minutes,
    )
    log_access(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        resource_type="appointment",
        resource_id=appointment_id,
        action="PATCH",
    )
    return result


@router.post("/{appointment_id}/confirm", response_model=AppointmentOut)
def confirm_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_permission(auth, "can_confirm_complete_appointments")
    _own_appointment_or_404(db, auth, appointment_id)
    result = confirm_appointment(db, tenant_id=auth.tenant_id, appointment_id=appointment_id)
    log_access(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        resource_type="appointment",
        resource_id=appointment_id,
        action="PATCH",
    )
    return result


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_permission(auth, "can_cancel_appointments")
    _own_appointment_or_404(db, auth, appointment_id)
    result = cancel_appointment(db, tenant_id=auth.tenant_id, appointment_id=appointment_id)
    log_access(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        resource_type="appointment",
        resource_id=appointment_id,
        action="PATCH",
    )
    return result


@router.post("/{appointment_id}/complete", response_model=AppointmentOut)
def complete_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_permission(auth, "can_confirm_complete_appointments")
    _own_appointment_or_404(db, auth, appointment_id)
    result = complete_appointment(db, tenant_id=auth.tenant_id, appointment_id=appointment_id)
    log_access(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        resource_type="appointment",
        resource_id=appointment_id,
        action="PATCH",
    )
    return result


@router.post("/{appointment_id}/no-show", response_model=AppointmentOut)
def mark_appointment_no_show_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_permission(auth, "can_confirm_complete_appointments")
    _own_appointment_or_404(db, auth, appointment_id)
    result = mark_appointment_no_show(db, tenant_id=auth.tenant_id, appointment_id=appointment_id)
    log_access(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        resource_type="appointment",
        resource_id=appointment_id,
        action="PATCH",
    )
    return result
