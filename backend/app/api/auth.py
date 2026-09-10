from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Tenant, User
from app.notifications import send_email, send_sms
from app.otp import OTP_DEBUG_ECHO_ENABLED, create_otp, verify_otp
from app.phone import DEFAULT_COUNTRY_CODE, normalize_phone
from app.rate_limit import (
    AUTH_LOGIN_RATE_LIMIT,
    AUTH_REGISTER_RATE_LIMIT,
    OTP_REQUEST_RATE_LIMIT,
    OTP_VERIFY_RATE_LIMIT,
    limiter,
)
from app.schemas.auth import (
    LoginRequest,
    MobileTokenResponse,
    OtpRequestResponse,
    PhoneNumberInput,
    ProfileAddEmailRequest,
    ProfileVerifyEmailRequest,
    RegisterCompleteRequest,
    RegisterRequest,
    RegisterVerifyOtpRequest,
    RegisterVerifyOtpResponse,
    UserOut,
)
from app.security import (
    AuthContext,
    clear_auth_cookie,
    create_access_token,
    create_registration_token,
    decode_registration_token,
    get_current_tenant,
    hash_password,
    set_auth_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _create_tenant_and_user(db: Session, payload: RegisterRequest) -> tuple[Tenant, User]:
    tenant = Tenant(name=payload.tenant_name)
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="owner",
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    return tenant, user


def _create_tenant_and_user_from_phone(
    db: Session, phone: str, tenant_name: str, password: str
) -> tuple[Tenant, User]:
    tenant = Tenant(name=tenant_name)
    db.add(tenant)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        phone=phone,
        password_hash=hash_password(password),
        role="owner",
    )
    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Phone already registered"
        )

    return tenant, user


def _find_user_by_identifier(db: Session, identifier: str) -> User | None:
    """Giris alanindaki degeri ONCE email, sonra (varsayilan ulke koduyla
    normalize edilmis) telefon olarak arar - kullanicidan format
    belirtmesini istemiyoruz (bkz. gorev ozeti). `identifier` gecerli bir
    telefon formatina normalize edilemiyorsa (orn. ne email ne telefon gibi
    duran bir girdi), normalize_phone'un firlattigi 422 burada yutulup
    "eslesme yok" olarak degerlendirilir - login'in her zaman ayni (401)
    hatayi donmesi icin.
    """
    user = db.query(User).filter(User.email == identifier).first()
    if user is not None:
        return user

    try:
        normalized_phone = normalize_phone(DEFAULT_COUNTRY_CODE, identifier)
    except HTTPException:
        return None
    return db.query(User).filter(User.phone == normalized_phone).first()


def _authenticate_by_identifier(db: Session, identifier: str, password: str) -> User:
    user = _find_user_by_identifier(db, identifier)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return user


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_REGISTER_RATE_LIMIT)
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)) -> Response:
    """Eski (dogrudan email+sifre) kayit akisi - bkz.
    app/schemas/auth.py::RegisterRequest docstring'i. Web/mobil UI artik
    bunun yerine /auth/register/request-otp -> verify-otp -> complete
    ucuncu adimini kullaniyor; bu endpoint SADECE geriye donuk uyumluluk
    (mevcut testler/entegrasyonlar) icin duruyor."""
    tenant, user = _create_tenant_and_user(db, payload)
    token = create_access_token(user_id=user.id, tenant_id=tenant.id)
    response = Response(status_code=status.HTTP_201_CREATED)
    set_auth_cookie(response, token)
    return response


@router.post("/login")
@limiter.limit(AUTH_LOGIN_RATE_LIMIT)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> Response:
    user = _authenticate_by_identifier(db, payload.email_or_phone, payload.password)
    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id)
    response = Response(status_code=status.HTTP_200_OK)
    set_auth_cookie(response, token)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookie(response)
    return response


@router.get("/me", response_model=UserOut)
def get_me(
    db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_tenant)
) -> User:
    user = db.query(User).filter(User.id == auth.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


# --- Telefon + OTP ile kayit ---
#
# Ucuncu adima bolunmus akis (bkz. gorev ozeti):
#   1. request-otp  : telefon -> kod uretilir, MOCK SMS ile "gonderilir"
#   2. verify-otp   : telefon + kod -> dogrulanirsa kisa omurlu bir
#                      registration_token donulur
#   3. complete     : registration_token + firma adi + sifre -> hesap
#                      olusur (web: cookie, mobil: /mobile/register/complete
#                      ile govdede token)
#
# Adim 1-2 arasinda henuz bir Tenant/User yok - "dogrulanmis telefon"
# bilgisi bir DB satirinda degil, registration_token'in kendisinde tasinir
# (bkz. app/security.py::create_registration_token).


@router.post("/register/request-otp", response_model=OtpRequestResponse)
@limiter.limit(OTP_REQUEST_RATE_LIMIT)
def register_request_otp(
    request: Request, payload: PhoneNumberInput, db: Session = Depends(get_db)
) -> OtpRequestResponse:
    phone = normalize_phone(payload.country_code, payload.phone_number)

    if db.query(User).filter(User.phone == phone).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu telefon numarasi zaten kayitli"
        )

    _otp, code = create_otp(db, purpose="register_phone", target=phone)
    send_sms(phone, f"Servisçep dogrulama kodunuz: {code} (5 dakika gecerli)")
    return OtpRequestResponse(debug_code=code if OTP_DEBUG_ECHO_ENABLED else None)


