"""KVKK unutulma hakki - musteri veri silme (anonimlestirme) alanlari.

`customers.deletion_requested_at` / `deleted_at`: ikisi de nullable,
varsayilan NULL (hic silinmemis). Var olan hicbir satiri etkilemez - bu
saf bir sema ekleme migration'i, veri donusumu yok.

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "customers", sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "customers", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("customers", "deleted_at")
    op.drop_column("customers", "deletion_requested_at")
