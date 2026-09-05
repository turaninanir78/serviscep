"""Randevu durum makinesi - framework'ten bağımsız.

`appointments.status` degerleri (bkz. migration 0001,
`ck_appointments_status`): pending, confirmed, cancelled, completed,
no_show. Hangi durumdan hangi hedef duruma gecilebilecegi TEK bu
dosyada tanimlanir - reschedule/cancel/complete/no-show endpoint'lerine
dagilmis, birbirinden bagimsiz kontrol mantigi olmasin diye.
"""

ACTIVE_STATUSES = frozenset({"pending", "confirmed"})
TERMINAL_STATUSES = frozenset({"cancelled", "completed", "no_show"})
ALL_STATUSES = ACTIVE_STATUSES | TERMINAL_STATUSES

# Hangi durumdan hangi (terminal) hedef durumlara gecilebilir. Terminal
# durumlardan baska bir yere gecis yok - randevu "kapanmis" sayilir.
ALLOWED_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": TERMINAL_STATUSES,
    "confirmed": TERMINAL_STATUSES,
    "cancelled": frozenset(),
    "completed": frozenset(),
    "no_show": frozenset(),
}


def can_transition_to(current_status: str, target_status: str) -> bool:
    """`current_status`'tan `target_status`'a (cancel/complete/no_show gibi
    bir durum degisikligine) gecilebilir mi?"""
    if target_status not in ALL_STATUSES:
        raise ValueError(f"unknown status: {target_status!r}")
    return target_status in ALLOWED_STATUS_TRANSITIONS.get(current_status, frozenset())


def can_reschedule(current_status: str) -> bool:
    """Reschedule (start_at/service/staff/buffer degisikligi) durumu
    degistirmez, ama sadece henuz sonuclanmamis (pending/confirmed)
    randevularda anlamlidir."""
    return current_status in ACTIVE_STATUSES
