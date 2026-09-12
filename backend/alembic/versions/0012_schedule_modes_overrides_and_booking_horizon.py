"""Calisma Plani: standart/esnek randevu modu + tarihe ozel istisna +
randevu acik kalma suresi.

Uc bagimsiz degisiklik:
1. `availability_rules`'a mode/slot_duration_minutes/gap_minutes ekliyor -
   mode="standard" olan gunlerde slot suresi secilen hizmetten degil, bu
   sabit degerlerden gelir (bkz. gorev ozeti - klinik/berber ornegi).
   Varsayilan mode="flexible" ile MEVCUT davranis (hizmet suresine gore
   esnek slot hesaplama) hicbir mevcut kural icin DEGISMEZ.
2. `availability_overrides`: haftalik sablonu BOZMADAN belirli bir tarihe
   ozel gecici degisiklik - "bunu kalici yap" onaylanirsa ayni degerlerle
   haftalik sablon (yeni bir AvailabilityRule) da ayrica olusturulur (bkz.
   app/api/availability_overrides.py), bu satirin kendisi degismez.
3. `tenants.max_advance_booking_days`: randevularin en fazla kac gun
   ileriye acilabilecegi - NULL varsayilan (sinirsiz), MEVCUT tum
   tenant'lar icin davranis degismez.

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "availability_rules",
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="flexible"),
    )
    op.add_column(
        "availability_rules", sa.Column("slot_duration_minutes", sa.Integer(), nullable=True)
    )
    op.add_column(
        "availability_rules",
        sa.Column("gap_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_availability_rules_mode",
        "availability_rules",
        "mode IN ('flexible', 'standard')",
    )

    op.create_table(
        "availability_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False, server_default="flexible"),
        sa.Column("slot_duration_minutes", sa.Integer(), nullable=True),
        sa.Column("gap_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_availability_overrides_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["staff_id", "tenant_id"],
            ["staff_members.id", "staff_members.tenant_id"],
            name="fk_availability_overrides_staff_id_tenant_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "mode IN ('flexible', 'standard')", name="ck_availability_overrides_mode"
        ),
    )
    op.create_index(
        "ix_availability_overrides_staff_id_date",
        "availability_overrides",
        ["staff_id", "date"],
    )

    op.add_column(
        "tenants", sa.Column("max_advance_booking_days", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("tenants", "max_advance_booking_days")

    op.drop_index("ix_availability_overrides_staff_id_date", table_name="availability_overrides")
    op.drop_table("availability_overrides")

    op.drop_constraint("ck_availability_rules_mode", "availability_rules", type_="check")
    op.drop_column("availability_rules", "gap_minutes")
    op.drop_column("availability_rules", "slot_duration_minutes")
    op.drop_column("availability_rules", "mode")
