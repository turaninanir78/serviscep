"""Add WhatsApp integration: encrypted access token on tenants, and a
conversations table logging inbound/outbound WhatsApp messages.

Note: `tenants.whatsapp_phone_number_id` (nullable, unique) and
`tenants.whatsapp_waba_id` (nullable) already exist from migration 0001 -
reused here rather than duplicated with new columns. Only
`whatsapp_access_token_encrypted` is new on tenants.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column("whatsapp_access_token_encrypted", sa.Text(), nullable=True),
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("direction", sa.String(length=3), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=True),
        sa.Column("wa_message_id", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_conversations_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            name="fk_conversations_customer_id_tenant_id",
        ),
        sa.UniqueConstraint("wa_message_id", name="uq_conversations_wa_message_id"),
        sa.CheckConstraint("direction IN ('in', 'out')", name="ck_conversations_direction"),
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    op.create_index("ix_conversations_customer_id", "conversations", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_conversations_customer_id", table_name="conversations")
    op.drop_index("ix_conversations_tenant_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_column("tenants", "whatsapp_access_token_encrypted")
