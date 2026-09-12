from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    event,
    func,
    text,
)

from app.crypto import hash_pii_lookup
from app.db import Base
from app.db_types import EncryptedString


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
    """`whatsapp_number` ve `display_name` KVKK kapsaminda hassas veri
    sayildigi icin DB'de sifreli saklanir (bkz. app/db_types.py::EncryptedString)
    - uygulama kodu icin SEFFAF (bu iki alan hala normal Python string'i gibi
    okunup yazilir, API yanitlari duz metin doner).

    Fernet sifrelemesi non-deterministik oldugu icin `whatsapp_number`
    uzerinde DOGRUDAN esitlik sorgusu calismaz - bunun yerine
    `whatsapp_number_hash` (deterministik HMAC, bkz. app/crypto.py::hash_pii_lookup)
    kullanilir; bu alan hem arama/lookup (orn. gelen WhatsApp mesajini
    mevcut musteriyle eslestirme, bkz. app/api/webhooks.py) hem de
    tenant-basina tekillik kisitlamasi (asagidaki UniqueConstraint) icin
    kullanilir. `_sync_customer_whatsapp_number_hash` event listener'i bu
    alani `whatsapp_number` her degistiginde otomatik senkronize eder - cagiran
    kodun hash'i elle hesaplamasina gerek yoktur.
    """

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_customers_id_tenant_id"),
        UniqueConstraint(
            "tenant_id",
            "whatsapp_number_hash",
            name="uq_customers_tenant_id_whatsapp_number_hash",
        ),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    whatsapp_number = Column(EncryptedString, nullable=False)
    whatsapp_number_hash = Column(String(64), nullable=False)
    display_name = Column(EncryptedString)
    first_seen_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # KVKK unutulma hakki (bkz. app/api/customers.py::request_customer_deletion) -
    # ikisi de NULL: hic silinmemis. deletion_requested_at, tenant'in "Veriyi
    # Sil" aksiyonunu tetikledigi an; deleted_at, anonimlestirmenin
    # GERCEKTEN tamamlandigi an. Su an ikisi ayni istekte, ayni anda
    # yaziliyor (islem senkron/geri alinamaz) - ayri tutulmalari, ileride
    # "once talep, sonra onay/isle" gibi iki adimli bir surece gecilirse
    # sema degisikligi gerektirmemesi icin.
    deletion_requested_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


@event.listens_for(Customer, "before_insert")
@event.listens_for(Customer, "before_update")
def _sync_customer_whatsapp_number_hash(mapper, connection, target: Customer) -> None:
    target.whatsapp_number_hash = hash_pii_lookup(target.whatsapp_number)


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


