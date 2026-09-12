from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crypto import encrypt_token
from app.db import get_db
from app.models import Tenant
from app.permissions import require_owner
from app.schemas.tenant import (
    TenantBookingSettingsUpdate,
    TenantOut,
    TenantWhatsAppConnect,
    TenantWhatsAppConnectResponse,
)
from app.security import AuthContext, get_current_tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _tenant_out(tenant: Tenant, auth: AuthContext) -> TenantOut:
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        timezone=tenant.timezone,
        my_role=auth.role,
        my_permissions=sorted(auth.permissions),
        my_staff_member_id=auth.staff_member_id,
        max_advance_booking_days=tenant.max_advance_booking_days,
    )


@router.get("/me", response_model=TenantOut)
def get_my_tenant(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return _tenant_out(tenant, auth)


@router.patch("/me/booking-settings", response_model=TenantOut)
def update_booking_settings(
    payload: TenantBookingSettingsUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    """Randevu acik kalma suresini gunceller - bkz. gorev ozeti: "bu sure
    her zaman degistirebilir olacak". Owner'a ozel (isletme genelinde bir
    politika, personelin degistirebilecegi bir sey degil)."""
    require_owner(auth)
    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if payload.max_advance_booking_days is not None and payload.max_advance_booking_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="max_advance_booking_days pozitif olmalı (sınırsız için null gönderin).",
        )

    tenant.max_advance_booking_days = payload.max_advance_booking_days
    db.commit()
    db.refresh(tenant)
    return _tenant_out(tenant, auth)


@router.patch("/me/whatsapp", response_model=TenantWhatsAppConnectResponse)
def connect_whatsapp(
    payload: TenantWhatsAppConnect,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    tenant.whatsapp_phone_number_id = payload.phone_number_id
    tenant.whatsapp_waba_id = payload.business_account_id
    tenant.whatsapp_access_token_encrypted = encrypt_token(payload.access_token)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="phone_number_id is already connected to another tenant",
        )

    return TenantWhatsAppConnectResponse(phone_number_id=tenant.whatsapp_phone_number_id)
