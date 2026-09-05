from datetime import time

from pydantic import BaseModel, ConfigDict, field_validator


class AvailabilityRuleCreate(BaseModel):
    staff_id: int
    # 0=Pazartesi ... 6=Pazar (Python date.weekday() ile aynı kodlama)
    weekday: int
    start_time: time
    end_time: time

    @field_validator("weekday")
    @classmethod
    def validate_weekday(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("weekday must be between 0 and 6")
        return v


class AvailabilityRuleUpdate(BaseModel):
    weekday: int | None = None
    start_time: time | None = None
    end_time: time | None = None

    @field_validator("weekday")
    @classmethod
    def validate_weekday(cls, v: int | None) -> int | None:
        if v is not None and not 0 <= v <= 6:
            raise ValueError("weekday must be between 0 and 6")
        return v


class AvailabilityRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    staff_id: int
    weekday: int
    start_time: time
    end_time: time
