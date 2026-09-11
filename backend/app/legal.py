"""Sozlesme/onay (KVKK) altyapisi.

Bu dosyada (ve bagli migration/model'lerde) hukuki metinlerin GERCEK
icerigi YOK - LegalDocument.content su an sadece yer tutucu metin tasiyor.
Gercek metni eklerken buradaki KOD DEGISMEZ, sadece `legal_documents`
tablosuna yeni bir satir eklenir (bkz. migration 0007'nin sonundaki seed
INSERT'leri, gercek metin ekleme rehberi olarak).
"""
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.models import DocumentAcceptance, LegalDocument

# Kayit sirasinda onaylanmasi ZORUNLU dokuman turleri. Yeni bir tur eklemek
# (orn. "cookie_policy") SADECE bu listeye bir satir eklemek - kayit akisi
# otomatik olarak o turun de en guncel versiyonunu arayip onay kaydi
# olusturur (dokuman DB'de yoksa sessizce atlanir, bkz. asagisi).
REQUIRED_DOCUMENT_TYPES = ["terms_of_service", "privacy_notice"]


def get_latest_document(db: Session, doc_type: str) -> LegalDocument | None:
    return (
        db.query(LegalDocument)
        .filter(LegalDocument.type == doc_type)
        .order_by(LegalDocument.effective_date.desc(), LegalDocument.id.desc())
        .first()
    )


def _client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    return request.client.host


def record_registration_consent(
    db: Session,
    *,
    accepted_terms: bool,
    tenant_id: int,
    user_id: int,
    request: Request | None,
) -> None:
    """Kayit tamamlanmadan HEMEN once cagrilir - `accepted_terms` False ise
    kaydi 400 ile reddeder (henuz commit edilmemis Tenant/User de rollback
    edilir). True ise, o an gecerli EN GUNCEL zorunlu dokuman versiyonlari
    icin DocumentAcceptance satirlari ekler (henuz commit ETMEZ - cagiran
    tarafin kendi Tenant/User commit'iyle AYNI islemde, atomik olarak
    kaydedilsin diye)."""
    if not accepted_terms:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kullanim sartlarini ve aydinlatma metnini kabul etmelisiniz.",
        )

    ip_address = _client_ip(request)
    for doc_type in REQUIRED_DOCUMENT_TYPES:
        document = get_latest_document(db, doc_type)
        if document is None:
            # Bu ortamda o tur icin henuz hicbir LegalDocument yok (orn.
            # migration seed'i calismamis bir dev ortami) - kaydi
            # ENGELLEMEK yerine atliyoruz, aksi halde eksik bir seed
            # dokumani tum kayit akisini kilitlerdi.
            continue
        db.add(
            DocumentAcceptance(
                tenant_id=tenant_id,
                user_id=user_id,
                document_id=document.id,
                ip_address=ip_address,
            )
        )
