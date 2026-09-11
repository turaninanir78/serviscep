"""Kayitta otomatik kendi-personel kaydi - mevcut tenant'lar icin backfill.

Yeni kayitlar artik register/complete-registration akisinda otomatik
olarak kendi adina bir StaffMember kaydi aliyor (bkz.
app/api/auth.py::_create_self_staff_member) - randevu olusturmanin bir
StaffMember gerektirmesinden dogan gereksiz surtunmeyi kaldirmak icin.

Bu migration, bu degisiklikten ONCE kayit olmus ve HALA hic personeli
olmayan tenant'lar icin ayni varsayilan isimle ("Ben") bir StaffMember
satiri ekliyor - saf veri backfill'i, sema degisikligi yok.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# app/api/auth.py::DEFAULT_SELF_STAFF_NAME ile AYNI deger - migration'lar
# kendi icinde bagimsiz oldugu icin (bkz. diger migration'lardaki ayni
# konvansiyon) buraya da sabit olarak yazildi, app kodundan import
# edilmiyor.
DEFAULT_SELF_STAFF_NAME = "Ben"


def upgrade() -> None:
    bind = op.get_bind()
    tenants_without_staff = bind.execute(
        sa.text(
            "SELECT t.id FROM tenants t "
            "LEFT JOIN staff_members sm ON sm.tenant_id = t.id "
            "WHERE sm.id IS NULL"
        )
    ).fetchall()

    for row in tenants_without_staff:
        bind.execute(
            sa.text(
                "INSERT INTO staff_members (tenant_id, name, is_active) "
                "VALUES (:tenant_id, :name, true)"
            ),
            {"tenant_id": row.id, "name": DEFAULT_SELF_STAFF_NAME},
        )


def downgrade() -> None:
    # Kasitli olarak no-op: bu bir veri backfill'i - hangi StaffMember
    # satirlarinin bu migration tarafindan mi yoksa migration'dan SONRA
    # uygulama tarafindan (ayni varsayilan isimle, bkz.
    # app/api/auth.py::_create_self_staff_member) mi olusturuldugunu
    # guvenilir bicimde ayirt etmenin bir yolu yok - isim eslesmesine
    # dayanarak satir silmek, gercek kullanicilarin "Ben" adinda
    # olusturdugu/yeniden adlandirdigi meşru kayitlari da silme riski
    # tasir.
    pass
