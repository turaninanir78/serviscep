from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.appointment import AvailableSlotsResponse
from app.security import AuthContext, get_current_tenant
from app.services.appointment_service import get_available_slots

router = APIRouter(prefix="/availability", tags=["availability"])


@router.get("/slots", response_model=AvailableSlotsResponse)
def read_available_slots(
    staff_id: int = Query(...),
    service_id: int = Query(...),
    date: date_type = Query(...),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    slots = get_available_slots(db, auth.tenant_id, staff_id, service_id, date)
    return AvailableSlotsResponse(
        date=date, staff_id=staff_id, service_id=service_id, slots=slots
    )
