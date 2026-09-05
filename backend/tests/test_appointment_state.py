import pytest

from app.core.appointment_state import (
    ACTIVE_STATUSES,
    TERMINAL_STATUSES,
    can_reschedule,
    can_transition_to,
)


def test_active_statuses_can_be_rescheduled():
    assert can_reschedule("pending") is True
    assert can_reschedule("confirmed") is True


def test_terminal_statuses_cannot_be_rescheduled():
    for terminal_status in TERMINAL_STATUSES:
        assert can_reschedule(terminal_status) is False


def test_active_statuses_can_transition_to_any_terminal_status():
    for active_status in ACTIVE_STATUSES:
        for terminal_status in TERMINAL_STATUSES:
            assert can_transition_to(active_status, terminal_status) is True


def test_terminal_statuses_cannot_transition_anywhere():
    for terminal_status in TERMINAL_STATUSES:
        for target in ACTIVE_STATUSES | TERMINAL_STATUSES:
            assert can_transition_to(terminal_status, target) is False


def test_can_transition_to_rejects_unknown_target_status():
    with pytest.raises(ValueError):
        can_transition_to("pending", "not_a_real_status")
