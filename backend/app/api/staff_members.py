from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import StaffMember, TenantMembership
from app.permissions import require_owner
from app.schemas.staff_invitation import StaffMembershipOut, StaffPermissionsUpdate
from app.schemas.staff_member import StaffMemberCreate, StaffMemberOut, StaffMemberUpdate
from app.security import AuthContext, get_current_tenant

router = APIRouter(prefix="/staff_members", tags=["staff_members"])


@router.post("", response_model=StaffMemberOut, status_code=status.HTTP_201_CREATED)
def create_staff_member(
    payload: StaffMemberCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_owner(auth)
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
    require_owner(auth)
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


def _linked_membership_or_404(db: Session, staff_id: int, tenant_id: int) -> TenantMembership:
    membership = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.staff_member_id == staff_id,
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.role == "staff",
            TenantMembership.status == "active",
        )
        .first()
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu personel bir kullanıcı hesabına bağlı değil (davetle eklenmemiş).",
        )
    return membership


def _membership_out(membership: TenantMembership) -> StaffMembershipOut:
    return StaffMembershipOut(
        staff_member_id=membership.staff_member_id,
        role=membership.role,
        can_view_customers=membership.can_view_customers,
        can_create_appointments=membership.can_create_appointments,
        can_cancel_appointments=membership.can_cancel_appointments,
        can_confirm_complete_appointments=membership.can_confirm_complete_appointments,
        can_manage_availability=membership.can_manage_availability,
        can_manage_services=membership.can_manage_services,
    )


@router.get("/{staff_id}/membership", response_model=StaffMembershipOut)
def get_staff_membership(
    staff_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    """Davetle eklenmis (bir kullanici hesabina bagli) bir personelin
    guncel yetkilerini doner - izin duzenleme ekraninin mevcut durumu
    yuklemesi icin. Yerel (davetsiz) personel icin 404 - onlarda
    duzenlenecek bir yetki YOK, her zaman sadece randevu kaynagi."""
    require_owner(auth)
    membership = _linked_membership_or_404(db, staff_id, auth.tenant_id)
    return _membership_out(membership)


@router.patch("/{staff_id}/permissions", response_model=StaffMembershipOut)
def update_staff_permissions(
    staff_id: int,
    payload: StaffPermissionsUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    require_owner(auth)
    membership = _linked_membership_or_404(db, staff_id, auth.tenant_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(membership, field, value)

    db.commit()
    db.refresh(membership)
    return _membership_out(membership)


@router.post("/{staff_id}/end-membership", response_model=StaffMemberOut)
def end_staff_membership(
    staff_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    """Davetle baglanmis bir personelin isletmeyle iliskisini sonlandirir
    - bkz. gorev ozeti: "isletmeden cikarsa butun bilgiler isletme
    hesabinda kalacak" - randevu/musteri gecmisi (staff_id hala gecerli)
    HIC DOKUNULMAZ, sadece SU ANDAN itibaren yeni randevu alamamasi icin
    StaffMember.is_active=False yapilir ve uyelik status="left" ile
    kapatilir. Kisinin KENDI hesabi/tenant'i etkilenmez - bir sonraki
    isteginde (bkz. app/security.py::_resolve_auth_context) otomatik
    olarak kendi owner baglamina doner, ayrica bir islem gerekmez."""
    require_owner(auth)
    membership = _linked_membership_or_404(db, staff_id, auth.tenant_id)

    membership.status = "left"
    membership.left_at = datetime.now(timezone.utc)

    staff = db.query(StaffMember).filter(StaffMember.id == staff_id).first()
    staff.is_active = False

    db.commit()
    db.refresh(staff)
    return staff
