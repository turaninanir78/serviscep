from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CustomerCreate(BaseModel):
    whatsapp_number: str
    display_name: str | None = None


class CustomerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    whatsapp_number: str
    display_name: str | None
    first_seen_at: datetime
