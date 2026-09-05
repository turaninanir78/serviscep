from pydantic import BaseModel, ConfigDict


class StaffMemberCreate(BaseModel):
    name: str
    is_active: bool = True


class StaffMemberUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class StaffMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    is_active: bool
