"""Musteri PII sifreleme (encryption at rest) + KVKK sozlesme/onay
altyapisi + basit erisim denetim izi.

--- Musteri sifreleme ---

`customers.whatsapp_number` ve `customers.display_name` artik DB'de
Fernet ile sifreli saklaniyor (bkz. app/db_types.py::EncryptedString) -
uygulama katmani icin SEFFAF (ORM seviyesinde hala duz metin okunup
yazilir). Bu migration VAR OLAN satirlari YERINDE sifreliyor
(encrypt-in-place): her satirin o anki duz metin degerini okuyup ayni
PII_ENCRYPTION_KEY ile sifreliyor ve UPDATE ediyor - veri kaybi olmaz,
sadece saklama formati degisir.

Fernet KASITLI OLARAK non-deterministik oldugu icin (ayni girdi her
seferinde farkli ciphertext) eski `uq_customers_tenant_id_whatsapp_number`
(duz metin uzerinde) kisitlamasi artik hicbir seyi engellemez - onun
yerine deterministik bir HMAC-SHA256 hash'i tasiyan yeni
`whatsapp_number_hash` sutunu uzerinde `uq_customers_tenant_id_whatsapp_number_hash`
kisitlamasi kuruluyor (hem tekillik hem esitlik-arama icin, bkz.
app/crypto.py::hash_pii_lookup).

Bu dosya, tutarlilik icin app/crypto.py'yi IMPORT ETMIYOR - diger tum
migration'lar gibi kendi icinde bagimsiz (gelecekte app/crypto.py'nin
API'si degisse bile bu migration'in GECMISTE calistigi haliyle okunabilir/
tekrar calistirilabilir kalmasi icin).

--- KVKK sozlesme/onay ---

`legal_documents`: versiyonlanmis hukuki metin (content SU AN SADECE yer
tutucu). `document_acceptances`: kim, hangi versiyonu, ne zaman kabul
etti. Asagida her ZORUNLU tur (terms_of_service, privacy_notice) icin
bir v1 placeholder satiri seed ediliyor - bunlar olmadan kayit akisi
onay kaydi olusturamaz (bkz. app/legal.py::record_registration_consent -
dokuman yoksa sessizce atlar, kaydi kilitlemez, ama gercek kullanimda
en azindan bir placeholder olmasi beklenir).

--- Erisim denetim izi ---

`access_logs`: hangi kullanicinin hangi tekil kayda (musteri/randevu) ne
zaman eristigi - bkz. app/access_log.py::log_access.

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-11

"""
import hashlib
import hmac
import os
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from cryptography.fernet import Fernet

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _pii_fernet() -> Fernet:
    return Fernet(os.environ["PII_ENCRYPTION_KEY"].encode())


def _hash_lookup(plaintext: str) -> str:
    key = os.environ["PII_ENCRYPTION_KEY"].encode()
    return hmac.new(key, plaintext.encode(), hashlib.sha256).hexdigest()


