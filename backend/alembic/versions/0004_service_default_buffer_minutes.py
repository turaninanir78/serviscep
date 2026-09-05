"""Add services.default_buffer_minutes.

Per-service default cleanup/gap buffer (minutes) applied after an
appointment for that service unless overridden per-booking on
appointments.buffer_minutes (already added in migration 0003).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "services",
        sa.Column(
            "default_buffer_minutes", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.create_check_constraint(
        "ck_services_default_buffer_minutes_nonnegative",
        "services",
        "default_buffer_minutes >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_services_default_buffer_minutes_nonnegative", "services", type_="check"
    )
    op.drop_column("services", "default_buffer_minutes")
