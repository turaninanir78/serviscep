from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AppointmentCreate(BaseModel):
    staff_id: int
    service_id: int
    customer_id: int
    start_at: datetime
    # Gonderilmezse, hizmetin default_buffer_minutes degeri kullanilir.
    buffer_minutes: int | None = Field(default=None, ge=0)


class AppointmentReschedule(BaseModel):
    # Hepsi opsiyonel (partial update). Sadece bunlar guncellenebilir -
    # customer_id veya status bu endpoint'ten degistirilemez.
    start_at: datetime | None = None
    service_id: int | None = None
    staff_id: int | None = None
    buffer_minutes: int | None = Field(default=None, ge=0)


class AppointmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    customer_id: int
    service_id: int
    staff_id: int
    start_at: datetime
    end_at: datetime
    status: str
    created_via: str
    buffer_minutes: int


class AvailableSlotsResponse(BaseModel):
    date: date
    staff_id: int
    service_id: int
    slots: list[datetime]
