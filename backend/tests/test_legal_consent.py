"""Sozlesme/onay (KVKK) altyapisi testleri.

Onay verilmeden kaydin tamamlanamadigini, onay verilince dogru
DocumentAcceptance kayitlarinin olustugunu, ve bir dokuman yeni bir
versiyona guncellendiginde eski onayin gecersiz sayildigini (needs_consent)
dogrular. Diger testlerle ayni yaklasim: calisan sunucuya gercek HTTP
istekleri, DB temizligi manuel.
"""
import random
import string
import uuid
from datetime import datetime, timezone

import requests

from app.db import SessionLocal
from app.models import DocumentAcceptance, LegalDocument, Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _unique_email() -> str:
    return f"legal-consent-test-{uuid.uuid4().hex}@example.com"


def _get_registration_token(phone_raw: str) -> str:
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
    return verify_res.json()["registration_token"]


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


def _cleanup_by_email(email: str) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
            db.commit()
    finally:
        db.close()


def test_get_latest_legal_document_returns_placeholder_seed():
    res = requests.get(f"{BASE_URL}/legal/terms_of_service")
    assert res.status_code == 200
    body = res.json()
    assert body["type"] == "terms_of_service"
    assert "PLACEHOLDER" in body["content"]


def test_unknown_document_type_returns_404():
    res = requests.get(f"{BASE_URL}/legal/not-a-real-document-type")
    assert res.status_code == 404


def test_register_complete_without_accepted_terms_is_rejected_and_creates_no_account():
    phone_raw = _random_phone_raw()
    try:
        token = _get_registration_token(phone_raw)
        res = requests.post(
            f"{BASE_URL}/auth/register/complete",
            json={
                "registration_token": token,
                "tenant_name": "No Consent Tenant",
                "password": "s3cret-pw",
                "accepted_terms": False,
            },
        )
        assert res.status_code == 400

        normalized = normalize_phone(COUNTRY_CODE, phone_raw)
        db = SessionLocal()
        try:
            assert db.query(User).filter(User.phone == normalized).first() is None
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)


def test_old_register_endpoint_also_requires_accepted_terms():
    email = _unique_email()
    try:
        res = requests.post(
            f"{BASE_URL}/auth/register",
            json={
                "tenant_name": "Old Flow No Consent",
                "email": email,
                "password": "s3cret-pw",
                "accepted_terms": False,
            },
        )
        assert res.status_code == 400
    finally:
        _cleanup_by_email(email)


def test_register_complete_with_accepted_terms_records_consent_for_both_required_documents():
    phone_raw = _random_phone_raw()
    try:
        token = _get_registration_token(phone_raw)
        res = requests.post(
            f"{BASE_URL}/auth/register/complete",
            json={
                "registration_token": token,
                "tenant_name": "Consent Tenant",
                "password": "s3cret-pw",
                "accepted_terms": True,
            },
        )
        assert res.status_code == 201

        normalized = normalize_phone(COUNTRY_CODE, phone_raw)
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.phone == normalized).first()
            assert user is not None
            acceptances = (
                db.query(DocumentAcceptance).filter(DocumentAcceptance.user_id == user.id).all()
            )
            accepted_types = {
                db.query(LegalDocument).filter(LegalDocument.id == a.document_id).first().type
                for a in acceptances
            }
            assert accepted_types == {"terms_of_service", "privacy_notice"}
        finally:
            db.close()
    finally:
        _cleanup_by_phone(phone_raw)


def test_consent_status_requires_authentication():
    res = requests.get(f"{BASE_URL}/legal/consent-status")
    assert res.status_code == 401


def test_new_document_version_makes_existing_acceptance_stale_until_reaccepted():
    phone_raw = _random_phone_raw()
    new_doc_id = None
    try:
        token = _get_registration_token(phone_raw)
        session = requests.Session()
        complete_res = session.post(
            f"{BASE_URL}/auth/register/complete",
            json={
                "registration_token": token,
                "tenant_name": "Reconsent Tenant",
                "password": "s3cret-pw",
                "accepted_terms": True,
            },
        )
        assert complete_res.status_code == 201

        status_res = session.get(f"{BASE_URL}/legal/consent-status")
        assert status_res.status_code == 200
        assert status_res.json()["needs_consent"] is False

        # Yeni bir versiyon "yayinla" - gercekte bir admin araciyla
        # yapilir, burada dogrudan DB'ye eklenerek simule ediliyor.
        db = SessionLocal()
        try:
            new_doc = LegalDocument(
                type="terms_of_service",
                version="v2-test",
                content="PLACEHOLDER v2",
                effective_date=datetime.now(timezone.utc),
            )
            db.add(new_doc)
            db.commit()
            db.refresh(new_doc)
            new_doc_id = new_doc.id
        finally:
            db.close()

        status_res_2 = session.get(f"{BASE_URL}/legal/consent-status")
        assert status_res_2.status_code == 200
        body = status_res_2.json()
        assert body["needs_consent"] is True
        assert any(d["id"] == new_doc_id for d in body["pending_documents"])

        accept_res = session.post(f"{BASE_URL}/legal/accept", json={"document_id": new_doc_id})
        assert accept_res.status_code == 204

        status_res_3 = session.get(f"{BASE_URL}/legal/consent-status")
        assert status_res_3.json()["needs_consent"] is False
    finally:
        _cleanup_by_phone(phone_raw)
        if new_doc_id is not None:
            db = SessionLocal()
            try:
                db.query(DocumentAcceptance).filter(
                    DocumentAcceptance.document_id == new_doc_id
                ).delete()
                db.query(LegalDocument).filter(LegalDocument.id == new_doc_id).delete()
                db.commit()
            finally:
                db.close()
