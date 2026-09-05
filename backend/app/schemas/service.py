from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ServiceCreate(BaseModel):
    name: str
    duration_minutes: int
    price: Decimal | None = None
    is_active: bool = True
    default_buffer_minutes: int = Field(default=0, ge=0)


class ServiceUpdate(BaseModel):
    name: str | None = None
    duration_minutes: int | None = None
    price: Decimal | None = None
    is_active: bool | None = None
    default_buffer_minutes: int | None = Field(default=None, ge=0)


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: str
    duration_minutes: int
    price: Decimal | None
    is_active: bool
    default_buffer_minutes: int
