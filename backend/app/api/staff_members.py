from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import StaffMember
from app.schemas.staff_member import StaffMemberCreate, StaffMemberOut, StaffMemberUpdate
from app.security import AuthContext, get_current_tenant

router = APIRouter(prefix="/staff_members", tags=["staff_members"])


@router.post("", response_model=StaffMemberOut, status_code=status.HTTP_201_CREATED)
def create_staff_member(
    payload: StaffMemberCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    staff = StaffMember(tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(staff)
    db.commit()
    db.refresh(staff)
    return staff


@router.get("", response_model=list[StaffMemberOut])
def list_staff_members(
    db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_tenant)
):
    return db.query(StaffMember).filter(StaffMember.tenant_id == auth.tenant_id).all()


@router.get("/{staff_id}", response_model=StaffMemberOut)
def get_staff_member(
    staff_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    staff = (
        db.query(StaffMember)
        .filter(StaffMember.id == staff_id, StaffMember.tenant_id == auth.tenant_id)
        .first()
    )
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")
    return staff


@router.patch("/{staff_id}", response_model=StaffMemberOut)
def update_staff_member(
    staff_id: int,
    payload: StaffMemberUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    staff = (
        db.query(StaffMember)
        .filter(StaffMember.id == staff_id, StaffMember.tenant_id == auth.tenant_id)
        .first()
    )
    if staff is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(staff, field, value)

    db.commit()
    db.refresh(staff)
    return staff
