"""Randevu motoru: müsaitlik hesabı ve çakışma kontrolü.

Bu modül bilinçli olarak framework'ten (FastAPI) ve veritabanından
bağımsızdır - sadece tarih/saat üzerinde çalışan saf fonksiyonlar içerir,
böylece API'den, panelden veya ileride WhatsApp/AI'dan aynı şekilde
çağrılabilir ve DB'ye dokunmadan test edilebilir (docs/architecture.md
Bölüm 8, 13).

Buffer (randevular arası boşluk/temizlik süresi) mantığı, veritabanındaki
`excl_appointments_staff_time_overlap` EXCLUDE constraint'iyle (migration
0003) BİREBİR aynı olacak şekilde tasarlanmıştır: her randevu kendi
`buffer_minutes` değeri kadar, bitişinden sonra da "işgal ediyor" sayılır
- yani karşılaştırılan her iki tarafın da KENDİ buffer'ı kendi etkin
bitişini uzatır. Bu iki mantığın (Python burada, SQL orada) birbirinden
sapması, kullanıcının "boş" gördüğü bir slotta beklenmedik bir 409/500
almasına yol açar; bkz. tests/test_buffer_minutes.py.
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
    buffer_minutes: int = 0


def has_conflict(
    start_at: datetime,
    end_at: datetime,
    other_start_at: datetime,
    other_end_at: datetime,
    buffer_minutes: int = 0,
    other_buffer_minutes: int = 0,
) -> bool:
    """İki randevu araligi, kendi buffer'larıyla genişletilmiş etkin
    bitişleri de hesaba katılarak çakışıyor mu?

    Her aralığın etkin bitişi `end_at + buffer_minutes`'tir - yani bir
    randevunun bitişinden sonraki buffer süresi de o randevu tarafından
    "işgal edilmiş" sayılır (temizlik/hazırlık süresi). Sınırda dokunma
    (birinin etkin bitişi tam diğerinin başlangıcına denk gelmesi)
    çakışma sayılmaz - veritabanındaki `[)` (half-open) aralık semantiği
    ile birebir tutarlı.
    """
    effective_end = end_at + timedelta(minutes=buffer_minutes)
    other_effective_end = other_end_at + timedelta(minutes=other_buffer_minutes)
    return start_at < other_effective_end and other_start_at < effective_end


def compute_available_slots(
    target_date: date,
    working_windows: list[WorkingWindow],
    booked_intervals: list[BookedInterval],
    duration_minutes: int,
    timezone: str,
    buffer_minutes: int = 0,
) -> list[datetime]:
    """Verilen gün için, çalışma saatleri içinde ve mevcut randevularla
    (kendi buffer'ları dahil) çakışmayan, `duration_minutes` uzunluğunda
    boş slotları döner.

    Slotlar her çalışma penceresinin başlangıcından itibaren
    `duration_minutes + buffer_minutes` aralıklarla dizilir (docs/
    architecture.md Bölüm 8'deki örnekle aynı mantığın buffer'lı hali:
    60 dk hizmet + 10 dk buffer -> 09:00, 10:10, 11:20, ...). Adayın
    kendisi (`duration_minutes`) çalışma penceresine sığmalı; adayın
    KENDİ buffer'ının pencere içinde sığması ZORUNLU DEĞİL - buffer,
    randevunun kendisi bitince baslayan bir "meşguliyet" süresi olup
    çalışma saatinin dışına taşabilir (ör. kapanıştan hemen önceki
    randevunun temizlik süresi mesai sonrasına sarkabilir).
    """
    if duration_minutes <= 0:
        raise ValueError("duration_minutes must be positive")

    tz = ZoneInfo(timezone)
    duration = timedelta(minutes=duration_minutes)
    step = duration + timedelta(minutes=buffer_minutes)
    slots: list[datetime] = []

    for window in working_windows:
        current = datetime.combine(target_date, window.start_time, tzinfo=tz)
        window_end = datetime.combine(target_date, window.end_time, tzinfo=tz)

        while current + duration <= window_end:
            candidate_end = current + duration
            if not any(
                has_conflict(
                    current,
                    candidate_end,
                    b.start_at,
                    b.end_at,
                    buffer_minutes=buffer_minutes,
                    other_buffer_minutes=b.buffer_minutes,
                )
                for b in booked_intervals
            ):
                slots.append(current)
            current += step

    return slots
