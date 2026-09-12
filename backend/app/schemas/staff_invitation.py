from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.auth import PhoneNumberInput


class StaffInvitationCreate(PhoneNumberInput):
    pass


class StaffInvitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    phone: str
    status: str
    created_at: datetime
    expires_at: datetime


class PendingStaffInvitationOut(BaseModel):
    """StaffInvitationOut + davet eden isletmenin adi - davet edilen
    kisinin hangi isletmeden geldigini gorup karar verebilmesi icin
    (StaffInvitation'da bir tenant_name sutunu yok, endpoint bunu
    Tenant'tan join'leyip elle dolduruyor)."""

    id: int
    tenant_id: int
    tenant_name: str
    status: str
    created_at: datetime
    expires_at: datetime


# --- Personel yetkileri (bkz. app/models.py::TenantMembership) ---


class StaffPermissionsUpdate(BaseModel):
    can_view_customers: bool | None = None
    can_create_appointments: bool | None = None
    can_cancel_appointments: bool | None = None
    can_confirm_complete_appointments: bool | None = None
    can_manage_availability: bool | None = None
    can_manage_services: bool | None = None


class StaffMembershipOut(BaseModel):
    staff_member_id: int
    role: str
    can_view_customers: bool
    can_create_appointments: bool
    can_cancel_appointments: bool
    can_confirm_complete_appointments: bool
    can_manage_availability: bool
    can_manage_services: bool