@router.post("/register/verify-otp", response_model=RegisterVerifyOtpResponse)
@limiter.limit(OTP_VERIFY_RATE_LIMIT)
def register_verify_otp(
    request: Request, payload: RegisterVerifyOtpRequest, db: Session = Depends(get_db)
) -> RegisterVerifyOtpResponse:
    phone = normalize_phone(payload.country_code, payload.phone_number)
    verify_otp(db, purpose="register_phone", target=phone, code=payload.code)
    return RegisterVerifyOtpResponse(registration_token=create_registration_token(phone))


@router.post("/register/complete", status_code=status.HTTP_201_CREATED)
def register_complete(payload: RegisterCompleteRequest, db: Session = Depends(get_db)) -> Response:
    phone = decode_registration_token(payload.registration_token)
    tenant, user = _create_tenant_and_user_from_phone(
        db, phone, payload.tenant_name, payload.password
    )
    token = create_access_token(user_id=user.id, tenant_id=tenant.id)
    response = Response(status_code=status.HTTP_201_CREATED)
    set_auth_cookie(response, token)
    return response


# --- Profil: sonradan e-posta ekleme ---
#
# Iki adim: request-email-otp (MOCK e-posta ile kod gonderilir) ->
# verify-email (kod dogrulanirsa email HEMEN mevcut hesaba yazilir - ayri
# bir "complete" adimina gerek yok, zaten giris yapmis bir kullaniciyiz).


@router.post("/profile/request-email-otp", response_model=OtpRequestResponse)
@limiter.limit(OTP_REQUEST_RATE_LIMIT)
def profile_request_email_otp(
    request: Request,
    payload: ProfileAddEmailRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
) -> OtpRequestResponse:
    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten kullaniliyor"
        )

    _otp, code = create_otp(
        db, purpose="profile_email", target=payload.email, user_id=auth.user_id
    )
    send_email(
        payload.email,
        "Servisçep e-posta dogrulama",
        f"Dogrulama kodunuz: {code} (5 dakika gecerli)",
    )
    return OtpRequestResponse(debug_code=code if OTP_DEBUG_ECHO_ENABLED else None)


@router.post("/profile/verify-email", response_model=UserOut)
@limiter.limit(OTP_VERIFY_RATE_LIMIT)
def profile_verify_email(
    request: Request,
    payload: ProfileVerifyEmailRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
) -> User:
    otp = verify_otp(db, purpose="profile_email", target=payload.email, code=payload.code)
    # Kod dogru olsa bile BASKA bir kullanicinin istedigi bir OTP'yi bu
    # kullanicinin kendi hesabina uygulamasini engeller (bkz.
    # app/models.py::OtpCode.user_id docstring'i).
    if otp.user_id != auth.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kod hatali.")

    user = db.query(User).filter(User.id == auth.user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.email = payload.email
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bu e-posta zaten kullaniliyor"
        )
    db.refresh(user)
    return user


# --- Mobil auth ---
#
# React Native'in tarayici cookie jar'i yok, bu yuzden web'deki httpOnly
# cookie akisi (yukarida) mobil'de kullanilamiyor. Token burada dogrudan
# govdede donuluyor, mobil taraf onu secure storage'a (iOS Keychain /
# Android Keystore - Expo'da expo-secure-store) yazip sonraki isteklerde
# "Authorization: Bearer <token>" header'iyla gonderiyor.
# app/security.py::get_current_tenant hem cookie'yi hem bu header'i kabul
# ediyor - web akisi bundan ETKILENMIYOR (cookie varsa once o bulunuyor).
#
# Kasitli olarak eklenmeyenler:
# - Refresh token / rotation: kapsam disi birakildi (bkz. gorev ozeti) -
#   access token web'le ayni omre sahip (24 saat), suresi dolunca mobil
#   kullanici tekrar login olur. Ileride eklenebilir.
# - /auth/mobile/logout: sunucu tarafinda tutulan bir session/refresh
#   kaydi olmadigi icin logout tamamen istemci tarafinda (secure storage'dan
#   token silme) - sunucuya bildirilecek bir sey yok.


@router.post(
    "/mobile/register",
    status_code=status.HTTP_201_CREATED,
    response_model=MobileTokenResponse,
)
@limiter.limit(AUTH_REGISTER_RATE_LIMIT)
def register_mobile(
    request: Request, payload: RegisterRequest, db: Session = Depends(get_db)
) -> MobileTokenResponse:
    """Eski (dogrudan email+sifre) mobil kayit akisi - bkz. register()
    docstring'i, mobil karsiligi."""
    tenant, user = _create_tenant_and_user(db, payload)
    token = create_access_token(user_id=user.id, tenant_id=tenant.id)
    return MobileTokenResponse(access_token=token)


@router.post("/mobile/login", response_model=MobileTokenResponse)
@limiter.limit(AUTH_LOGIN_RATE_LIMIT)
def login_mobile(
    request: Request, payload: LoginRequest, db: Session = Depends(get_db)
) -> MobileTokenResponse:
    user = _authenticate_by_identifier(db, payload.email_or_phone, payload.password)
    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id)
    return MobileTokenResponse(access_token=token)


@router.post(
    "/mobile/register/complete",
    status_code=status.HTTP_201_CREATED,
    response_model=MobileTokenResponse,
)
def register_complete_mobile(
    payload: RegisterCompleteRequest, db: Session = Depends(get_db)
) -> MobileTokenResponse:
    phone = decode_registration_token(payload.registration_token)
    tenant, user = _create_tenant_and_user_from_phone(
        db, phone, payload.tenant_name, payload.password
    )
    token = create_access_token(user_id=user.id, tenant_id=tenant.id)
    return MobileTokenResponse(access_token=token)
