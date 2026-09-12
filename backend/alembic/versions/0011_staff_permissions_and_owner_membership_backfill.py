"""Personel yetkileri + mevcut kullanicilar icin owner membership backfill.

Iki bagimsiz degisiklik:
1. `tenant_memberships`'e 6 boolean yetki sutunu ekliyor - SADECE
   role="staff" satirlari icin anlamli (bkz. app/permissions.py). Owner
   satirlari icin degerleri onemsiz (owner her zaman tam yetkili).
2. Bu tabloyu ekleyen migration'dan (0009) ONCE kayit olmus kullanicilar
   icin hic TenantMembership satiri yok - her User icin kendi tenant'inda
   bir role="owner" satiri acan bir backfill (0010'daki self-staff-member
   backfill'iyle AYNI desen: raw SQL, saf veri, sema degisikligi yok).
   Yeni kayitlar artik register akisinda otomatik bu satiri aliyor (bkz.
   app/api/auth.py::_create_owner_membership).

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PERMISSION_COLUMNS = (
    "can_view_customers",
    "can_create_appointments",
    "can_cancel_appointments",
    "can_confirm_complete_appointments",
    "can_manage_availability",
    "can_manage_services",
)


def upgrade() -> None:
    for column_name in PERMISSION_COLUMNS:
        op.add_column(
            "tenant_memberships",
            sa.Column(column_name, sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )

    bind = op.get_bind()
    users_without_owner_membership = bind.execute(
        sa.text(
            "SELECT u.id AS user_id, u.tenant_id AS tenant_id FROM users u "
            "LEFT JOIN tenant_memberships tm "
            "ON tm.user_id = u.id AND tm.tenant_id = u.tenant_id AND tm.status = 'active' "
            "WHERE tm.id IS NULL"
        )
    ).fetchall()

    for row in users_without_owner_membership:
        bind.execute(
            sa.text(
                "INSERT INTO tenant_memberships (user_id, tenant_id, role, status) "
                "VALUES (:user_id, :tenant_id, 'owner', 'active')"
            ),
            {"user_id": row.user_id, "tenant_id": row.tenant_id},
        )


def downgrade() -> None:
    for column_name in reversed(PERMISSION_COLUMNS):
        op.drop_column("tenant_memberships", column_name)
    # Backfill edilen owner satirlari kasitli olarak SILINMIYOR (bkz.
    # migration 0010'daki ayni gerekce - hangi satirlarin bu migration
    # tarafindan mi yoksa sonradan uygulama tarafindan mi eklendigini
    # guvenilir bicimde ayirt etmenin bir yolu yok).
