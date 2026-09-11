"""Sifre gucu politikasi - TUM sifre olusturma/degistirme noktalarinda
(kayit - eski ve telefon+OTP akislari, profilden sifre degistirme)
`validate_password_strength` cagrilarak MERKEZI olarak uygulanir; kural
tek yerde tanimli.

Bu projede su an bir sifre-sifirlama (unuttum) akisi YOK - eklenirse ayni
fonksiyon oradan da cagrilmali.
"""
from fastapi import HTTPException, status

MIN_PASSWORD_LENGTH = 6


def validate_password_strength(password: str) -> None:
    """Kural saglanmazsa 400 firlatir - hangi kuralin eksik oldugunu
    belirten net, Turkce bir mesajla (ilk karsilasilan eksiklik
    raporlanir, hepsi tek seferde degil - kullanicinin adim adim
    duzeltebilmesi icin ekstra bilgi degil, "en acil" sorunu gostermek
    yeterli)."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Şifre en az {MIN_PASSWORD_LENGTH} karakter olmalı.",
        )
    if not any(ch.isupper() for ch in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre en az bir büyük harf içermeli.",
        )
    if not any(ch.islower() for ch in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre en az bir küçük harf içermeli.",
        )
    if not any(not ch.isalnum() for ch in password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre en az bir özel karakter içermeli.",
        )
