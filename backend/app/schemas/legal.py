from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LegalDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    version: str
    content: str
    effective_date: datetime


class ConsentStatusOut(BaseModel):
    needs_consent: bool
    pending_documents: list[LegalDocumentOut]


class AcceptConsentRequest(BaseModel):
    document_id: int
