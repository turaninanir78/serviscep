from pydantic import BaseModel, ConfigDict


class RegisterRequest(BaseModel):
    """Eski (dogrudan email+sifre) kayit akisi - artik web/mobil UI
    tarafindan kullanilmiyor (yerini asagidaki telefon+OTP akisi aldi) ama
    geriye donuk uyumluluk icin (mevcut test/entegrasyonlar) korunuyor -
    bkz. gorev ozeti."""

    tenant_name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    # Kullanici tek bir "email veya telefon" alanina girer - backend hangi
    # formatta oldugunu varsaymadan once email, sonra (normalize ederek)
    # telefon alaninda arar (bkz. app/api/auth.py::_find_user_by_identifier).
    email_or_phone: str
    password: str


class MobileTokenResponse(BaseModel):
    """Web'in aksine (token httpOnly cookie'de tasinir), mobil client'larin
    tarayici cookie jar'i yok - token dogrudan govdede donuluyor, mobil
    taraf onu secure storage'a yazip Authorization: Bearer ile gonderiyor."""

    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    email: str | None
    phone: str | None
    role: str


# --- Telefon + OTP ile kayit ---


class PhoneNumberInput(BaseModel):
    # Web/mobil, ayri bir ulke kodu secici + numara alani gosteriyor (bkz.
    # frontend/mobile lib/countryCodes.ts) - backend ikisini alip merkezi
    # olarak normalize ediyor (bkz. app/phone.py::normalize_phone).
    country_code: str
    phone_number: str


class OtpRequestResponse(BaseModel):
    message: str = "ok"
    # SADECE production disinda dolu - bkz. app/otp.py::OTP_DEBUG_ECHO_ENABLED.
    debug_code: str | None = None


class RegisterVerifyOtpRequest(PhoneNumberInput):
    code: str


class RegisterVerifyOtpResponse(BaseModel):
    registration_token: str


class RegisterCompleteRequest(BaseModel):
    registration_token: str
    tenant_name: str
    password: str


# --- Profil: sonradan e-posta ekleme ---


class ProfileAddEmailRequest(BaseModel):
    email: str


class ProfileVerifyEmailRequest(BaseModel):
    email: str
    code: str
