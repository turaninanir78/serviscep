"""Randevu motoru: müsaitlik hesabı ve çakışma kontrolü.

Bu modül bilinçli olarak framework'ten (FastAPI) ve veritabanından
bağımsızdır - sadece tarih/saat üzerinde çalışan saf fonksiyonlar içerir,
böylece API'den, panelden veya ileride WhatsApp/AI'dan aynı şekilde
çağrılabilir ve DB'ye dokunmadan test edilebilir (docs/architecture.md
Bölüm 8, 13).
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class WorkingWindow:
    start_time: time
    end_time: time


@dataclass(frozen=True)
class BookedInterval:
    start_at: datetime
    end_at: datetime


def has_conflict(
    start_at: datetime,
    end_at: datetime,
    other_start_at: datetime,
    other_end_at: datetime,
) -> bool:
    """İki zaman aralığı çakışıyor mu? Sınırda dokunma (10:00-11:00 ile
    11:00-12:00) çakışma sayılmaz."""
    return start_at < other_end_at and other_start_at < end_at


def compute_available_slots(
    target_date: date,
    working_windows: list[WorkingWindow],
    booked_intervals: list[BookedInterval],
    duration_minutes: int,
    timezone: str,
) -> list[datetime]:
    """Verilen gün için, çalışma saatleri içinde ve mevcut randevularla
    çakışmayan, `duration_minutes` uzunluğunda boş slotları döner.

    Slotlar her çalışma penceresinin başlangıcından itibaren
    `duration_minutes` aralıklarla hesaplanır (docs/architecture.md
    Bölüm 8'deki örnekle aynı mantık: 09:00-18:00, 60 dk -> 09:00, 10:00, ...).
    """
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")

    tz = ZoneInfo(timezone)
    duration = timedelta(minutes=duration_minutes)
    slots: list[datetime] = []

    for window in working_windows:
        current = datetime.combine(target_date, window.start_time, tzinfo=tz)
        window_end = datetime.combine(target_date, window.end_time, tzinfo=tz)

        while current + duration <= window_end:
            candidate_end = current + duration
            if not any(
                has_conflict(current, candidate_end, b.start_at, b.end_at)
                for b in booked_intervals
            ):
                slots.append(current)
            current += duration

    return slots
