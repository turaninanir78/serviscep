from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AvailabilityOverride, AvailabilityRule, StaffMember
from app.permissions import require_own_staff_resource, require_permission
from app.schemas.availability_override import AvailabilityOverrideCreate, AvailabilityOverrideOut
from app.security import AuthContext, get_current_tenant

router = APIRouter(prefix="/availability_overrides", tags=["availability_overrides"])


def _get_staff_or_404(db: Session, staff_id: int, tenant_id: int) -> StaffMember:
    staff = (
        db.query(StaffMember)
        .filter(StaffMember.id == staff_id, StaffMember.tenant_id == tenant_id)
        .first()
    )
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
    return staff


@router.post("", response_model=AvailabilityOverrideOut, status_code=status.HTTP_201_CREATED)
def create_availability_override(
    payload: AvailabilityOverrideCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    """Belirli bir tarihe ozel gecici degisiklik - bkz. gorev ozeti:
    "arada bir günü değiştirebilsin, değişiklik sadece o güne ait olsun,
    diğer zamanlara uygulamak ister misin diye sorsun, onaylarsa o plan
    o gün için artık sabit olsun". Haftalik sablon (AvailabilityRule)
    SADECE `apply_to_weekly_template=True` ise (kullanicinin "evet, kalici
    yap" onayindan sonra) AYRICA guncellenir - bu satirin kendisi HER
    ZAMAN sadece bu tarihe ozel kalir."""
    require_permission(auth, "can_manage_availability")
    require_own_staff_resource(auth, payload.staff_id)
    _get_staff_or_404(db, payload.staff_id, auth.tenant_id)

    if payload.start_time >= payload.end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time must be before end_time",
        )

    override = AvailabilityOverride(
        tenant_id=auth.tenant_id,
        staff_id=payload.staff_id,
        date=payload.date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        mode=payload.mode,
        slot_duration_minutes=payload.slot_duration_minutes,
        gap_minutes=payload.gap_minutes,
    )
    db.add(override)

    if payload.apply_to_weekly_template:
        # "Bunu kalici yap" - o haftanin gunu icin mevcut TUM kurallari bu
        # tek pencereyle DEGISTIRIR (bkz. gorev ozeti - "o plan o gün için
        # artık sabit olsun"). Override satirinin kendisi bundan ETKILENMEZ.
        weekday = payload.date.weekday()
        db.query(AvailabilityRule).filter(
            AvailabilityRule.tenant_id == auth.tenant_id,
            AvailabilityRule.staff_id == payload.staff_id,
            AvailabilityRule.weekday == weekday,
        ).delete()
        db.add(
            AvailabilityRule(
                tenant_id=auth.tenant_id,
                staff_id=payload.staff_id,
                weekday=weekday,
                start_time=payload.start_time,
                end_time=payload.end_time,
                mode=payload.mode,
                slot_duration_minutes=payload.slot_duration_minutes,
                gap_minutes=payload.gap_minutes,
            )
        )

    db.commit()
    db.refresh(override)
    return override


@router.get("", response_model=list[AvailabilityOverrideOut])
def list_availability_overrides(
    staff_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    query = db.query(AvailabilityOverride).filter(
        AvailabilityOverride.tenant_id == auth.tenant_id
    )
    if auth.role == "staff":
        query = query.filter(AvailabilityOverride.staff_id == auth.staff_member_id)
    elif staff_id is not None:
        query = query.filter(AvailabilityOverride.staff_id == staff_id)
    return query.order_by(AvailabilityOverride.date).all()


@router.post("/{override_id}/remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_availability_override(
    override_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
) -> None:
    """O tarihi haftalik sablona geri dondurur - DELETE yerine POST
    kullaniliyor (bkz. app/main.py CORS allow_methods, projede zaten
    yerlesik desen - orn. staff_members'daki end-membership)."""
    require_permission(auth, "can_manage_availability")
    override = (
        db.query(AvailabilityOverride)
        .filter(
            AvailabilityOverride.id == override_id,
            AvailabilityOverride.tenant_id == auth.tenant_id,
        )
        .first()
    )
    if override is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Override not found")
    require_own_staff_resource(auth, override.staff_id)

    db.delete(override)
    db.commit()
