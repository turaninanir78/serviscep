from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Appointment
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


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment_endpoint(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
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
    return db.query(Appointment).filter(Appointment.tenant_id == auth.tenant_id).all()


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    appointment = (
        db.query(Appointment)
        .filter(Appointment.id == appointment_id, Appointment.tenant_id == auth.tenant_id)
        .first()
    )
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")
    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def reschedule_appointment_endpoint(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    return reschedule_appointment(
        db,
        tenant_id=auth.tenant_id,
        appointment_id=appointment_id,
        start_at=payload.start_at,
        service_id=payload.service_id,
        staff_id=payload.staff_id,
        buffer_minutes=payload.buffer_minutes,
    )


@router.post("/{appointment_id}/confirm", response_model=AppointmentOut)
def confirm_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    return confirm_appointment(db, tenant_id=auth.tenant_id, appointment_id=appointment_id)


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    return cancel_appointment(db, tenant_id=auth.tenant_id, appointment_id=appointment_id)


@router.post("/{appointment_id}/complete", response_model=AppointmentOut)
def complete_appointment_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    return complete_appointment(db, tenant_id=auth.tenant_id, appointment_id=appointment_id)


@router.post("/{appointment_id}/no-show", response_model=AppointmentOut)
def mark_appointment_no_show_endpoint(
    appointment_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    return mark_appointment_no_show(db, tenant_id=auth.tenant_id, appointment_id=appointment_id)