def upgrade() -> None:
    # --- Erisim denetim izi ---
    op.create_table(
        "access_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("resource_type", sa.String(length=30), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_access_logs_tenant_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_access_logs_user_id", ondelete="SET NULL"
        ),
    )
    op.create_index("ix_access_logs_tenant_id", "access_logs", ["tenant_id"])
    op.create_index(
        "ix_access_logs_resource_type_resource_id", "access_logs", ["resource_type", "resource_id"]
    )

    # --- KVKK sozlesme/onay ---
    op.create_table(
        "legal_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("type", "version", name="uq_legal_documents_type_version"),
    )

    op.create_table(
        "document_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_document_acceptances_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_document_acceptances_user_id", ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["legal_documents.id"],
            name="fk_document_acceptances_document_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_document_acceptances_user_id", "document_acceptances", ["user_id"])

    # Zorunlu dokuman turleri icin yer tutucu v1 - GERCEK metni eklerken
    # bu tabloya (type'i ayni, version'u "v2", effective_date'i ileri bir
    # tarih olan) YENI bir satir eklenir; bu iki satir DEGISTIRILMEZ.
    op.execute(
        sa.text(
            "INSERT INTO legal_documents (type, version, content, effective_date) "
            "VALUES (:type, :version, :content, now())"
        ).bindparams(
            type="terms_of_service",
            version="v1",
            content="PLACEHOLDER - gercek metin eklenecek",
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO legal_documents (type, version, content, effective_date) "
            "VALUES (:type, :version, :content, now())"
        ).bindparams(
            type="privacy_notice",
            version="v1",
            content="PLACEHOLDER - gercek metin eklenecek",
        )
    )

    # --- Musteri PII sifreleme (encrypt-in-place) ---
    op.alter_column(
        "customers", "whatsapp_number", existing_type=sa.String(length=32), type_=sa.Text()
    )
    op.alter_column(
        "customers", "display_name", existing_type=sa.String(length=255), type_=sa.Text()
    )
    op.add_column("customers", sa.Column("whatsapp_number_hash", sa.String(length=64), nullable=True))

    bind = op.get_bind()
    fernet = _pii_fernet()
    rows = bind.execute(sa.text("SELECT id, whatsapp_number, display_name FROM customers")).fetchall()
    for row in rows:
        encrypted_number = fernet.encrypt(row.whatsapp_number.encode()).decode()
        number_hash = _hash_lookup(row.whatsapp_number)
        encrypted_name = (
            fernet.encrypt(row.display_name.encode()).decode()
            if row.display_name is not None
            else None
        )
        bind.execute(
            sa.text(
                "UPDATE customers SET whatsapp_number = :number, whatsapp_number_hash = :hash, "
                "display_name = :name WHERE id = :id"
            ),
            {
                "number": encrypted_number,
                "hash": number_hash,
                "name": encrypted_name,
                "id": row.id,
            },
        )

    op.alter_column("customers", "whatsapp_number_hash", nullable=False)
    op.drop_constraint(
        "uq_customers_tenant_id_whatsapp_number", "customers", type_="unique"
    )
    op.create_unique_constraint(
        "uq_customers_tenant_id_whatsapp_number_hash",
        "customers",
        ["tenant_id", "whatsapp_number_hash"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    fernet = _pii_fernet()
    rows = bind.execute(sa.text("SELECT id, whatsapp_number, display_name FROM customers")).fetchall()
    for row in rows:
        decrypted_number = fernet.decrypt(row.whatsapp_number.encode()).decode()
        decrypted_name = (
            fernet.decrypt(row.display_name.encode()).decode()
            if row.display_name is not None
            else None
        )
        bind.execute(
            sa.text("UPDATE customers SET whatsapp_number = :number, display_name = :name WHERE id = :id"),
            {"number": decrypted_number, "name": decrypted_name, "id": row.id},
        )

    op.drop_constraint(
        "uq_customers_tenant_id_whatsapp_number_hash", "customers", type_="unique"
    )
    op.create_unique_constraint(
        "uq_customers_tenant_id_whatsapp_number", "customers", ["tenant_id", "whatsapp_number"]
    )
    op.drop_column("customers", "whatsapp_number_hash")
    op.alter_column(
        "customers", "display_name", existing_type=sa.Text(), type_=sa.String(length=255)
    )
    op.alter_column(
        "customers", "whatsapp_number", existing_type=sa.Text(), type_=sa.String(length=32)
    )

    op.drop_index("ix_document_acceptances_user_id", table_name="document_acceptances")
    op.drop_table("document_acceptances")
    op.drop_table("legal_documents")

    op.drop_index("ix_access_logs_resource_type_resource_id", table_name="access_logs")
    op.drop_index("ix_access_logs_tenant_id", table_name="access_logs")
    op.drop_table("access_logs")
