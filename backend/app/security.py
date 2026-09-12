import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import TenantMembership

JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 1440

# JWT'nin tasindigi httpOnly cookie. XSS ile calisan bir script bu cookie'yi
# document.cookie uzerinden OKUYAMAZ (httponly=True) - token artik sadece
# tarayici tarafindan otomatik eklenir, JS'in eline hic gecmez.
ACCESS_TOKEN_COOKIE_NAME = "access_token"

# Dev'de (docker-compose, http://localhost) Secure=True olursa tarayici
# cookie'yi hic kaydetmez (Secure cookie'ler sadece HTTPS uzerinden kabul
# edilir) - login basarili gorunur ama sonraki her istek 401 doner. Bu yuzden
# varsayilan false; prod'da (HTTPS arkasinda) COOKIE_SECURE=true set edilmeli.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

# Dev/test'te belirtilmezse "development" sayilir - mevcut varsayilan
# davranis (COOKIE_SECURE=false serbest) aynen korunur. Sadece ENVIRONMENT
# acikca "production" olarak ayarlandiginda asagidaki kontrol devreye girer.
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development").strip().lower()


def _validate_cookie_security(environment: str, cookie_secure: bool) -> None:
    """Production'da COOKIE_SECURE=false ile calismayi ENGELLER - aksi halde
    JWT tasiyan httpOnly cookie, Secure bayragi olmadan acik metin HTTP
    uzerinden de tasinabilir, bu da bir man-in-the-middle saldirganinin
    oturum cookie'sini calmasina izin verir. Ayri, parametreli bir fonksiyon
    olmasinin sebebi: modulun kendi global durumuna (ENVIRONMENT/
    COOKIE_SECURE, yukarida) bagli kalmadan, dogrudan farkli
    kombinasyonlarla unit test edilebilmesi.
    """
    if environment == "production" and not cookie_secure:
        raise RuntimeError(
            "COOKIE_SECURE must be true in production "
            "(set the COOKIE_SECURE environment variable to \"true\")"
        )


# Modul import edilir edilmez (yani uygulama baslarken, ilk router
# import'unda) calisir - yanlis yapilandirilmis bir production ortaminda
# uygulamanin hic ayaga kalkmamasini saglar.
_validate_cookie_security(ENVIRONMENT, COOKIE_SECURE)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: int, tenant_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"user_id": user_id, "tenant_id": tenant_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


# Telefon+OTP ile kayit, iki adima bolunmus durumda (once telefon
# dogrulanir, sonra sifre/firma adi alinir) ama henuz bir Tenant/User
# olusmadigi icin normal bir access token verilemez. Bunun yerine, "bu
# telefon az once dogrulandi" bilgisini tasiyan, KISA omurlu, ayri amacli
# (purpose alaniyla normal access token'dan ayirt edilen) bir JWT
# kullaniliyor - ek bir "pending registration" tablosuna gerek kalmadan.
REGISTRATION_TOKEN_PURPOSE = "phone_verified_registration"
REGISTRATION_TOKEN_EXPIRE_MINUTES = 10


def create_registration_token(phone: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=REGISTRATION_TOKEN_EXPIRE_MINUTES)
    payload = {"purpose": REGISTRATION_TOKEN_PURPOSE, "phone": phone, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_registration_token(token: str) -> str:
    """Gecerliyse dogrulanmis telefon numarasini dondurur, degilse 400."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dogrulama oturumunun suresi dolmus. Lutfen tekrar baslayin.",
        )
    if payload.get("purpose") != REGISTRATION_TOKEN_PURPOSE or not payload.get("phone"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Gecersiz dogrulama oturumu."
        )
    return payload["phone"]


# Sifre sifirlama (unuttum) da registration_token ile ayni stateless JWT
# yaklasimini kullanir - ek bir "pending reset" tablosuna gerek yok. Farkli
# olan tek sey: bu token'in TEK KULLANIMLIK olmasi gerekiyor (sifre
# degistirildikten sonra ayni linkin/koddan turetilen token'in tekrar
# calismasi istenmiyor). Bunu ayri bir "kullanildi" tablosu/sutunu OLMADAN
# saglamak icin, token'in icine sifrenin o anki hash'inin bir PARMAK IZI
# (ham hash degil - bcrypt hash'i istemciye dogrudan gondermek gereksiz risk)
# gomuluyor: /complete asamasinda bu parmak izi kullanicinin O ANKI
# password_hash'iyla karsilastirilir. Ilk basarili kullanim sifreyi
# degistirdigi icin parmak izi otomatik olarak eskir - ayni token bir daha
# ASLA eslesmez (kullanicinin sifresini baska bir yoldan degistirmesi de
# ayni sekilde token'i geciz kilar - ekstra bir guvenlik faydasi).
PASSWORD_RESET_TOKEN_PURPOSE = "password_reset"
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 10


def _password_fingerprint(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode()).hexdigest()


def create_password_reset_token(user_id: int, current_password_hash: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    payload = {
        "purpose": PASSWORD_RESET_TOKEN_PURPOSE,
        "user_id": user_id,
        "pwfp": _password_fingerprint(current_password_hash),
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_password_reset_token(token: str) -> tuple[int, str]:
    """Gecerliyse (user_id, sifre parmak izi) dondurur, degilse 400."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Şifre sıfırlama bağlantısının süresi dolmuş. Lütfen tekrar deneyin.",
        )
    if payload.get("purpose") != PASSWORD_RESET_TOKEN_PURPOSE or "user_id" not in payload or "pwfp" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz şifre sıfırlama isteği."
        )
    return payload["user_id"], payload["pwfp"]


