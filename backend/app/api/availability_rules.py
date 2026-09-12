from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AvailabilityRule, StaffMember
from app.permissions import require_own_staff_resource, require_permission
from app.schemas.availability_rule import (
    AvailabilityRuleCreate,
    AvailabilityRuleOut,
    AvailabilityRuleUpdate,
)
from app.security import AuthContext, get_current_tenant

router = APIRouter(prefix="/availability_rules", tags=["availability_rules"])


def _get_staff_or_404(db: Session, staff_id: int, tenant_id: int) -> StaffMember:
    staff = (
        db.query(StaffMember)
        .filter(StaffMember.id == staff_id, StaffMember.tenant_id == tenant_id)
        .first()
    )
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
    return staff


@router.post("", response_model=AvailabilityRuleOut, status_code=status.HTTP_201_CREATED)
def create_availability_rule(
    payload: AvailabilityRuleCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_permission(auth, "can_manage_availability")
    require_own_staff_resource(auth, payload.staff_id)
    _get_staff_or_404(db, payload.staff_id, auth.tenant_id)

    if payload.start_time >= payload.end_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time must be before end_time",
        )

    rule = AvailabilityRule(tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("", response_model=list[AvailabilityRuleOut])
def list_availability_rules(
    db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_tenant)
):
    query = db.query(AvailabilityRule).filter(AvailabilityRule.tenant_id == auth.tenant_id)
    if auth.role == "staff":
        query = query.filter(AvailabilityRule.staff_id == auth.staff_member_id)
    return query.all()


@router.patch("/{rule_id}", response_model=AvailabilityRuleOut)
def update_availability_rule(
    rule_id: int,
    payload: AvailabilityRuleUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_permission(auth, "can_manage_availability")
    rule = (
        db.query(AvailabilityRule)
        .filter(AvailabilityRule.id == rule_id, AvailabilityRule.tenant_id == auth.tenant_id)
        .first()
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Availability rule not found"
        )
    require_own_staff_resource(auth, rule.staff_id)

    updates = payload.model_dump(exclude_unset=True)
    new_start = updates.get("start_time", rule.start_time)
    new_end = updates.get("end_time", rule.end_time)
    if new_start >= new_end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_time must be before end_time",
        )

    for field, value in updates.items():
        setattr(rule, field, value)

    db.commit()
    db.refresh(rule)
    return rule
