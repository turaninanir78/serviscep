"""Enable btree_gist and add an EXCLUDE constraint against overlapping
appointments per staff member.

This is the database-level backstop against the race condition where two
concurrent requests both pass the application-level conflict pre-check
(app/core/availability.has_conflict) before either has committed, and then
both attempt to insert an overlapping appointment. A unique/EXCLUDE
constraint is the only mechanism Postgres offers that is actually checked
atomically against concurrent, not-yet-committed transactions - the
application-level check alone cannot close this window.

`buffer_minutes` is added to appointments (default 0, so existing/typical
behavior is unchanged - [start_at, end_at) with touching boundaries still
allowed) purely so the exclusion range expression has something of its own
to add on top of end_at without needing to look up another table (EXCLUDE
constraints can only reference the row's own columns).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.add_column(
        "appointments",
        sa.Column("buffer_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_appointments_buffer_minutes_nonnegative",
        "appointments",
        "buffer_minutes >= 0",
    )

    # Postgres'in yerlesik tstzrange() kurucusu VE timestamptz + interval
    # toplama operatoru STABLE olarak isaretli, IMMUTABLE degil (ay/gun
    # bilesenli interval'larin oturum saat dilimine bagli olabilecegi genel
    # durum icin temkinli bir siniflandirma) - bu yuzden ikisi de GiST
    # index/EXCLUDE ifadesinde dogrudan kullanilamiyor ("functions in index
    # expression must be marked IMMUTABLE"). Bizim durumumuzda buffer
    # sadece dakika cinsinden oldugu icin bu toplama gercekten saat
    # dilimine bagli degil - toplamayi da icine alan kendi IMMUTABLE
    # fonksiyonumuzu tanimliyoruz (bilinen, guvenli bir workaround).
    op.execute(
        """
        CREATE FUNCTION immutable_appointment_range(timestamptz, timestamptz, integer)
        RETURNS tstzrange AS $$
            SELECT tstzrange($1, $2 + ($3 * interval '1 minute'), '[)');
        $$ LANGUAGE sql IMMUTABLE STRICT
        """
    )

    op.execute(
        """
        ALTER TABLE appointments
        ADD CONSTRAINT excl_appointments_staff_time_overlap
        EXCLUDE USING gist (
            staff_id WITH =,
            immutable_appointment_range(start_at, end_at, buffer_minutes) WITH &&
        )
        WHERE (status <> 'cancelled')
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE appointments DROP CONSTRAINT excl_appointments_staff_time_overlap"
    )
    op.execute(
        "DROP FUNCTION immutable_appointment_range(timestamptz, timestamptz, integer)"
    )
    op.drop_constraint(
        "ck_appointments_buffer_minutes_nonnegative", "appointments", type_="check"
    )
    op.drop_column("appointments", "buffer_minutes")
    # btree_gist extension'i kasitli olarak kaldirmiyoruz - baska nesneler
    # kullaniyor olabilir, DROP EXTENSION burada guvenli degil.
