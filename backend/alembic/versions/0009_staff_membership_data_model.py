"""Personel / cok kullanicili tenant uyeligi - sema iskeleti.

"ServisCep Personel / Coklu Kullanici Tasarimi - Mimari Degerlendirme"
gorev ozetinde onerilen modelin SADECE veri katmanini ekliyor:

- `tenant_memberships`: bir kullanicinin bir tenant'taki rolu/durumu -
  "kendi tenant'i" ile "su an calistigi isletme" ayrimini kurar.
- `staff_invitations`: bir tenant'in bir telefon numarasina gonderdigi
  personel davetiyesi.
- `staff_service_assignments`: bir personelin hangi hizmeti (kendi
  fiyat/sure sapmasiyla) verdigi.

Bu migration'la BIRLIKTE gelmeyenler (bir sonraki asamaya birakildi,
bkz. app/models.py'deki bu uc modelin ustundeki blok yorum): mevcut
kayit akislarinin owner icin bir TenantMembership satiri acmasi,
get_current_tenant'in aktif membership'i DB'den dogrulamasi, davet
gonderme/kabul etme endpoint'leri, web/mobil ekranlari.

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenant_memberships",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("staff_member_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_tenant_memberships_user_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_tenant_memberships_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["staff_member_id", "tenant_id"],
            ["staff_members.id", "staff_members.tenant_id"],
            name="fk_tenant_memberships_staff_member_id_tenant_id",
        ),
        sa.CheckConstraint("role IN ('owner', 'staff')", name="ck_tenant_memberships_role"),
        sa.CheckConstraint("status IN ('active', 'left')", name="ck_tenant_memberships_status"),
    )
    op.create_index("ix_tenant_memberships_tenant_id", "tenant_memberships", ["tenant_id"])
    op.create_index("ix_tenant_memberships_user_id", "tenant_memberships", ["user_id"])
    # Bir kullanicinin ayni tenant'ta ayni anda birden fazla AKTIF uyeligi
    # olamaz.
    op.create_index(
        "uq_tenant_memberships_one_active_per_user_tenant",
        "tenant_memberships",
        ["user_id", "tenant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
    )
    # Bir kullanicinin ayni anda (FARKLI tenant'larda bile) birden fazla
    # AKTIF "staff" uyeligi olamaz.
    op.create_index(
        "uq_tenant_memberships_one_active_staff_per_user",
        "tenant_memberships",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("role = 'staff' AND status = 'active'"),
    )

    op.create_table(
        "staff_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("invited_by_user_id", sa.Integer(), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_staff_invitations_tenant_id", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["invited_by_user_id"], ["users.id"], name="fk_staff_invitations_invited_by_user_id"
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="ck_staff_invitations_status",
        ),
    )
    op.create_index("ix_staff_invitations_tenant_id", "staff_invitations", ["tenant_id"])
    op.create_index("ix_staff_invitations_phone", "staff_invitations", ["phone"])
    # Ayni tenant, ayni numaraya birden fazla BEKLEYEN davet gonderemez
    # (once mevcut olani iptal/kabul edilmeli).
    op.create_index(
        "uq_staff_invitations_one_pending_per_tenant_phone",
        "staff_invitations",
        ["tenant_id", "phone"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "staff_service_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("staff_member_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("price_override", sa.Numeric(10, 2), nullable=True),
        sa.Column("duration_override", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_staff_service_assignments_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["staff_member_id", "tenant_id"],
            ["staff_members.id", "staff_members.tenant_id"],
            name="fk_staff_service_assignments_staff_member_id_tenant_id",
        ),
        sa.ForeignKeyConstraint(
            ["service_id", "tenant_id"],
            ["services.id", "services.tenant_id"],
            name="fk_staff_service_assignments_service_id_tenant_id",
        ),
        sa.UniqueConstraint(
            "staff_member_id",
            "service_id",
            name="uq_staff_service_assignments_staff_member_id_service_id",
        ),
    )
    op.create_index(
        "ix_staff_service_assignments_tenant_id", "staff_service_assignments", ["tenant_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_staff_service_assignments_tenant_id", table_name="staff_service_assignments"
    )
    op.drop_table("staff_service_assignments")

    op.drop_index(
        "uq_staff_invitations_one_pending_per_tenant_phone", table_name="staff_invitations"
    )
    op.drop_index("ix_staff_invitations_phone", table_name="staff_invitations")
    op.drop_index("ix_staff_invitations_tenant_id", table_name="staff_invitations")
    op.drop_table("staff_invitations")

    op.drop_index(
        "uq_tenant_memberships_one_active_staff_per_user", table_name="tenant_memberships"
    )
    op.drop_index(
        "uq_tenant_memberships_one_active_per_user_tenant", table_name="tenant_memberships"
    )
    op.drop_index("ix_tenant_memberships_user_id", table_name="tenant_memberships")
    op.drop_index("ix_tenant_memberships_tenant_id", table_name="tenant_memberships")
    op.drop_table("tenant_memberships")
