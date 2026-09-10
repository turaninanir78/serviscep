"""GET/POST /webhooks/whatsapp testleri - gercek Meta hesabi olmadan,
elle hazirlanmis (simule edilmis) payload'larla.

Bu testler CALISAN sunucuya (http://localhost:8000) gercek HTTP istekleri
atar - docker compose stack'i ayakta olmali (bkz.
tests/test_appointment_race_condition.py'deki ayni desen).
"""
import hashlib
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.request

import pytest

from app.db import SessionLocal
from app.models import Conversation, Customer, Tenant

BASE_URL = "http://localhost:8000"
APP_SECRET = os.environ["WHATSAPP_APP_SECRET"]
VERIFY_TOKEN = os.environ["WHATSAPP_WEBHOOK_VERIFY_TOKEN"]


def _sign(body: bytes) -> str:
    digest = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def _post_webhook(body: bytes, signature: str | None) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Hub-Signature-256"] = signature
    req = urllib.request.Request(
        f"{BASE_URL}/webhooks/whatsapp", data=body, method="POST", headers=headers
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def _post_webhook_raw(body: bytes, signature: str | None) -> tuple[int, str]:
    """`_post_webhook` ile ayni, ama govdeyi JSON olarak parse ETMEYE
    CALISMAZ - bozuk istek testlerinde sunucu JSON olmayan bir govde
    (ör. "Internal Server Error" duz metni) donebiliyor."""
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Hub-Signature-256"] = signature
    req = urllib.request.Request(
        f"{BASE_URL}/webhooks/whatsapp", data=body, method="POST", headers=headers
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def _message_payload(
    phone_number_id: str, from_number: str, text: str, wa_message_id: str
) -> dict:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_TEST_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "905550000000",
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {"profile": {"name": "Test Musteri"}, "wa_id": from_number}
                            ],
                            "messages": [
                                {
                                    "from": from_number,
                                    "id": wa_message_id,
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _message_payload_without_id(phone_number_id: str, from_number: str, text: str) -> dict:
    """`_message_payload` ile ayni, ama mesaj nesnesinde `id` alani YOK.
    Gercek Meta trafiginde bu alan HER ZAMAN bulunur, ama DB semasi
    (`wa_message_id` NULLABLE) bunu zorunlu kilmiyor - bkz. asagidaki
    xfail test (idempotency acigi)."""
    payload = _message_payload(phone_number_id, from_number, text, wa_message_id="placeholder")
    del payload["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
    return payload


@pytest.fixture
def tenant_with_whatsapp():
    db = SessionLocal()
    tenant = Tenant(name="Webhook Test Tenant", whatsapp_phone_number_id="1234567890123")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    yield db, tenant.id

    db.rollback()
    db.query(Tenant).filter(Tenant.id == tenant.id).delete()
    db.commit()
    db.close()


def test_verify_webhook_with_correct_token_returns_challenge():
    status_code, body = _get(
        f"{BASE_URL}/webhooks/whatsapp?hub.mode=subscribe"
        f"&hub.verify_token={VERIFY_TOKEN}&hub.challenge=abc123"
    )
    assert status_code == 200
    assert body == "abc123"


def test_verify_webhook_with_incorrect_token_returns_403():
    status_code, _ = _get(
        f"{BASE_URL}/webhooks/whatsapp?hub.mode=subscribe"
        f"&hub.verify_token=wrong-token&hub.challenge=abc123"
    )
    assert status_code == 403


def test_valid_signature_is_accepted(tenant_with_whatsapp):
    payload = _message_payload("1234567890123", "905551110001", "Merhaba", "wamid.VALIDSIG")
    body = json.dumps(payload).encode()

    status_code, _ = _post_webhook(body, _sign(body))

    assert status_code == 200


def test_invalid_signature_is_rejected(tenant_with_whatsapp):
    payload = _message_payload("1234567890123", "905551110002", "Merhaba", "wamid.BADSIG")
    body = json.dumps(payload).encode()

    status_code, _ = _post_webhook(body, "sha256=" + "0" * 64)

    assert status_code == 403


def test_known_phone_number_id_message_is_recorded(tenant_with_whatsapp):
    db, tenant_id = tenant_with_whatsapp
    payload = _message_payload(
        "1234567890123", "905551110003", "Randevu almak istiyorum", "wamid.KNOWN1"
    )
    body = json.dumps(payload).encode()

    status_code, _ = _post_webhook(body, _sign(body))
    assert status_code == 200

    conversation = (
        db.query(Conversation)
        .filter(Conversation.tenant_id == tenant_id, Conversation.wa_message_id == "wamid.KNOWN1")
        .first()
    )
    assert conversation is not None
    assert conversation.direction == "in"
    assert conversation.message_text == "Randevu almak istiyorum"

    customer = (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant_id, Customer.whatsapp_number == "905551110003")
        .first()
    )
    assert customer is not None
    assert conversation.customer_id == customer.id


def test_unknown_phone_number_id_returns_200_but_is_not_recorded():
    payload = _message_payload(
        "no-such-phone-number-id", "905551110004", "Merhaba", "wamid.UNKNOWN1"
    )
    body = json.dumps(payload).encode()

    status_code, _ = _post_webhook(body, _sign(body))
    assert status_code == 200

    db = SessionLocal()
    try:
        conversation = (
            db.query(Conversation).filter(Conversation.wa_message_id == "wamid.UNKNOWN1").first()
        )
        assert conversation is None
    finally:
        db.close()


# --- GET /webhooks/whatsapp - hub.mode edge case'leri ---


def test_verify_webhook_with_missing_hub_mode_returns_403():
    status_code, _ = _get(
        f"{BASE_URL}/webhooks/whatsapp?hub.verify_token={VERIFY_TOKEN}&hub.challenge=abc123"
    )
    assert status_code == 403


def test_verify_webhook_with_wrong_hub_mode_value_returns_403():
    status_code, _ = _get(
        f"{BASE_URL}/webhooks/whatsapp?hub.mode=unsubscribe"
        f"&hub.verify_token={VERIFY_TOKEN}&hub.challenge=abc123"
    )
    assert status_code == 403


def test_verify_webhook_failure_does_not_leak_challenge_in_body():
    status_code, body = _get(
        f"{BASE_URL}/webhooks/whatsapp?hub.mode=subscribe"
        f"&hub.verify_token=wrong-token&hub.challenge=SECRETCHALLENGE"
    )
    assert status_code == 403
    assert "SECRETCHALLENGE" not in body


# --- POST /webhooks/whatsapp - imza dogrulama edge case'leri ---


def test_missing_signature_header_is_rejected_and_not_recorded(tenant_with_whatsapp):
    payload = _message_payload("1234567890123", "905551110005", "Imzasiz istek", "wamid.NOSIG1")
    body = json.dumps(payload).encode()

    status_code, _ = _post_webhook(body, signature=None)
    assert status_code == 403

    db = SessionLocal()
    try:
        assert (
            db.query(Conversation).filter(Conversation.wa_message_id == "wamid.NOSIG1").first()
            is None
        )
    finally:
        db.close()


def test_signature_valid_for_different_payload_is_rejected_as_tampered(tenant_with_whatsapp):
    """Gercek bir imzayi ALIP BASKA bir govdeye uygulamak (ornegin bir
    ara katmanin/saldirganin govdeyi degistirmesi) da gecersiz imza kadar
    reddedilmeli - bu, mevcut test_invalid_signature_is_rejected'in
    kullandigi "rastgele/uydurma" imzadan farkli, daha gercekci bir
    saldiri senaryosu."""
    original = _message_payload(
        "1234567890123", "905551110006", "Orijinal mesaj", "wamid.TAMPERED1"
    )
    tampered = _message_payload(
        "1234567890123", "905551110006", "Degistirilmis mesaj", "wamid.TAMPERED1"
    )
    signature_for_original = _sign(json.dumps(original).encode())
    tampered_body = json.dumps(tampered).encode()

    status_code, _ = _post_webhook(tampered_body, signature_for_original)
    assert status_code == 403

    db = SessionLocal()
    try:
        assert (
            db.query(Conversation)
            .filter(Conversation.wa_message_id == "wamid.TAMPERED1")
            .first()
            is None
        )
    finally:
        db.close()


def test_signature_signed_with_wrong_secret_is_rejected(tenant_with_whatsapp):
    payload = _message_payload(
        "1234567890123", "905551110007", "Yanlis secret ile imzalanmis", "wamid.WRONGSECRET1"
    )
    body = json.dumps(payload).encode()
    wrong_secret_signature = (
        "sha256=" + hmac.new(b"totally-wrong-secret", body, hashlib.sha256).hexdigest()
    )

    status_code, _ = _post_webhook(body, wrong_secret_signature)
    assert status_code == 403

    db = SessionLocal()
    try:
        assert (
            db.query(Conversation)
            .filter(Conversation.wa_message_id == "wamid.WRONGSECRET1")
            .first()
            is None
        )
    finally:
        db.close()


# --- POST /webhooks/whatsapp - bozuk govde ---
#
# Gecerli imzali ama bozuk/bos JSON govdeli bir istek artik receive_webhook
# icindeki try/except json.JSONDecodeError tarafindan yakalanip 200 ile
# yanitlaniyor - dosyanin basindaki "Meta'nin kurali: HER ZAMAN 200 don"
# felsefesiyle tutarli (Meta aksi halde ayni bozuk istegi tekrar tekrar
# dener). Onceden bu 500 donduren, xfail ile belgelenmis bilinen bir aciktı.


def test_malformed_json_body_with_valid_signature_does_not_return_500():
    body = b"{bu gecerli bir json degil"
    status_code, _ = _post_webhook_raw(body, _sign(body))
    assert status_code == 200


def test_empty_body_with_valid_signature_does_not_return_500():
    body = b""
    status_code, _ = _post_webhook_raw(body, _sign(body))
    assert status_code == 200


def test_server_remains_usable_after_malformed_request(tenant_with_whatsapp):
    """Yukaridaki 500'ler uygulama SURECINI cokertmiyor - ayni sunucu,
    hemen ardindan gelen gecerli bir istegi normal isliyor mu, onu
    dogruluyoruz."""
    malformed_body = b"{not valid json"
    _post_webhook_raw(malformed_body, _sign(malformed_body))

    payload = _message_payload(
        "1234567890123",
        "905551110008",
        "Bozuk istekten sonra hala calisiyor mu",
        "wamid.AFTERCRASH1",
    )
    body = json.dumps(payload).encode()
    status_code, _ = _post_webhook(body, _sign(body))
    assert status_code == 200

    db = SessionLocal()
    try:
        assert (
            db.query(Conversation)
            .filter(Conversation.wa_message_id == "wamid.AFTERCRASH1")
            .first()
            is not None
        )
    finally:
        db.close()


# --- POST /webhooks/whatsapp - gecerli JSON ama obje degil ---
#
# json.loads() bir dict yerine liste/null/string/sayi da dondurebilir -
# _process_whatsapp_payload'un payload.get(...) cagrisi bu durumda
# AttributeError'a (list/str/int/None'da .get() yok) yol acip 500
# donduruyordu. receive_webhook artik parse'tan sonra isinstance(payload,
# dict) kontrolu yapip degilse islenmeden 200 donuyor - bozuk JSON'la ayni
# felsefe.


def test_valid_json_array_body_does_not_return_500():
    body = b"[]"
    status_code, _ = _post_webhook_raw(body, _sign(body))
    assert status_code == 200


def test_valid_json_null_body_does_not_return_500():
    body = b"null"
    status_code, _ = _post_webhook_raw(body, _sign(body))
    assert status_code == 200


def test_valid_json_string_body_does_not_return_500():
    body = b'"just a string"'
    status_code, _ = _post_webhook_raw(body, _sign(body))
    assert status_code == 200


def test_valid_json_number_body_does_not_return_500():
    body = b"42"
    status_code, _ = _post_webhook_raw(body, _sign(body))
    assert status_code == 200


# --- POST /webhooks/whatsapp - govde boyutu ---


def test_large_payload_is_processed_no_application_level_size_limit(tenant_with_whatsapp):
    """Uygulama kodunda govde boyutu siniri YOK - bu test mevcut durumu
    belgeliyor (gorev talimati geregi bir sinir EKLENMEDI)."""
    huge_text = "x" * 300_000  # gercek bir WhatsApp metin mesajindan COK daha buyuk
    payload = _message_payload("1234567890123", "905551110009", huge_text, "wamid.BIGPAYLOAD1")
    body = json.dumps(payload).encode()

    status_code, _ = _post_webhook(body, _sign(body))
    assert status_code == 200

    db = SessionLocal()
    try:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.wa_message_id == "wamid.BIGPAYLOAD1")
            .first()
        )
        assert conversation is not None
        assert conversation.message_text == huge_text
    finally:
        db.close()


# --- POST /webhooks/whatsapp - tekrar eden teslimat (Meta retry) ---


def test_duplicate_delivery_with_same_wa_message_id_is_idempotent(tenant_with_whatsapp):
    """Meta, 200 alamadiginda (veya baska bir nedenle) ayni webhook'u
    birden fazla kez gonderebilir. `wa_message_id` UNIQUE constraint +
    IntegrityError yakalama (bkz. app/api/webhooks.py::_store_inbound_message)
    sayesinde bu idempotent olmali - bu test BUG DEGIL, mevcut kodun zaten
    dogru davrandigini dogruluyor."""
    payload = _message_payload(
        "1234567890123", "905551110010", "Iki kere gonderilen mesaj", "wamid.DUPTEST1"
    )
    body = json.dumps(payload).encode()
    signature = _sign(body)

    status_1, _ = _post_webhook(body, signature)
    status_2, _ = _post_webhook(body, signature)
    assert status_1 == 200
    assert status_2 == 200

    db = SessionLocal()
    try:
        conversations = (
            db.query(Conversation).filter(Conversation.wa_message_id == "wamid.DUPTEST1").all()
        )
        assert len(conversations) == 1

        customers = (
            db.query(Customer).filter(Customer.whatsapp_number == "905551110010").all()
        )
        assert len(customers) == 1
    finally:
        db.close()


def test_duplicate_delivery_without_wa_message_id_is_not_deduplicated(tenant_with_whatsapp):
    """`id` alani eksik olsa da _fallback_message_key (bkz.
    app/api/webhooks.py) mesajin degismeyen alanlarindan deterministik bir
    yedek anahtar turetiyor, bu da wa_message_id UNIQUE constraint'ine
    tabi oluyor - onceden bu, mukerrer Conversation kaydina yol acan
    bilinen bir aciktı."""
    payload = _message_payload_without_id(
        "1234567890123", "905551110011", "Id'siz mesaj, iki kere gonderiliyor"
    )
    body = json.dumps(payload).encode()
    signature = _sign(body)

    status_1, _ = _post_webhook(body, signature)
    status_2, _ = _post_webhook(body, signature)
    assert status_1 == 200
    assert status_2 == 200

    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.whatsapp_number == "905551110011").first()
        assert customer is not None
        conversations = (
            db.query(Conversation).filter(Conversation.customer_id == customer.id).all()
        )
        assert len(conversations) == 1
    finally:
        db.close()


