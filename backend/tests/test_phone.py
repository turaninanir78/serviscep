"""app/phone.py::normalize_phone testleri - saf fonksiyon, HTTP/DB
gerektirmez (diger saf-fonksiyon test dosyalarindaki - orn.
test_security_config.py - yaklasimla ayni)."""
import pytest
from fastapi import HTTPException

from app.phone import normalize_phone


def test_leading_zero_is_stripped():
    assert normalize_phone("+90", "05321234567") == "+905321234567"


def test_without_leading_zero_gives_same_result():
    assert normalize_phone("+90", "5321234567") == "+905321234567"


def test_same_number_with_and_without_leading_zero_normalize_identically():
    # Login/OTP hedef eslesmesinin dogru calismasi icin kritik: kullanici
    # "0532..." de yazsa "532..." da yazsa AYNI kullaniciyi bulmaliyiz.
    assert normalize_phone("+90", "0532 111 22 33") == normalize_phone("+90", "5321112233")


def test_non_digit_characters_are_removed():
    assert normalize_phone("+90", "(0532) 123-45-67") == "+905321234567"


def test_country_code_without_plus_prefix_is_normalized():
    assert normalize_phone("90", "5321234567") == "+905321234567"


def test_unsupported_country_code_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        normalize_phone("+1", "5551234567")
    assert exc_info.value.status_code == 422


def test_too_short_number_is_rejected():
    with pytest.raises(HTTPException) as exc_info:
        normalize_phone("+90", "123")
    assert exc_info.value.status_code == 422
