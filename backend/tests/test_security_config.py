"""app/security.py::_validate_cookie_security testleri.

Saf, parametreli bir fonksiyon oldugu icin (bilerek modulun kendi
ENVIRONMENT/COOKIE_SECURE global degiskenlerine bagli degil) gercek ortam
degiskenlerini degistirmeye veya modulu yeniden yuklemeye gerek kalmadan
dogrudan cagirip test edebiliyoruz - diger test dosyalarindaki gibi canli
sunucuya HTTP istegi atmiyor (bkz. app/core/availability.py testlerindeki
ayni "framework'ten bagimsiz, saf fonksiyon" yaklasimi).
"""
import pytest

from app.security import _validate_cookie_security


def test_production_with_insecure_cookie_refuses_to_start():
    with pytest.raises(RuntimeError, match="COOKIE_SECURE must be true in production"):
        _validate_cookie_security("production", False)


def test_production_with_secure_cookie_is_allowed():
    _validate_cookie_security("production", True)  # exception firlatmamali


def test_development_with_insecure_cookie_is_allowed():
    # Mevcut dev/docker-compose davranisi - degismemesi gereken varsayilan.
    _validate_cookie_security("development", False)


def test_development_with_secure_cookie_is_allowed():
    _validate_cookie_security("development", True)


def test_non_production_environment_values_are_not_blocked():
    # Kontrol SADECE "production" icin - ENVIRONMENT hic ayarlanmamis ya da
    # "staging"/bos gibi baska bir deger tasiyan dev/test/CI ortamlarinda
    # uygulamanin yanlislikla baslamayi reddetmesini istemiyoruz.
    _validate_cookie_security("staging", False)
    _validate_cookie_security("", False)
