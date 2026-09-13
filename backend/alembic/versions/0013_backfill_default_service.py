"""Kayitta otomatik varsayilan hizmet - mevcut tenant'lar icin backfill.

Yeni kayitlar artik register/complete-registration akisinda otomatik
kendi-personel kaydinin (bkz. 0010_backfill_self_staff_member) yaninda
bir de varsayilan Service kaydi aliyor (bkz.
app/api/auth.py::_create_default_service) - randevu olusturmanin hem
bir StaffMember HEM bir Service gerektirmesinden dogan surtunmeyi
kaldirmak icin.

Bu migration, bu degisiklikten ONCE kayit olmus ve HALA hic hizmeti
olmayan tenant'lar icin ayni varsayilan degerlerle ("Genel Hizmet",
30 dk) bir Service satiri ekliyor - saf veri backfill'i, sema
degisikligi yok. Zaten en az bir hizmeti olan tenant'lara DOKUNULMAZ.

Revision ID: 0013
Revises: 0012
Create Date: 2026-09-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# app/api/auth.py::DEFAULT_SERVICE_NAME / DEFAULT_SERVICE_DURATION_MINUTES ile
# AYNI degerler - migration'lar kendi icinde bagimsiz oldugu icin (bkz. diger
# migration'lardaki ayni konvansiyon) buraya da sabit olarak yazildi, app
# kodundan import edilmiyor.
DEFAULT_SERVICE_NAME = "Genel Hizmet"
DEFAULT_SERVICE_DURATION_MINUTES = 30


def upgrade() -> None:
    bind = op.get_bind()
    tenants_without_service = bind.execute(
        sa.text(
            "SELECT t.id FROM tenants t "
            "LEFT JOIN services s ON s.tenant_id = t.id "
            "WHERE s.id IS NULL"
        )
    ).fetchall()

    for row in tenants_without_service:
        bind.execute(
            sa.text(
                "INSERT INTO services (tenant_id, name, duration_minutes, is_active, default_buffer_minutes) "
                "VALUES (:tenant_id, :name, :duration_minutes, true, 0)"
            ),
            {
                "tenant_id": row.id,
                "name": DEFAULT_SERVICE_NAME,
                "duration_minutes": DEFAULT_SERVICE_DURATION_MINUTES,
            },
        )


def downgrade() -> None:
    # Kasitli olarak no-op: bu bir veri backfill'i - hangi Service
    # satirlarinin bu migration tarafindan mi yoksa migration'dan SONRA
    # uygulama tarafindan (ayni varsayilan isimle, bkz.
    # app/api/auth.py::_create_default_service) mi olusturuldugunu
    # guvenilir bicimde ayirt etmenin bir yolu yok - isim eslesmesine
    # dayanarak satir silmek, gercek kullanicilarin "Genel Hizmet" adinda
    # olusturdugu/yeniden adlandirdigi meşru kayitlari da silme riski
    # tasir.
    pass