class AccessLog(Base):
    """Kim (tenant_id+user_id), hangi kayda (resource_type+resource_id),
    ne zaman, hangi islemle eristi - basit bir denetim izi (KVKK'nin
    hesap verebilirlik/izlenebilirlik gerekliligi icin). Ayrintili bir
    analiz araci degil; sadece GET/PATCH/DELETE gibi tekil-kayit
    erisimlerinde app/access_log.py::log_access ile yaziliyor."""

    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    resource_type = Column(String(30), nullable=False)
    resource_id = Column(Integer, nullable=False)
    action = Column(String(10), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class LegalDocument(Base):
    """Versiyonlanmis hukuki metin (aydinlatma metni, kullanim sartlari,
    veri isleme sozlesmesi...). `content` bu gorevde SADECE yer tutucu
    metin icerir - gercek metin eklenirken kod DEGISMEZ, sadece bu tabloya
    (`type`'i ayni, `version`'u bir sonraki, `effective_date`'i bugun/ileri
    bir tarih olan) YENI bir satir eklenir. Ayni turun ayni versiyonunu iki
    kez eklemeyi engellemek disinda gecmis versiyonlar hicbir zaman
    silinmez/degistirilmez (bkz. DocumentAcceptance - hangi kullanicinin
    hangi versiyonu onayladigi kaliciligina dayanir)."""

    __tablename__ = "legal_documents"
    __table_args__ = (
        UniqueConstraint("type", "version", name="uq_legal_documents_type_version"),
    )

    id = Column(Integer, primary_key=True)
    type = Column(String(50), nullable=False)
    version = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    effective_date = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class DocumentAcceptance(Base):
    """Bir LegalDocument versiyonunun kabul edildigi kaydi. `user_id`
    nullable: bazi onaylar (ileride) sadece tenant seviyesinde
    tutulabilir; kayit akisindaki onaylar hem tenant_id hem user_id
    doludur (bkz. app/legal.py::record_registration_consent)."""

    __tablename__ = "document_acceptances"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    document_id = Column(Integer, ForeignKey("legal_documents.id"), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ip_address = Column(String(45), nullable=True)


# --- Personel / cok kullanicili tenant uyeligi ---
#
# Asagidaki uc model, "ServisCep Personel / Coklu Kullanici Tasarimi -
# Mimari Degerlendirme" gorev ozetindeki onerilen modeli uyguluyor.
# Once (migration 0009) sadece sema eklenmisti; auth/JWT akisi
# (app/security.py::get_current_tenant, aktif membership'i DB'den
# cozumluyor), davet gonderme/kabul etme (app/api/staff_invitations.py)
# ve yetki kontrolleri (app/permissions.py) sonradan devreye alindi.
# Mevcut User.tenant_id hala "kisinin KENDI tenant'i" anlaminda duruyor
# (owner membership'i her zaman buna karsilik gelir) - aktif calisma
# baglami (su an hangi isletme altinda calisiyor) artik BUNDAN degil,
# TenantMembership'ten okunuyor.


class TenantMembership(Base):
    """Bir kullanicinin bir tenant'taki ROLU ve DURUMU - "hangi tenant'a
    aitim" bilgisi artik User/Tenant uzerine degil, buraya kuruluyor.
    Boylece bir kisinin KENDI tenant'i (owner oldugu, verinin kalici
    sahibi) ile SU AN calistigi isletme (staff oldugu) birbirinden
    ayrisiyor; tenant'in kendisine bir role veya parent_tenant_id
    yuklenmiyor (bkz. gorev ozetindeki mimari gerekce).

    `staff_member_id`: SADECE role="staff" icin doludur - hangi
    StaffMember (randevu kaynagi) kaydina karsilik geldigini gosterir.
    Composite FK (staff_member_id, tenant_id) sayesinde baglanti
    KESINLIKLE ayni tenant'a ait bir StaffMember'a kurulabilir; nullable
    oldugu icin owner kayitlarinda (staff_member_id NULL) Postgres'in
    varsayilan MATCH SIMPLE davranisiyla FK kontrolu devre disi kalir.

    `status`: "active" (su an gecerli) / "left" (ayrilmis - kayit
    SILINMEZ, gecmis/rapor butunlugu icin DB'de kalir, bkz. gorev
    ozeti). Asagidaki iki kismi (partial) unique index, gorev
    ozetindeki iki kurali DB seviyesinde garanti eder:
      1. Bir kullanicinin ayni tenant'ta ayni anda birden fazla AKTIF
         uyeligi olamaz.
      2. Bir kullanicinin ayni anda (FARKLI tenant'larda bile) birden
         fazla AKTIF "staff" uyeligi olamaz.

    Yetki sutunlari (can_*) SADECE role="staff" satirlari icin anlamli -
    owner her zaman tam yetkilidir, bu sutunlara hic bakilmaz (bkz.
    app/permissions.py::require_permission). Granularlik, gorev
    ozetindeki "her isletmeye uyabilecek esneklik" gerekcesiyle
    (klinikte hekim sadece gorsun, berberde personel her seyi yonetsin)
    BILEREK sabit bir "staff" rolu yerine isletme sahibinin her personel
    icin AYRI AYRI acip kapatabilecegi anahtarlar olarak tasarlandi.
    """

    __tablename__ = "tenant_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["staff_member_id", "tenant_id"],
            ["staff_members.id", "staff_members.tenant_id"],
            name="fk_tenant_memberships_staff_member_id_tenant_id",
        ),
        CheckConstraint("role IN ('owner', 'staff')", name="ck_tenant_memberships_role"),
        CheckConstraint("status IN ('active', 'left')", name="ck_tenant_memberships_status"),
        Index(
            "uq_tenant_memberships_one_active_per_user_tenant",
            "user_id",
            "tenant_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index(
            "uq_tenant_memberships_one_active_staff_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("role = 'staff' AND status = 'active'"),
        ),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    staff_member_id = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, server_default="active")
    joined_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    left_at = Column(DateTime(timezone=True), nullable=True)
    can_view_customers = Column(Boolean, nullable=False, server_default="false")
    can_create_appointments = Column(Boolean, nullable=False, server_default="false")
    can_cancel_appointments = Column(Boolean, nullable=False, server_default="false")
    can_confirm_complete_appointments = Column(Boolean, nullable=False, server_default="false")
    can_manage_availability = Column(Boolean, nullable=False, server_default="false")
    can_manage_services = Column(Boolean, nullable=False, server_default="false")


