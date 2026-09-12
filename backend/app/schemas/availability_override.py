from datetime import date as date_type, time

from pydantic import BaseModel, ConfigDict, model_validator

from app.schemas.availability_rule import ScheduleMode, validate_standard_mode_fields


class AvailabilityOverrideCreate(BaseModel):
    staff_id: int
    date: date_type
    start_time: time
    end_time: time
    mode: ScheduleMode = "flexible"
    slot_duration_minutes: int | None = None
    gap_minutes: int = 0
    # True ise, bu istisna AYNI degerlerle haftalik sablona da (yeni bir
    # AvailabilityRule olarak) yazilir - bkz. gorev ozeti: "diğer zamanlara
    # uygulamak ister misin diye sorsun, onaylarsa o plan o gün için artık
    # sabit olsun". Bu satirin kendisi HER ZAMAN sadece bu tarihe ozel kalir.
    apply_to_weekly_template: bool = False

    @model_validator(mode="after")
    def validate_standard_mode(self) -> "AvailabilityOverrideCreate":
        validate_standard_mode_fields(self.mode, self.slot_duration_minutes)
        return self


class AvailabilityOverrideOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    staff_id: int
    date: date_type
    start_time: time
    end_time: time
    mode: str
    slot_duration_minutes: int | None
    gap_minutes: int
