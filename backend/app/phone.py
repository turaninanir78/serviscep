"""Telefon numarasi normalizasyonu (E.164).

Web ve mobil, kullaniciya bir ulke kodu secici (su an SADECE +90) + ham
numara alani gosteriyor - kullanici "0532...", "532..." ya da araya bosluk/
tire koyarak yazsa da, DB'de HEP tek, normalize edilmis E.164 formatinda
(+905XXXXXXXXX) saklaniyor. Normalizasyon SADECE burada, backend'de
yapiliyor (web/mobil ham girdiyi oldugu gibi gonderiyor) - aksi halde
"0532..." ile "532..." ayni numara oldugu halde OTP/login sirasinda farkli
kayit gibi gorunebilirdi.

Yeni bir ulke eklemek SADECE SUPPORTED_COUNTRY_CODES'a (ve web/mobildeki
karsilik gelen dropdown/picker listesine) bir satir eklemek demek - bu
fonksiyonun kendisi veya DB semasi degismiyor.
"""
import re

from fastapi import HTTPException, status

DEFAULT_COUNTRY_CODE = "+90"

# Su an sadece Turkiye destekleniyor - ileride yeni bir ulke eklemek bu
# listeye bir satir eklemekten ibaret (bkz. modul docstring'i).
SUPPORTED_COUNTRY_CODES = {"+90"}


def normalize_phone(country_code: str, national_number: str) -> str:
    """(ulke kodu, ham ulusal numara) -> E.164 (ornek: "+90", "0532..." ->
    "+90532...").

    Ulusal numaranin basindaki 0 (varsa) atilir, rakam disi her karakter
    (bosluk, tire, parantez) temizlenir.
    """
    country_code = country_code.strip()
    if not country_code.startswith("+"):
        country_code = f"+{country_code}"

    if country_code not in SUPPORTED_COUNTRY_CODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Desteklenmeyen ulke kodu",
        )

    digits = re.sub(r"\D", "", national_number)
    digits = digits.lstrip("0")

    if not (7 <= len(digits) <= 14):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Gecersiz telefon numarasi",
        )

    return f"{country_code}{digits}"
