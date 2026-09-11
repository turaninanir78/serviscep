"""Telefon bazli kayit + OTP dogrulama icin sema degisiklikleri.

- `users.email`: artik NULLABLE (kayit artik SADECE telefonla yapiliyor,
  email sonradan profil ekranindan eklenip dogrulanabilir). Mevcut
  satirlarin hepsinde email zaten dolu oldugu icin bu, veri kaybi olmayan
  saf bir kisitlama gevsetmesi.
- `users.phone`: yeni, nullable, unique - E.164 formatinda (bkz.
  app/phone.py::normalize_phone).
- `ck_users_email_or_phone_present`: en az birinin dolu olmasini garanti
  eder (ikisi de NULL olan bir hesap olusmasin diye).
- `otp_codes`: telefonla kayit ve e-posta dogrulama akislarinin ortak
  dogrulama-kodu tablosu (bkz. app/models.py::OtpCode docstring'i).

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=True)
    op.add_column("users", sa.Column("phone", sa.String(length=20), nullable=True))
    op.create_unique_constraint("uq_users_phone", "users", ["phone"])
    op.create_check_constraint(
        "ck_users_email_or_phone_present", "users", "email IS NOT NULL OR phone IS NOT NULL"
    )

    op.create_table(
        "otp_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_otp_codes_user_id", ondelete="CASCADE"
        ),
    )
    # register_phone/verify-otp ve profile_email/verify-email, "bu
    # purpose+target icin en guncel, henuz tuketilmemis kod" sorgusunu her
    # istek/dogrulamada calistiriyor - bu ikili+created_at siralamasi tam da
    # bu erisim deseni.
    op.create_index("ix_otp_codes_purpose_target", "otp_codes", ["purpose", "target"])


def downgrade() -> None:
    op.drop_index("ix_otp_codes_purpose_target", table_name="otp_codes")
    op.drop_table("otp_codes")
    op.drop_constraint("ck_users_email_or_phone_present", "users", type_="check")
    op.drop_constraint("uq_users_phone", "users", type_="unique")
    op.drop_column("users", "phone")
    op.alter_column("users", "email", existing_type=sa.String(length=255), nullable=False)