# --- POST /webhooks/whatsapp - eszamanli yeni musteri olusturma ---
#
# Gercek concurrency'i (iki thread'in tam ayni anda calismasi) sirali HTTP
# istekleriyle guvenilir bicimde tetiklemek zor - ikinci istek genelde
# ilkinin commit'ini zaten gormus olur, hicbir INSERT catismasi yasanmaz.
# Bunun yerine Postgres'in kendi transaction izolasyonunu kullanip
# IntegrityError'i deterministik olarak tetikliyoruz: bu thread ayni
# (tenant, whatsapp_number) icin bir Customer satirini ACIK bir
# transaction'da (flush edip commit ETMEDEN) tutarken, webhook istegi ayri
# bir thread'de gonderiliyor. Webhook'un kendi INSERT'i bu satirin serbest
# kalmasini beklemek zorunda kalir (Postgres UNIQUE index davranisi); biz
# ana thread'de commit edince, webhook'un INSERT'i gercek bir
# IntegrityError'a donusur - _store_inbound_message bunu rollback+re-query
# ile idempotent sekilde ele almali (500 degil, 200 ve TEK Customer satiri).


def test_concurrent_new_customer_creation_does_not_return_500(tenant_with_whatsapp):
    db, tenant_id = tenant_with_whatsapp
    phone_number = "905551110012"

    holder_db = SessionLocal()
    holder_db.add(Customer(tenant_id=tenant_id, whatsapp_number=phone_number))
    holder_db.flush()  # satiri ekler ama commit etmez - webhook'un INSERT'i buna kilitlenir

    result: dict = {}

    def send_webhook():
        payload = _message_payload(
            "1234567890123", phone_number, "Eszamanli musteri testi", "wamid.RACETEST1"
        )
        body = json.dumps(payload).encode()
        result["status"], _ = _post_webhook(body, _sign(body))

    thread = threading.Thread(target=send_webhook)
    thread.start()
    time.sleep(1)  # webhook'un SELECT+INSERT'ini baslatip kilide takilmasi icin sure taniyoruz
    holder_db.commit()  # simdi webhook'un bekleyen INSERT'i IntegrityError'a donusur
    thread.join(timeout=15)

    try:
        assert not thread.is_alive(), "webhook istegi zaman asimina ugradi"
        assert result.get("status") == 200

        customers = (
            db.query(Customer)
            .filter(Customer.tenant_id == tenant_id, Customer.whatsapp_number == phone_number)
            .all()
        )
        assert len(customers) == 1

        conversations = (
            db.query(Conversation)
            .filter(Conversation.customer_id == customers[0].id)
            .all()
        )
        assert len(conversations) == 1
        assert conversations[0].wa_message_id == "wamid.RACETEST1"
    finally:
        holder_db.close()
