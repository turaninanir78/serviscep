from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Tenant, User
from app.rate_limit import AUTH_LOGIN_RATE_LIMIT, AUTH_REGISTER_RATE_LIMIT, limiter
from app.schemas.auth import LoginRequest, MobileTokenResponse, RegisterRequest
from app.security import (
    clear_auth_cookie,
    create_access_token,
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


def _authenticate(db: Session, payload: LoginRequest) -> User:
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return user


@router.post("/register", status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_REGISTER_RATE_LIMIT)
def register(request: Request, payload: RegisterRequest, db: Session = Depends(get_db)) -> Response:
    tenant, user = _create_tenant_and_user(db, payload)
    token = create_access_token(user_id=user.id, tenant_id=tenant.id)
    response = Response(status_code=status.HTTP_201_CREATED)
    set_auth_cookie(response, token)
    return response


@router.post("/login")
@limiter.limit(AUTH_LOGIN_RATE_LIMIT)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)) -> Response:
    user = _authenticate(db, payload)
    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id)
    response = Response(status_code=status.HTTP_200_OK)
    set_auth_cookie(response, token)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookie(response)
    return response


# --- Mobil auth ---
#
# React Native'in tarayici cookie jar'i yok, bu yuzden web'deki httpOnly
# cookie akisi (yukarida) mobil'de kullanilamiyor. Token burada dogrudan
# govdede donuluyor; mobil taraf onu secure storage'a (iOS Keychain / Android
# Keystore - Expo'da expo-secure-store) yazip sonraki isteklerde
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
    tenant, user = _create_tenant_and_user(db, payload)
    token = create_access_token(user_id=user.id, tenant_id=tenant.id)
    return MobileTokenResponse(access_token=token)


@router.post("/mobile/login", response_model=MobileTokenResponse)
@limiter.limit(AUTH_LOGIN_RATE_LIMIT)
def login_mobile(
    request: Request, payload: LoginRequest, db: Session = Depends(get_db)
) -> MobileTokenResponse:
    user = _authenticate(db, payload)
    token = create_access_token(user_id=user.id, tenant_id=user.tenant_id)
    return MobileTokenResponse(access_token=token)
