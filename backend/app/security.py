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
