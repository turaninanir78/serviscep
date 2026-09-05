from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Appointment
from app.schemas.appointment import AppointmentCreate, AppointmentOut
from app.security import AuthContext, get_current_tenant
from app.services.appointment_service import create_appointment

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
