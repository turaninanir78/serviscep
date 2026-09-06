"""WhatsApp Cloud API istemcisi - giden mesaj gonderimi.

docs/architecture.md Bolum 9/13'teki "yan etki" ilkesiyle tutarli: bu
modul cekirdek randevu akisinin bir parcasi degil, ona eklenen bir
bildirim katmanidir. Bu yuzden send_whatsapp_message hicbir zaman
exception firlatmaz - basarisiz bir WhatsApp gonderimi, randevu
olusturma/iptal etme gibi asil islemi ASLA bozmamali.
"""
import logging

import requests
from sqlalchemy.orm import Session

from app.crypto import decrypt_token
from app.models import Conversation, Tenant

logger = logging.getLogger(__name__)

GRAPH_API_VERSION = "v21.0"
_REQUEST_TIMEOUT_SECONDS = 10


def send_whatsapp_message(
    db: Session,
    tenant: Tenant,
    to_number: str,
    text: str,
    customer_id: int | None = None,
) -> bool:
    """Meta WhatsApp Cloud API'ye giden bir metin mesaji gonderir ve
    basarili olursa conversations'a direction='out' olarak kaydeder.

    Tenant'in WhatsApp baglantisi yoksa sessizce False doner. Herhangi bir
    hata (ag, Meta API, veya DB) yakalanip loglanir - hicbir zaman
    caginan taraf icin exception firlatilmaz.
    """
    if not tenant.whatsapp_phone_number_id or not tenant.whatsapp_access_token_encrypted:
        return False

    try:
        access_token = decrypt_token(tenant.whatsapp_access_token_encrypted)
        url = (
            f"https://graph.facebook.com/{GRAPH_API_VERSION}/"
            f"{tenant.whatsapp_phone_number_id}/messages"
        )
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            json={
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": text},
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        wa_message_id = None
        try:
            wa_message_id = response.json()["messages"][0]["id"]
        except (ValueError, KeyError, IndexError):
            pass

        db.add(
            Conversation(
                tenant_id=tenant.id,
                customer_id=customer_id,
                direction="out",
                message_text=text,
                wa_message_id=wa_message_id,
            )
        )
        db.commit()
        return True
    except Exception:
        db.rollback()
        logger.exception(
            "WhatsApp mesaji gonderilemedi (tenant_id=%s, to=%s)", tenant.id, to_number
        )
        return False
