from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.legal import REQUIRED_DOCUMENT_TYPES, get_latest_document
from app.models import DocumentAcceptance, LegalDocument
from app.schemas.legal import AcceptConsentRequest, ConsentStatusOut, LegalDocumentOut
from app.security import AuthContext, get_current_tenant

router = APIRouter(prefix="/legal", tags=["legal"])

# NOT: /consent-status ve /accept, asagidaki /{doc_type} catch-all rotasindan
# ONCE tanimlanmali - aksi halde FastAPI "consent-status" degerini bir
# doc_type path parametresi sanip yanlis rotaya yonlendirir (Starlette
# rotalari TANIMLANMA sirasina gore eslestirir).


@router.get("/consent-status", response_model=ConsentStatusOut)
def get_consent_status(
    db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_tenant)
) -> ConsentStatusOut:
    """Giris yapmis kullanicinin, ZORUNLU dokuman turlerinin EN GUNCEL
    versiyonlarini onaylayip onaylamadigini kontrol eder - bir dokuman
    yeni bir versiyona guncellendiginde (yeni bir LegalDocument satiri
    eklendiginde), eski versiyonu onaylamis kullanicilar otomatik olarak
    "onay bekliyor" durumuna duser (DocumentAcceptance sadece belirli bir
    document_id icin arandigi icin, eski versiyonun onayi yeni versiyon
    icin gecerli sayilmaz)."""
    pending: list[LegalDocument] = []
    for doc_type in REQUIRED_DOCUMENT_TYPES:
        latest = get_latest_document(db, doc_type)
        if latest is None:
            continue
        accepted = (
            db.query(DocumentAcceptance)
            .filter(
                DocumentAcceptance.user_id == auth.user_id,
                DocumentAcceptance.document_id == latest.id,
            )
            .first()
        )
        if accepted is None:
            pending.append(latest)

    return ConsentStatusOut(needs_consent=len(pending) > 0, pending_documents=pending)


@router.post("/accept", status_code=status.HTTP_204_NO_CONTENT)
def accept_document(
    payload: AcceptConsentRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
) -> None:
    document = db.query(LegalDocument).filter(LegalDocument.id == payload.document_id).first()
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    db.add(
        DocumentAcceptance(
            tenant_id=auth.tenant_id, user_id=auth.user_id, document_id=document.id
        )
    )
    db.commit()


@router.get("/{doc_type}", response_model=LegalDocumentOut)
def get_document(doc_type: str, db: Session = Depends(get_db)) -> LegalDocument:
    document = get_latest_document(db, doc_type)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document
