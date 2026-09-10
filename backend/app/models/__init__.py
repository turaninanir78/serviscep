from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)

from app.db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    whatsapp_phone_number_id = Column(String(64))
    whatsapp_waba_id = Column(String(64))
    whatsapp_access_token_encrypted = Column(Text)
    plan_type = Column(String(20), nullable=False, server_default="classic")
    timezone = Column(String(64), nullable=False, server_default="Europe/Istanbul")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "email IS NOT NULL OR phone IS NOT NULL", name="ck_users_email_or_phone_present"
        ),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    # Ikisi de nullable: kayit artik SADECE telefonla yapiliyor (email NULL
    # baslar), email sonradan profil ekranindan dogrulanip eklenebilir. Eski
    # (migration 0006 ONCESI) hesaplarin hepsinde email dolu, phone NULL -
    # CHECK constraint sadece "en az biri dolu olsun" der, ikisi de nullable
    # oldugu icin Postgres UNIQUE semantigi geregi (NULL'lar birbirinden
    # farkli sayilir) ayni anda birden fazla NULL email/phone sorun cikarmaz.
    email = Column(String(255), unique=True)
    phone = Column(String(20), unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OtpCode(Base):
    """Telefonla kayit (purpose="register_phone") ve profile e-posta ekleme
    (purpose="profile_email") akislarinin ortak dogrulama-kodu tablosu.

    `target`, dogrulanan sey (normalize edilmis E.164 telefon ya da e-posta)
    - kod, gercek deger yerine hash'i olarak saklaniyor (app/security.py
    hash_password/verify_password ile, sifrelerle ayni bcrypt mekanizmasi).
    `user_id`, sadece profile_email icin doludur (hangi giris yapmis
    kullanicinin istegi oldugunu dogrulamak icin) - register_phone icin NULL
    (henuz bir User/Tenant yok).
    """

    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True)
    purpose = Column(String(30), nullable=False)
    target = Column(String(255), nullable=False)
    code_hash = Column(String(255), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    attempts = Column(Integer, nullable=False, server_default="0")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_customers_id_tenant_id"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    whatsapp_number = Column(String(32), nullable=False)
    display_name = Column(String(255))
    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StaffMember(Base):
    __tablename__ = "staff_members"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_staff_members_id_tenant_id"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, server_default="true")


class Service(Base):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_services_id_tenant_id"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    name = Column(String(255), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    price = Column(Numeric(10, 2))
    is_active = Column(Boolean, nullable=False, server_default="true")
    default_buffer_minutes = Column(Integer, nullable=False, server_default="0")


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"
    __table_args__ = (
        ForeignKeyConstraint(
            ["staff_id", "tenant_id"],
            ["staff_members.id", "staff_members.tenant_id"],
            name="fk_availability_rules_staff_id_tenant_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    staff_id = Column(Integer, nullable=False)
    weekday = Column(SmallInteger, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            name="fk_appointments_customer_id_tenant_id",
        ),
        ForeignKeyConstraint(
            ["service_id", "tenant_id"],
            ["services.id", "services.tenant_id"],
            name="fk_appointments_service_id_tenant_id",
        ),
        ForeignKeyConstraint(
            ["staff_id", "tenant_id"],
            ["staff_members.id", "staff_members.tenant_id"],
            name="fk_appointments_staff_id_tenant_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    customer_id = Column(Integer, nullable=False)
    service_id = Column(Integer, nullable=False)
    staff_id = Column(Integer, nullable=False)
    start_at = Column(DateTime(timezone=True), nullable=False)
    end_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(20), nullable=False, server_default="pending")
    created_via = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    buffer_minutes = Column(Integer, nullable=False, server_default="0")


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["customer_id", "tenant_id"],
            ["customers.id", "customers.tenant_id"],
            name="fk_conversations_customer_id_tenant_id",
        ),
        CheckConstraint("direction IN ('in', 'out')", name="ck_conversations_direction"),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    customer_id = Column(Integer, nullable=True)
    direction = Column(String(3), nullable=False)
    message_text = Column(Text)
    wa_message_id = Column(String(255), unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
