import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import StaffInvitation, StaffMember, Tenant, TenantMembership, User
from app.notifications import send_sms
from app.permissions import require_owner
from app.phone import normalize_phone
from app.rate_limit import OTP_REQUEST_RATE_LIMIT, limiter
from app.schemas.staff_invitation import (
    PendingStaffInvitationOut,
    StaffInvitationCreate,
    StaffInvitationOut,
    StaffMembershipOut,
)
from app.security import AuthContext, get_current_tenant, hash_password

router = APIRouter(prefix="/staff_invitations", tags=["staff_invitations"])

# Davet, kabul akisinda bir token GEREKTIRMIYOR (bkz. app/models.py::
# StaffInvitation docstring'i - kabul, davet edilenin ZATEN dogrulanmis
# kendi hesabiyla giris yapip bakmasiyla olur) - bu sure sadece "bu
# davet artik anlamsiz, temizlenebilir" sinirini belirler.
INVITATION_EXPIRE_DAYS = 7

DEFAULT_INVITED_STAFF_NAME = "Yeni Personel"


def _tenant_or_404(db: Session, tenant_id: int) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


@router.post("", response_model=StaffInvitationOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(OTP_REQUEST_RATE_LIMIT)
def create_staff_invitation(
    request: Request,
    payload: StaffInvitationCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
) -> StaffInvitation:
    require_owner(auth)
    phone = normalize_phone(payload.country_code, payload.phone_number)

    invited_user = db.query(User).filter(User.phone == phone).first()
    if invited_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bu telefon numarasıyla kayıtlı bir kullanıcı yok.",
        )
    if invited_user.id == auth.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Kendinizi davet edemezsiniz."
        )

    already_member = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.user_id == invited_user.id,
            TenantMembership.tenant_id == auth.tenant_id,
            TenantMembership.status == "active",
        )
        .first()
    )
    if already_member is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu kullanıcı zaten işletmenizin üyesi."
        )

    invitation = StaffInvitation(
        tenant_id=auth.tenant_id,
        invited_by_user_id=auth.user_id,
        phone=phone,
        token_hash=hash_password(secrets.token_urlsafe(32)),
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITATION_EXPIRE_DAYS),
    )
    db.add(invitation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu numaraya zaten bekleyen bir davet gönderilmiş.",
        )
    db.refresh(invitation)

    tenant = _tenant_or_404(db, auth.tenant_id)
    send_sms(
        phone,
        f"{tenant.name} sizi personel olarak davet etti. Uygulamaya girip daveti kabul edebilirsiniz.",
    )
    return invitation


@router.get("", response_model=list[StaffInvitationOut])
def list_staff_invitations(
    db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_tenant)
) -> list[StaffInvitation]:
    require_owner(auth)
    return (
        db.query(StaffInvitation)
        .filter(StaffInvitation.tenant_id == auth.tenant_id)
        .order_by(StaffInvitation.created_at.desc())
        .all()
    )


@router.post("/{invitation_id}/revoke", response_model=StaffInvitationOut)
def revoke_staff_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
) -> StaffInvitation:
    require_owner(auth)
    invitation = (
        db.query(StaffInvitation)
        .filter(StaffInvitation.id == invitation_id, StaffInvitation.tenant_id == auth.tenant_id)
        .first()
    )
    if invitation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    if invitation.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu davet artık beklemede değil."
        )

    invitation.status = "revoked"
    db.commit()
    db.refresh(invitation)
    return invitation


# --- Davet edilenin gordugu/tepki verdigi uc ---
#
# `auth.tenant_id` burada KULLANILMIYOR - bu asagidaki uc endpoint,
# kullanicinin KENDI telefonuna gelen davetlerle (hangi tenant'ta
# calisiyor olursa olsun) ilgili.


def _current_user_or_404(db: Session, auth: AuthContext) -> User:
    user = db.query(User).filter(User.id == auth.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/pending", response_model=list[PendingStaffInvitationOut])
def list_pending_invitations_for_me(
    db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_tenant)
) -> list[PendingStaffInvitationOut]:
    user = _current_user_or_404(db, auth)
    if user.phone is None:
        return []

    rows = (
        db.query(StaffInvitation, Tenant.name)
        .join(Tenant, Tenant.id == StaffInvitation.tenant_id)
        .filter(
            StaffInvitation.phone == user.phone,
            StaffInvitation.status == "pending",
            StaffInvitation.expires_at > datetime.now(timezone.utc),
        )
        .order_by(StaffInvitation.created_at.desc())
        .all()
    )
    return [
        PendingStaffInvitationOut(
            id=invitation.id,
            tenant_id=invitation.tenant_id,
            tenant_name=tenant_name,
            status=invitation.status,
            created_at=invitation.created_at,
            expires_at=invitation.expires_at,
        )
        for invitation, tenant_name in rows
    ]


def _pending_invitation_for_me_or_404(
    db: Session, auth: AuthContext, invitation_id: int, user: User
) -> StaffInvitation:
    invitation = (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.id == invitation_id,
            StaffInvitation.status == "pending",
            StaffInvitation.expires_at > datetime.now(timezone.utc),
        )
        .first()
    )
    # Baskasinin davetini kabul/red edemez - var olmayanla AYNI 404
    # (davetin var olup olmadigini sizdirmemek icin).
    if invitation is None or user.phone is None or invitation.phone != user.phone:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found")
    return invitation


@router.post("/{invitation_id}/accept", response_model=StaffMembershipOut)
def accept_staff_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
) -> StaffMembershipOut:
    user = _current_user_or_404(db, auth)
    invitation = _pending_invitation_for_me_or_404(db, auth, invitation_id, user)

    already_staff_elsewhere = (
        db.query(TenantMembership)
        .filter(
            TenantMembership.user_id == user.id,
            TenantMembership.role == "staff",
            TenantMembership.status == "active",
        )
        .first()
    )
    if already_staff_elsewhere is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Zaten başka bir işletmede personelsiniz - önce oradan ayrılmalısınız.",
        )

    staff = StaffMember(tenant_id=invitation.tenant_id, name=DEFAULT_INVITED_STAFF_NAME)
    db.add(staff)
    db.flush()  # membership icin staff.id gerekiyor

    membership = TenantMembership(
        user_id=user.id,
        tenant_id=invitation.tenant_id,
        role="staff",
        staff_member_id=staff.id,
        status="active",
    )
    db.add(membership)
    invitation.status = "accepted"
    invitation.accepted_at = datetime.now(timezone.utc)

    try:
        db.commit()
    except IntegrityError:
        # Es zamanli baska bir kabul (bkz. app/api/webhooks.py::
        # _store_inbound_message'daki ayni desen) - "en fazla bir aktif
        # staff uyeligi" kisitina carpmis olabilir.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Zaten başka bir işletmede personelsiniz - önce oradan ayrılmalısınız.",
        )
    db.refresh(membership)

    return StaffMembershipOut(
        staff_member_id=staff.id,
        role="staff",
        can_view_customers=membership.can_view_customers,
        can_create_appointments=membership.can_create_appointments,
        can_cancel_appointments=membership.can_cancel_appointments,
        can_confirm_complete_appointments=membership.can_confirm_complete_appointments,
        can_manage_availability=membership.can_manage_availability,
        can_manage_services=membership.can_manage_services,
    )


@router.post("/{invitation_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline_staff_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
) -> None:
    user = _current_user_or_404(db, auth)
    invitation = _pending_invitation_for_me_or_404(db, auth, invitation_id, user)
    invitation.status = "revoked"
    db.commit()
