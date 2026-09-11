"""Musteri PII sifreleme testleri.

`Customer.whatsapp_number`/`display_name` artik DB'de Fernet ile sifreli
saklaniyor (bkz. app/db_types.py::EncryptedString) - bu testler:
1. Ham DB satirinin GERCEKTEN sifreli (ciphertext) oldugunu,
2. API yanitinin hala duz metin donduğunu (uygulama katmani icin seffaf),
3. Ayni duz metnin FARKLI satirlarda FARKLI ciphertext urettigini (Fernet
   non-determinizmi),
4. Aramanin/tekilligin bu yuzden ayri bir deterministik hash sutunu
   (whatsapp_number_hash) uzerinden calistigini,
5. Encrypt/decrypt round-trip'in (migration'in veri donusumunde kullandigi
   ayni islem) veri kaybina yol acmadigini

dogrular. Diger testlerle ayni yaklasim: calisan sunucuya gercek HTTP
istekleri, DB temizligi tenant uzerinden manuel.
"""
import random
import string

import requests
from sqlalchemy import text

from app.crypto import decrypt_pii, encrypt_pii, hash_pii_lookup
from app.db import SessionLocal
from app.models import Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _register_and_get_session(tenant_name: str) -> tuple[requests.Session, str]:
    phone_raw = _random_phone_raw()
    otp_res = requests.post(
        f"{BASE_URL}/auth/register/request-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
    )
    assert otp_res.status_code == 200, otp_res.text
    code = otp_res.json()["debug_code"]

    verify_res = requests.post(
        f"{BASE_URL}/auth/register/verify-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw, "code": code},
    )
    assert verify_res.status_code == 200, verify_res.text
    registration_token = verify_res.json()["registration_token"]

    session = requests.Session()
    complete_res = session.post(
        f"{BASE_URL}/auth/register/complete",
        json={
            "registration_token": registration_token,
            "tenant_name": tenant_name,
            "password": "S3cret-pw!",
            "accepted_terms": True,
        },
    )
    assert complete_res.status_code == 201, complete_res.text
    return session, phone_raw


def _cleanup_by_phone(phone_raw: str) -> None:
    normalized = normalize_phone(COUNTRY_CODE, phone_raw)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone == normalized).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
            db.commit()
    finally:
        db.close()


def test_encrypt_decrypt_round_trip_preserves_original_value():
    """Migration'in encrypt-in-place adiminda kullandigi ayni islem - bu
    saf fonksiyon testi, o donusumun veri kaybina yol acmadigini dogrular
    (gercek migration'i testte tekrar calistirmak yerine, ayni islemi
    dogrudan test ediyoruz - bkz. test_security_config.py'deki ayni
    yaklasim)."""
    original = "905551234567"
    encrypted = encrypt_pii(original)
    assert encrypted != original
    assert decrypt_pii(encrypted) == original


def test_same_value_hashes_identically_different_values_do_not():
    assert hash_pii_lookup("905551234567") == hash_pii_lookup("905551234567")
    assert hash_pii_lookup("905551234567") != hash_pii_lookup("905551234568")


def test_customer_whatsapp_number_is_encrypted_in_db_but_plaintext_in_api_response():
    session, phone_raw = _register_and_get_session("Encryption Test Tenant")
    try:
        create_res = session.post(
            f"{BASE_URL}/customers",
            json={"whatsapp_number": "905559990011", "display_name": "Ayşe Yılmaz"},
        )
        assert create_res.status_code == 201
        body = create_res.json()
        assert body["whatsapp_number"] == "905559990011"
        assert body["display_name"] == "Ayşe Yılmaz"
        customer_id = body["id"]

        db = SessionLocal()
        try:
            row = db.execute(
                text("SELECT whatsapp_number, display_name FROM customers WHERE id = :id"),
                {"id": customer_id},
            ).first()
            assert row.whatsapp_number != "905559990011"
            assert row.display_name != "Ayşe Yılmaz"
            assert decrypt_pii(row.whatsapp_number) == "905559990011"
            assert decrypt_pii(row.display_name) == "Ayşe Yılmaz"
        finally:
            db.close()

        get_res = session.get(f"{BASE_URL}/customers/{customer_id}")
        assert get_res.status_code == 200
        assert get_res.json()["whatsapp_number"] == "905559990011"
        assert get_res.json()["display_name"] == "Ayşe Yılmaz"
    finally:
        _cleanup_by_phone(phone_raw)


def test_same_plaintext_produces_different_ciphertext_in_different_rows():
    """Fernet KASITLI OLARAK non-deterministik - bu, ayni telefon numarasi
    iki farkli musteri satirina yazilsa (farkli tenant'larda) bile
    ciphertext'lerin FARKLI olacagini, dolayisiyla dogrudan esitlik
    sorgusunun neden mumkun olmadigini (bkz. whatsapp_number_hash)
    dogrudan gosterir."""
    session_a, phone_a = _register_and_get_session("Cipher Diff Tenant A")
    session_b, phone_b = _register_and_get_session("Cipher Diff Tenant B")
    try:
        res_a = session_a.post(f"{BASE_URL}/customers", json={"whatsapp_number": "905559990033"})
        res_b = session_b.post(f"{BASE_URL}/customers", json={"whatsapp_number": "905559990033"})
        assert res_a.status_code == 201
        assert res_b.status_code == 201

        db = SessionLocal()
        try:
            row_a = db.execute(
                text("SELECT whatsapp_number FROM customers WHERE id = :id"),
                {"id": res_a.json()["id"]},
            ).first()
            row_b = db.execute(
                text("SELECT whatsapp_number FROM customers WHERE id = :id"),
                {"id": res_b.json()["id"]},
            ).first()
            assert row_a.whatsapp_number != row_b.whatsapp_number
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_a)
        _cleanup_by_phone(phone_b)


def test_duplicate_whatsapp_number_within_same_tenant_is_still_rejected():
    """Tekillik kisitlamasi artik whatsapp_number_hash uzerinde (bkz.
    migration 0007) - bu, eski (duz metin uzerindeki) davranisin
    korundugunu dogrular."""
    session, phone_raw = _register_and_get_session("Dup Customer Tenant")
    try:
        first = session.post(f"{BASE_URL}/customers", json={"whatsapp_number": "905559990022"})
        assert first.status_code == 201

        second = session.post(f"{BASE_URL}/customers", json={"whatsapp_number": "905559990022"})
        assert second.status_code == 409
    finally:
        _cleanup_by_phone(phone_raw)
