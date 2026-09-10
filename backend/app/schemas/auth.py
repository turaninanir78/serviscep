from pydantic import BaseModel


class RegisterRequest(BaseModel):
    tenant_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class MobileTokenResponse(BaseModel):
    """Web'in aksine (token httpOnly cookie'de tasinir), mobil client'larin
    tarayici cookie jar'i yok - token dogrudan govdede donuluyor, mobil
    taraf onu secure storage'a yazip Authorization: Bearer ile gonderiyor."""

    access_token: str
    token_type: str = "bearer"
