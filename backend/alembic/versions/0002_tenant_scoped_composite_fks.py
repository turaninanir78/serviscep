"""Tenant-scoped composite FKs and data integrity checks

Adds (id, tenant_id) unique constraints to customers, services, and
staff_members so that appointments and availability_rules can reference
them through a composite foreign key that includes tenant_id. This makes
it impossible, at the database level, for an appointment or availability
rule to point at a customer/service/staff member belonging to a
different tenant than the appointment/rule itself.

Also adds CHECK constraints for basic data sanity (time ordering,
positive duration, non-negative price) that were not enforced in 0001.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. (id, tenant_id) unique constraints - required as the target of
    # the composite foreign keys added below.
    op.create_unique_constraint(
        "uq_customers_id_tenant_id", "customers", ["id", "tenant_id"]
    )
    op.create_unique_constraint(
        "uq_services_id_tenant_id", "services", ["id", "tenant_id"]
    )
    op.create_unique_constraint(
        "uq_staff_members_id_tenant_id", "staff_members", ["id", "tenant_id"]
    )

    # 2. appointments: replace single-column FKs with tenant-scoped
    # composite FKs.
    op.drop_constraint("fk_appointments_customer_id", "appointments", type_="foreignkey")
    op.drop_constraint("fk_appointments_service_id", "appointments", type_="foreignkey")
    op.drop_constraint("fk_appointments_staff_id", "appointments", type_="foreignkey")

    op.create_foreign_key(
        "fk_appointments_customer_id_tenant_id",
        "appointments",
        "customers",
        ["customer_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_appointments_service_id_tenant_id",
        "appointments",
        "services",
        ["service_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_appointments_staff_id_tenant_id",
        "appointments",
        "staff_members",
        ["staff_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="RESTRICT",
    )

    # 3. availability_rules: same composite-FK fix for staff_id.
    op.drop_constraint(
        "fk_availability_rules_staff_id", "availability_rules", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_availability_rules_staff_id_tenant_id",
        "availability_rules",
        "staff_members",
        ["staff_id", "tenant_id"],
        ["id", "tenant_id"],
        ondelete="CASCADE",
    )

    # 4-6. Data sanity CHECK constraints.
    op.create_check_constraint(
        "ck_availability_rules_time_order",
        "availability_rules",
        "start_time < end_time",
    )
    op.create_check_constraint(
        "ck_appointments_time_order", "appointments", "start_at < end_at"
    )
    op.create_check_constraint(
        "ck_services_duration_positive", "services", "duration_minutes > 0"
    )
    op.create_check_constraint(
        "ck_services_price_nonnegative", "services", "price >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_services_price_nonnegative", "services", type_="check")
    op.drop_constraint("ck_services_duration_positive", "services", type_="check")
    op.drop_constraint("ck_appointments_time_order", "appointments", type_="check")
    op.drop_constraint(
        "ck_availability_rules_time_order", "availability_rules", type_="check"
    )

    op.drop_constraint(
        "fk_availability_rules_staff_id_tenant_id",
        "availability_rules",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_availability_rules_staff_id",
        "availability_rules",
        "staff_members",
        ["staff_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.drop_constraint(
        "fk_appointments_staff_id_tenant_id", "appointments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_appointments_service_id_tenant_id", "appointments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_appointments_customer_id_tenant_id", "appointments", type_="foreignkey"
    )

    op.create_foreign_key(
        "fk_appointments_staff_id",
        "appointments",
        "staff_members",
        ["staff_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_appointments_service_id",
        "appointments",
        "services",
        ["service_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_appointments_customer_id",
        "appointments",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.drop_constraint("uq_staff_members_id_tenant_id", "staff_members", type_="unique")
    op.drop_constraint("uq_services_id_tenant_id", "services", type_="unique")
    op.drop_constraint("uq_customers_id_tenant_id", "customers", type_="unique")
