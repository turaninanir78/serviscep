from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crypto import encrypt_token
from app.db import get_db
from app.models import Tenant
from app.schemas.tenant import TenantOut, TenantWhatsAppConnect, TenantWhatsAppConnectResponse
from app.security import AuthContext, get_current_tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=TenantOut)
def get_my_tenant(
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    tenant = db.query(Tenant).filter(Tenant.id == auth.tenant_id).first()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return TenantOut(
        id=tenant.id,
        name=tenant.name,
        timezone=tenant.timezone,
        my_role=auth.role,
        my_permissions=sorted(auth.permissions),
    )


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
