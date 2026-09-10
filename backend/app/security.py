import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request, Response, status
from passlib.context import CryptContext

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


@dataclass(frozen=True)
class AuthContext:
    user_id: int
    tenant_id: int


def get_current_tenant(request: Request) -> AuthContext:
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
        return AuthContext(user_id=payload["user_id"], tenant_id=payload["tenant_id"])
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )
