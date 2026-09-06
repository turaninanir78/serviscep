"""Meta WhatsApp Cloud API webhook alım noktası.

docs/architecture.md Bölüm 8/10: WhatsApp mesajlarının birincil alım
noktası backend'dir. Bu endpoint auth GEREKTİRMEZ (Meta'nın çağırdığı,
herkese açık bir uç nokta) - güvenlik, HMAC-SHA256 imza doğrulamasıyla
sağlanır. Meta'nın kuralı gereği, tenant eşleşmese bile HER ZAMAN 200
dönülür - aksi halde Meta aynı webhook'u tekrar tekrar dener.
"""
import hashlib
import hmac
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Conversation, Customer, Tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/whatsapp", tags=["webhooks"])

WHATSAPP_APP_SECRET = os.environ["WHATSAPP_APP_SECRET"]
WHATSAPP_WEBHOOK_VERIFY_TOKEN = os.environ["WHATSAPP_WEBHOOK_VERIFY_TOKEN"]


@router.get("")
def verify_webhook(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    if (
        hub_mode == "subscribe"
        and hub_verify_token is not None
        and hmac.compare_digest(hub_verify_token, WHATSAPP_WEBHOOK_VERIFY_TOKEN)
        and hub_challenge is not None
    ):
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification failed")


def _verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = signature_header[len("sha256=") :]
    return hmac.compare_digest(expected, provided)


def _store_inbound_message(db: Session, tenant: Tenant, message: dict, contacts: dict) -> None:
    from_number = message.get("from")
    if not from_number:
        return

    wa_message_id = message.get("id")
    message_text = message.get("text", {}).get("body")

    customer = (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant.id, Customer.whatsapp_number == from_number)
        .first()
    )
    if customer is None:
        display_name = contacts.get(from_number, {}).get("profile", {}).get("name")
        customer = Customer(
            tenant_id=tenant.id, whatsapp_number=from_number, display_name=display_name
        )
        db.add(customer)
        db.flush()

    db.add(
        Conversation(
            tenant_id=tenant.id,
            customer_id=customer.id,
            direction="in",
            message_text=message_text,
            wa_message_id=wa_message_id,
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # Meta, 200 donulmezse ayni webhook'u tekrar tekrar gonderebilir -
        # wa_message_id UNIQUE constraint'i sayesinde bu idempotent bir
        # sekilde atlanir (mukerrer kayit olusmaz).
        db.rollback()
        logger.info("Yinelenen wa_message_id, atlaniyor: %s", wa_message_id)


def _process_whatsapp_payload(db: Session, payload: dict) -> None:
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            messages = value.get("messages", [])
            if not messages or not phone_number_id:
                continue

            tenant = (
                db.query(Tenant)
                .filter(Tenant.whatsapp_phone_number_id == phone_number_id)
                .first()
            )
            if tenant is None:
                logger.warning("Bilinmeyen WhatsApp phone_number_id: %s", phone_number_id)
                continue

            contacts = {c.get("wa_id"): c for c in value.get("contacts", [])}
            for message in messages:
                _store_inbound_message(db, tenant, message, contacts)


@router.post("")
async def receive_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_hub_signature_256: str | None = Header(default=None),
):
    raw_body = await request.body()
    if not _verify_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    payload = await request.json()
    _process_whatsapp_payload(db, payload)

    # Meta'nin kurali: eslesme olmasa/hata olsa bile HER ZAMAN 200 - aksi
    # halde Meta ayni webhook'u tekrar tekrar dener.
    return {"status": "ok"}
