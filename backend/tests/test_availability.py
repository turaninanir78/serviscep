from datetime import date, datetime, time

import pytest
from zoneinfo import ZoneInfo

from app.core.availability import (
    BookedInterval,
    WorkingWindow,
    compute_available_slots,
    has_conflict,
)

TZ = "Europe/Istanbul"
TARGET_DATE = date(2026, 9, 7)  # bir Pazartesi


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(TARGET_DATE, time(hour, minute), tzinfo=ZoneInfo(TZ))


def test_full_day_available_when_no_bookings():
    windows = [WorkingWindow(start_time=time(9, 0), end_time=time(18, 0))]

    slots = compute_available_slots(
        target_date=TARGET_DATE,
        working_windows=windows,
        booked_intervals=[],
        duration_minutes=60,
        timezone=TZ,
    )

    assert slots == [_dt(h) for h in range(9, 18)]


def test_fully_booked_day_has_no_slots():
    windows = [WorkingWindow(start_time=time(9, 0), end_time=time(18, 0))]
    booked = [BookedInterval(start_at=_dt(9), end_at=_dt(18))]

    slots = compute_available_slots(
        target_date=TARGET_DATE,
        working_windows=windows,
        booked_intervals=booked,
        duration_minutes=60,
        timezone=TZ,
    )

    assert slots == []


def test_partially_booked_day_excludes_only_overlapping_slots():
    windows = [WorkingWindow(start_time=time(9, 0), end_time=time(18, 0))]
    booked = [BookedInterval(start_at=_dt(10), end_at=_dt(11))]

    slots = compute_available_slots(
        target_date=TARGET_DATE,
        working_windows=windows,
        booked_intervals=booked,
        duration_minutes=60,
        timezone=TZ,
    )

    assert _dt(10) not in slots
    assert _dt(9) in slots
    assert _dt(11) in slots
    assert len(slots) == 8


def test_conflicting_appointment_is_rejected():
    assert has_conflict(_dt(10), _dt(11), _dt(10, 30), _dt(11, 30)) is True
    assert has_conflict(_dt(10), _dt(11), _dt(9), _dt(10, 30)) is True
    assert has_conflict(_dt(9), _dt(18), _dt(10), _dt(11)) is True


def test_non_conflicting_appointment_is_accepted():
    assert has_conflict(_dt(10), _dt(11), _dt(11), _dt(12)) is False
    assert has_conflict(_dt(10), _dt(11), _dt(8), _dt(9)) is False


def test_compute_available_slots_rejects_non_positive_duration():
    with pytest.raises(ValueError):
        compute_available_slots(
            target_date=TARGET_DATE,
            working_windows=[WorkingWindow(start_time=time(9, 0), end_time=time(18, 0))],
            booked_intervals=[],
            duration_minutes=0,
            timezone=TZ,
        )
