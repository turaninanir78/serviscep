from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ServiceCreate(BaseModel):
    name: str
    duration_minutes: int
    price: Decimal | None = None
    is_active: bool = True


class ServiceUpdate(BaseModel):
    name: str | None = None
    duration_minutes: int | None = None
    price: Decimal | None = None
    is_active: bool | None = None


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    duration_minutes: int
    price: Decimal | None
    is_active: bool
