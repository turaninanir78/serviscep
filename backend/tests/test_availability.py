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


def test_compute_available_slots_spaces_slots_by_duration_plus_buffer():
    # 60 dk hizmet + 10 dk buffer -> slotlar 70 dk araliklarla dizilmeli.
    # 09:00-18:00 (540 dk) penceresinde: 09:00, 10:10, 11:20, 12:30, 13:40,
    # 14:50, 16:00 (7 slot) - bir sonraki aday 17:10 olurdu ama 17:10+60=18:10
    # pencereyi asiyor, o yuzden gecersiz.
    windows = [WorkingWindow(start_time=time(9, 0), end_time=time(18, 0))]

    slots = compute_available_slots(
        target_date=TARGET_DATE,
        working_windows=windows,
        booked_intervals=[],
        duration_minutes=60,
        buffer_minutes=10,
        timezone=TZ,
    )

    expected = [
        _dt(9, 0),
        _dt(10, 10),
        _dt(11, 20),
        _dt(12, 30),
        _dt(13, 40),
        _dt(14, 50),
        _dt(16, 0),
    ]
    assert slots == expected


def test_existing_booking_buffer_minutes_affects_slot_computation_and_conflict_check():
    # Onceki randevu 09:00-09:30, KENDI buffer'i 15 dk (varsayilan degil,
    # randevuya ozel/override bir deger oldugunu varsayalim). Bu randevunun
    # "isgal ettigi" alan efektif olarak 09:00-09:45'e kadar uzaniyor.
    booked_with_buffer = [BookedInterval(start_at=_dt(9), end_at=_dt(9, 30), buffer_minutes=15)]
    # Ayni randevu, buffer_minutes=0 override'iyla olusturulmus olsaydi.
    booked_no_buffer = [BookedInterval(start_at=_dt(9), end_at=_dt(9, 30), buffer_minutes=0)]

    # Cakisma kontrolu: 09:30'da baslayan yeni bir aday (kendi buffer'i 0),
    # onceki randevunun buffer'ina gore farkli sonuc vermeli.
    assert (
        has_conflict(_dt(9, 30), _dt(10, 0), _dt(9), _dt(9, 30), buffer_minutes=0, other_buffer_minutes=15)
        is True
    )
    assert (
        has_conflict(_dt(9, 30), _dt(10, 0), _dt(9), _dt(9, 30), buffer_minutes=0, other_buffer_minutes=0)
        is False
    )

    # Slot hesabi: 30 dk'lik hizmet, ADAYIN kendi buffer'i 0 (sabit 30 dk'lik
    # izgara: 09:00, 09:30, 10:00, ...). Onceki randevunun KENDI buffer'i
    # farkli oldugunda 09:30 slotu musait/musait-degil arasinda degismeli.
    windows = [WorkingWindow(start_time=time(9, 0), end_time=time(12, 0))]

    slots_with_buffer = compute_available_slots(
        target_date=TARGET_DATE,
        working_windows=windows,
        booked_intervals=booked_with_buffer,
        duration_minutes=30,
        buffer_minutes=0,
        timezone=TZ,
    )
    slots_no_buffer = compute_available_slots(
        target_date=TARGET_DATE,
        working_windows=windows,
        booked_intervals=booked_no_buffer,
        duration_minutes=30,
        buffer_minutes=0,
        timezone=TZ,
    )

    assert _dt(9, 30) not in slots_with_buffer  # onceki randevunun buffer'i 09:45'e kadar isgal ediyor
    assert _dt(9, 30) in slots_no_buffer  # buffer=0 oldugunda 09:30 hemen musait
