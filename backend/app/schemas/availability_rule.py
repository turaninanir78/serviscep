from datetime import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# "standard" modda slot suresi secilen hizmetten degil, bu sabit degerden
# gelir - bkz. app/models.py::AvailabilityRule docstring'i.
ScheduleMode = Literal["flexible", "standard"]


def validate_standard_mode_fields(mode: str, slot_duration_minutes: int | None) -> None:
    """AvailabilityOverrideCreate ile PAYLASILAN dogrulama (bkz.
    app/schemas/availability_override.py) - iki semanin ayni kurali
    birbirinden sapmadan uygulamasi icin tek yerde tanimli."""
    if mode == "standard" and (slot_duration_minutes is None or slot_duration_minutes <= 0):
        raise ValueError("standard modda slot_duration_minutes zorunlu ve pozitif olmalı")


class AvailabilityRuleCreate(BaseModel):
    staff_id: int
    # 0=Pazartesi ... 6=Pazar (Python date.weekday() ile aynı kodlama)
    weekday: int
    start_time: time
    end_time: time
    mode: ScheduleMode = "flexible"
    # SADECE mode="standard" icin: sabit slot suresi + slotlar arasi bosluk.
    slot_duration_minutes: int | None = None
    gap_minutes: int = 0

    @field_validator("weekday")
    @classmethod
    def validate_weekday(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("weekday must be between 0 and 6")
        return v

    @model_validator(mode="after")
    def validate_standard_mode(self) -> "AvailabilityRuleCreate":
        validate_standard_mode_fields(self.mode, self.slot_duration_minutes)
        return self


class AvailabilityRuleUpdate(BaseModel):
    weekday: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    mode: ScheduleMode | None = None
    slot_duration_minutes: int | None = None
    gap_minutes: int | None = None

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
    mode: str
    slot_duration_minutes: int | None
    gap_minutes: int