def password_reset_token_is_still_valid(current_password_hash: str, token_fingerprint: str) -> bool:
    """Token olusturuldugundan beri sifre DEGISMEDIYSE True - bkz. modul
    ustundeki aciklama (tek-kullanimlik token, ekstra tablo olmadan)."""
    return _password_fingerprint(current_password_hash) == token_fingerprint


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        # Lax: ayni site (port farketmiyor) fetch/XHR istekleriyle gonderilir,
        # ama farkli bir sitenin tetikledigi cross-site POST/PATCH istegine
        # EKLENMEZ - butun mutasyon endpoint'lerimiz POST/PATCH oldugu icin bu
        # CSRF'e karsi zaten pratik bir koruma sagliyor; Strict, kullaniciyi
        # panele disaridan gelen bir linkle girdiginde de cookie'yi disleyip
        # gereksiz yere tekrar login istetirdi.
        samesite="lax",
        max_age=JWT_EXPIRE_MINUTES * 60,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=ACCESS_TOKEN_COOKIE_NAME, path="/")


# Personel/coklu-kullanici uyeligi (bkz. app/models.py::TenantMembership)
# devreye alinirken eklendi - bir "staff" satirinda hangi islemlerin
# acik/kapali oldugunu belirten sutun adlari. app/permissions.py bu
# listeyi (dolayisiyla AuthContext.permissions'i) kullanarak yetki
# kontrolu yapiyor; buradan disari (permissions.py'ye) aktarilan TEK
# kaynak burasi - iki yerde ayri ayri tanimlanip birbirinden sapmasin
# diye.
STAFF_PERMISSIONS: tuple[str, ...] = (
    "can_view_customers",
    "can_create_appointments",
    "can_cancel_appointments",
    "can_confirm_complete_appointments",
    "can_manage_availability",
    "can_manage_services",
)


@dataclass(frozen=True)
class AuthContext:
    user_id: int
    tenant_id: int
    # "owner" (kendi isletmesi - varsayilan/legacy davranis) veya "staff"
    # (bir baska isletmeye davetle baglanmis). Owner HER ZAMAN tam
    # yetkilidir, asagidaki `permissions` SADECE role="staff" icin
    # anlamlidir (bkz. app/permissions.py::require_permission).
    role: str = "owner"
    # SADECE role="staff" icin doludur - bu kullanicinin o tenant'taki
    # hangi StaffMember kaydina karsilik geldigini gosterir (bkz.
    # app/permissions.py::require_own_staff_resource).
    staff_member_id: int | None = None
    permissions: frozenset[str] = field(default_factory=frozenset)


def _resolve_auth_context(user_id: int, legacy_tenant_id: int, db: Session) -> AuthContext:
    """JWT SADECE user_id tasir (tenant_id de tasir ama asagida GORMEZDEN
    GELINIR) - aktif calisma baglami (su an HANGI isletme altinda
    calisiliyor) her istekte TenantMembership'ten TAZE okunur. Boylece
    bir davet kabul edildiginde/bir uyelikten ayrilindiginda kullanicinin
    JWT'si hala gecerliyken (24 saat) bile DEGISIKLIK bir sonraki
    istekte hemen yansir - yeniden giris yapmasi gerekmez.

    `legacy_tenant_id`, HICBIR aktif TenantMembership satiri bulunamazsa
    (migration 0011'den ONCEKI bir hesap - olmamali ama garanti olsun
    diye - veya dogrudan DB fixture'iyle olusturulmus bir test kullanicisi,
    bkz. ornegin test_appointment_race_condition.py'deki
    create_access_token(user_id=0, ...) kullanimi) DUSULECEK guvenlik
    agidir - bu durumda eskisi gibi JWT'deki tenant_id'ye guvenilip
    "owner" gibi davranilir.
    """
    memberships = (
        db.query(TenantMembership)
        .filter(TenantMembership.user_id == user_id, TenantMembership.status == "active")
        .all()
    )
    # Bir kullanicinin ayni anda hem KENDI tenant'inda bir owner satiri
    # HEM baska bir tenant'ta bir staff satiri olabilir (DB kisiti sadece
    # "en fazla bir aktif staff" ve "tenant basina en fazla bir aktif
    # uyelik" der, ikisinin BIRLIKTE var olmasini engellemez) - staff
    # satiri varsa SU AN calisilan isletme odur, yoksa kendi tenant'i.
    active = next((m for m in memberships if m.role == "staff"), None) or next(
        (m for m in memberships if m.role == "owner"), None
    )

    if active is None:
        return AuthContext(user_id=user_id, tenant_id=legacy_tenant_id, role="owner")

    if active.role != "staff":
        return AuthContext(user_id=user_id, tenant_id=active.tenant_id, role="owner")

    granted = frozenset(name for name in STAFF_PERMISSIONS if getattr(active, name))
    return AuthContext(
        user_id=user_id,
        tenant_id=active.tenant_id,
        role="staff",
        staff_member_id=active.staff_member_id,
        permissions=granted,
    )


def get_current_tenant(
    request: Request, db: Session = Depends(get_db)
) -> AuthContext:
    token = request.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
    if token is None:
        # Mobil app'lerin (React Native) tarayici cookie jar'i yok - token'i
        # Authorization: Bearer header'iyla gonderiyorlar (bkz. app/api/auth.py
        # /auth/mobile/*). Web akisi bundan ETKILENMIYOR: cookie varsa yukarida
        # zaten bulunup buraya hic dusulmuyor.
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip() or None
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    try:
        user_id = payload["user_id"]
        legacy_tenant_id = payload["tenant_id"]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )

    return _resolve_auth_context(user_id, legacy_tenant_id, db)
