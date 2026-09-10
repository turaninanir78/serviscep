"""Auth endpoint'leri (login, register - web ve mobil) icin IP bazli rate
limiting.

slowapi (limits kutuphanesini FastAPI/Starlette'e baglayan ince bir katman)
kullaniliyor - FastAPI ekosisteminde bu is icin standart, aktif bakimi olan
secim; Redis gibi ek bir altyapi GEREKTIRMIYOR (varsayilan bellek-ici
depolama tek-instance bir deployment icin yeterli, ileride cok-instance bir
deployment gerekirse `storage_uri` ile Redis'e gecirilebilir).

ENVIRONMENT=production DISINDA (yani mevcut dev/test/CI ortaminda)
varsayilan olarak DEVRE DISI - aksi halde ayni container'da art arda calisan
TUM testler (hepsi ayni loopback IP'den login/register cagirir) ayni
paylasilan sayaci tuketip birbirini kirardi. Gercekten zorlandigini
dogrulayan testler (tests/test_auth_rate_limit.py) bu yuzden normal test
kosusunda skip edilir - RATE_LIMIT_ENABLED=true ile ayrica baslatilmis bir
container'a karsi calistirilmalari gerekir (bkz. o dosyanin basindaki
aciklama ve gorev ozeti).
"""
import os

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.security import ENVIRONMENT


def _env_or_default(name: str, default: str) -> str:
    """os.environ.get(name, default) tek basina yetmiyor: docker-compose.yml
    bu degiskenleri `${VAR:-}` (bos varsayilan) ile geciriyor, yani host'ta
    ayarlanmamis olsalar bile container icinde BOS STRING olarak (yok
    degil, var-ama-bos) gorunuyorlar - duz `.get()` bu durumda `default`
    yerine "" donerdi. Bos/bosluk-only bir deger de "ayarlanmamis" sayilir.
    """
    value = os.environ.get(name, "").strip()
    return value if value else default


RATE_LIMIT_ENABLED = (
    _env_or_default("RATE_LIMIT_ENABLED", "true" if ENVIRONMENT == "production" else "false")
    .lower()
    == "true"
)

# Task'ta onerilen varsayilanlar:
# - Login: dakikada 5 deneme. Brute-force sifre tahminini pratikte
#   imkansizlastirirken (dakikada 5 deneme ile anlamli bir sozluk saldirisi
#   yapilamaz), sifresini unutup birkac kez yanlis yazan gercek bir
#   kullaniciyi cezalandirmayacak kadar gevsek.
# - Register: saatte 10 deneme. Gercek bir isletme sahibi neredeyse hep
#   SADECE BIR KEZ kayit olur - bu limit otomatik spam hesap acmayi
#   zorlastirirken meru bir kayit denemesini pratikte hic etkilemez.
AUTH_LOGIN_RATE_LIMIT = _env_or_default("AUTH_LOGIN_RATE_LIMIT", "5/minute")
AUTH_REGISTER_RATE_LIMIT = _env_or_default("AUTH_REGISTER_RATE_LIMIT", "10/hour")

limiter = Limiter(key_func=get_remote_address, enabled=RATE_LIMIT_ENABLED)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Mevcut hata sozlesmesiyle (her yerde HTTPException(detail=...))
    tutarli, acik bir 429 govdesi - slowapi'nin kendi varsayilan handler'i
    farkli bir sekil ({"error": ...}) donuyor.
    """
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many attempts. Please try again later."},
    )
