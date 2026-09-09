from pydantic import BaseModel


class RegisterRequest(BaseModel):
    tenant_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str