class StaffInvitation(Base):
    """Bir tenant'in bir telefon numarasina gonderdigi personel (staff)
    davetiyesi. Kabul/red, davet edilen kisinin KENDI (zaten telefon+OTP
    ile dogrulanmis) hesabiyla giris yapip bu numarayla eslesen bekleyen
    davetleri gorup onaylamasiyla olur (bkz. app/api/staff_invitations.py)
    - kayit sirasinda zaten yapilmis OTP dogrulamasinin USTUNE ayrica bir
    OTP istenmiyor (gorev ozeti: "zaten uye olup otp dogrulamasi yaptigi
    icin ayrica bir dogrulamaya gerek yok"). `token_hash` bu yuzden
    kabul akisinda KULLANILMIYOR - ileride e-posta/SMS uzerinden dogrudan
    tiklanabilir bir davet linki eklenirse (kisi henuz giris yapmadan)
    diye sema seviyesinde duruyor, sadece rastgele bir deger ile
    dolduruluyor.

    `invited_by_user_id`: davet gonderen kullanici (admin/owner) - bu
    kullanicinin GERCEKTEN `tenant_id`'nin yetkilisi olup olmadigi
    composite bir FK ile DB seviyesinde dogrulanamaz (User tablosunda
    (id, tenant_id) tekillik kisitlamasi yok) - bu kontrol, davet
    gonderilirken VE kabul edilirken uygulama katmaninda tekrar
    yapilmali (bkz. gorev ozeti - "davet eden adminin yetkisi ... tekrar
    kontrol edilmelidir").
    """

    __tablename__ = "staff_invitations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'accepted', 'expired', 'revoked')",
            name="ck_staff_invitations_status",
        ),
        Index(
            "uq_staff_invitations_one_pending_per_tenant_phone",
            "tenant_id",
            "phone",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    invited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    phone = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, server_default="pending")
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class StaffServiceAssignment(Base):
    """Bir StaffMember'in hangi Service'i verdigini belirtir - ortak
    hizmet kataloguyla (Service) personelin KENDI fiyat/sure sapmasini
    ayirir (bkz. gorev ozeti - iki personel ayni hizmeti farkli fiyatla
    verebilmeli, biri degistirince digeri etkilenmemeli).
    `price_override`/`duration_override` NULL ise Service'in varsayilan
    degeri kullanilir - bu yorumlama uygulama katmaninda yapilir, bu
    gorev sadece semayi ekliyor."""

    __tablename__ = "staff_service_assignments"
    __table_args__ = (
        ForeignKeyConstraint(
            ["staff_member_id", "tenant_id"],
            ["staff_members.id", "staff_members.tenant_id"],
            name="fk_staff_service_assignments_staff_member_id_tenant_id",
        ),
        ForeignKeyConstraint(
            ["service_id", "tenant_id"],
            ["services.id", "services.tenant_id"],
            name="fk_staff_service_assignments_service_id_tenant_id",
        ),
        UniqueConstraint(
            "staff_member_id",
            "service_id",
            name="uq_staff_service_assignments_staff_member_id_service_id",
        ),
    )

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    staff_member_id = Column(Integer, nullable=False)
    service_id = Column(Integer, nullable=False)
    price_override = Column(Numeric(10, 2), nullable=True)
    duration_override = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
