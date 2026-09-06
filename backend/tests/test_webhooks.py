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
