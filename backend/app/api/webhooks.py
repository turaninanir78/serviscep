"""Meta WhatsApp Cloud API webhook alım noktası.

docs/architecture.md Bölüm 8/10: WhatsApp mesajlarının birincil alım
noktası backend'dir. Bu endpoint auth GEREKTİRMEZ (Meta'nın çağırdığı,
herkese açık bir uç nokta) - güvenlik, HMAC-SHA256 imza doğrulamasıyla
sağlanır. Meta'nın kuralı gereği, tenant eşleşmese bile HER ZAMAN 200
dönülür - aksi halde Meta aynı webhook'u tekrar tekrar dener.
"""
import hashlib
import hmac
import json
import logging
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.crypto import hash_pii_lookup
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


def _fallback_message_key(tenant_id: int, from_number: str, message: dict) -> str:
    """Gercek Meta trafiginde `id` alani her zaman bulunur, ama sema bunu
    zorunlu kilmiyor (bkz. Conversation.wa_message_id - NULLABLE). Bu alan
    eksikse, Meta'nin bir tekrar denemesinde AYNEN koruyacagi alanlardan
    (tenant + gonderen numara + timestamp + metin) deterministik bir
    yedek anahtar turetiyoruz - boylece wa_message_id UNIQUE constraint'i
    id'siz mesajlar icin de idempotency saglar. Gercek wa_message_id'lerle
    (hep "wamid." ile baslar) cakismayi engellemek icin ayri bir on ek
    kullaniliyor.
    """
    text = message.get("text", {}).get("body")
    raw = f"{tenant_id}:{from_number}:{message.get('timestamp')}:{text}"
    digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"fallback:{digest}"


def _store_inbound_message(db: Session, tenant: Tenant, message: dict, contacts: dict) -> None:
    from_number = message.get("from")
    if not from_number:
        return

    wa_message_id = message.get("id") or _fallback_message_key(tenant.id, from_number, message)
    message_text = message.get("text", {}).get("body")

    # Customer.whatsapp_number sifreli (bkz. app/db_types.py::EncryptedString) -
    # Fernet non-deterministik oldugu icin dogrudan esitlik sorgusu
    # calismaz, bunun yerine deterministik hash sutunu kullanilir (bkz.
    # app/models.py::Customer docstring'i).
    from_number_hash = hash_pii_lookup(from_number)
    customer = (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant.id, Customer.whatsapp_number_hash == from_number_hash)
        .first()
    )
    if customer is None:
        display_name = contacts.get(from_number, {}).get("profile", {}).get("name")
        customer = Customer(
            tenant_id=tenant.id, whatsapp_number=from_number, display_name=display_name
        )
        db.add(customer)
        try:
            db.flush()
        except IntegrityError:
            # Ayni yeni telefon numarasiyla eszamanli iki webhook, ikisi de
            # yukarideki sorguda customer'i None bulup ayni anda yeni
            # Customer eklemeye calisirsa: (tenant_id, whatsapp_number)
            # UNIQUE constraint'i (bkz. migration
            # uq_customers_tenant_id_whatsapp_number) kaybeden istegin
            # flush'inda IntegrityError firlatir. wa_message_id
            # idempotency mantigiyla tutarli olarak: rollback edip diger
            # istegin az once olusturdugu kaydi tekrar sorguluyoruz.
            db.rollback()
            customer = (
                db.query(Customer)
                .filter(
                    Customer.tenant_id == tenant.id,
                    Customer.whatsapp_number_hash == from_number_hash,
                )
                .first()
            )
            if customer is None:
                # Cok dusuk ihtimalli, farkli bir hata - islemeye devam
                # edecek bir musteri yok, sessizce cik.
                logger.warning(
                    "Musteri flush'ta IntegrityError sonrasi bulunamadi: tenant=%s, from=%s",
                    tenant.id,
                    from_number,
                )
                return

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

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        # Bozuk/bos govde de dosyanin basindaki "her zaman 200" kuralina
        # tabi - islenecek bir sey yok ama 500 donup Meta'yi ayni bozuk
        # istegi sonsuza kadar tekrar etmeye itmemeliyiz.
        logger.warning("Gecersiz JSON govdesi, islenmeden atlaniyor")
        return {"status": "ok"}

    if not isinstance(payload, dict):
        # Gecerli JSON ama beklenen sekilde degil (liste, null, string,
        # sayi...) - _process_whatsapp_payload'un .get() cagrilari bir
        # dict varsayiyor, bozuk JSON ile ayni "islenecek bir sey yok,
        # 200 don" mantigina tabi olmali.
        logger.warning(
            "JSON govdesi obje degil (%s turu), islenmeden atlaniyor", type(payload).__name__
        )
        return {"status": "ok"}

    _process_whatsapp_payload(db, payload)

    # Meta'nin kurali: eslesme olmasa/hata olsa bile HER ZAMAN 200 - aksi
    # halde Meta ayni webhook'u tekrar tekrar dener.
    return {"status": "ok"}
