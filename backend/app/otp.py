"""OTP (tek kullanimlik kod) uretimi ve dogrulamasi - telefonla kayit
(purpose="register_phone") ve profile e-posta ekleme
(purpose="profile_email") akislarinin ortak mekanizmasi.

Kod, DB'de duz metin degil hash olarak saklanir (app/security.py'deki
sifre hash'lemeyle ayni bcrypt mekanizmasi) - DB'ye erisen biri gecerli
kodlari dogrudan okuyamaz.
"""
import secrets
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import OtpCode
from app.security import ENVIRONMENT, hash_password, verify_password

OTP_CODE_LENGTH = 6
OTP_EXPIRE_MINUTES = 5
OTP_MAX_ATTEMPTS = 5
# Ayni (purpose, target) icin art arda kod istemeyi yavaslatir - hem gercek
# saglayicide (Netgsm/SMTP) gereksiz maliyeti hem birinin baskasinin
# telefonuna/e-postasina spam OTP gonderttirmesini onler. IP bazli
# OTP_REQUEST_RATE_LIMIT (bkz. app/rate_limit.py) ile birlikte calisir - bu
# ikisi FARKLI seyleri sinirlar (biri hedef, biri kaynak IP bazli).
OTP_RESEND_COOLDOWN_SECONDS = 60

# Production DISINDA, OTP endpoint'lerinin JSON yanitinda kodun kendisi de
# donulur ("debug_code") - gercek bir SMS/e-posta saglayicisi olmadigi icin
# otomatik testlerin ve manuel gelistirme/E2E testinin logdan asenkron
# okumaya gerek kalmadan kodu alabilmesi icin (bkz. gorev ozeti). Production'da
# bu asla donulmez - kod SADECE gercek SMS/e-posta ile kullaniciya ulasir.
OTP_DEBUG_ECHO_ENABLED = ENVIRONMENT != "production"


def _generate_code() -> str:
    # random.choices() KRIPTOGRAFIK OLARAK GUVENLI DEGIL (Mersenne Twister
    # tahmin edilebilir) - OTP kodu gibi guvenlik-kritik bir deger icin
    # `secrets` modulu (os.urandom tabanli, CSPRNG) kullanilir.
    return "".join(secrets.choice(string.digits) for _ in range(OTP_CODE_LENGTH))


def create_otp(db: Session, *, purpose: str, target: str, user_id: int | None = None) -> tuple[OtpCode, str]:
    """Yeni bir OTP satiri olusturur, (satir, duz-metin-kod) dondurur.

    Cagiran taraf, donen kodu app/notifications.py::send_sms/send_email ile
    GERCEK (mock) gonderim icin kullanir - burada asla loglanmaz/donulmez,
    o sorumluluk cagirana ait.
    """
    # Ayni (purpose, target) icin esZAMANLI iki istek, ikisi de henuz
    # commit edilmemisken asagidaki "son X saniyede kod var mi" kontrolunu
    # AYNI ANDA gecebilir (klasik TOCTOU) - cooldown'u etkisiz kilar.
    # SELECT ... FOR UPDATE burada yetersiz kalir cunku ilk istekte
    # kilitlenecek bir satir henuz yok (fantom satir sorunu); bunun yerine
    # Postgres advisory lock ile ayni (purpose, target) icin TUM
    # create_otp cagrilarini serilestiriyoruz. Kilit, bu fonksiyonun
    # sonundaki db.commit() ile (islem bitince otomatik) serbest kalir.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"), {"lock_key": f"otp:{purpose}:{target}"})

    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
    recent = (
        db.query(OtpCode)
        .filter(
            OtpCode.purpose == purpose,
            OtpCode.target == target,
            OtpCode.consumed_at.is_(None),
            OtpCode.created_at > cooldown_cutoff,
        )
        .first()
    )
    if recent is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Yeni kod istemeden once lutfen biraz bekleyin.",
        )

    code = _generate_code()
    otp = OtpCode(
        purpose=purpose,
        target=target,
        user_id=user_id,
        code_hash=hash_password(code),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRE_MINUTES),
    )
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp, code


def verify_otp(db: Session, *, purpose: str, target: str, code: str) -> OtpCode:
    """En guncel, tuketilmemis OtpCode satirini bulup kodu dogrular.

    Basarili olursa satiri consumed_at ile isaretleyip dondurur (cagiran
    taraf, tekrar kullanilmasin diye ayrica bir sey yapmasi gerekmez).
    Basarisiz her durumda HTTPException firlatir.
    """
    otp = (
        db.query(OtpCode)
        .filter(
            OtpCode.purpose == purpose,
            OtpCode.target == target,
            OtpCode.consumed_at.is_(None),
        )
        .order_by(OtpCode.created_at.desc())
        .first()
    )

    if otp is None or otp.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Kod bulunamadi veya suresi dolmus. Yeni kod isteyin.",
        )

    if otp.attempts >= OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cok fazla yanlis deneme. Yeni kod isteyin.",
        )

    if not verify_password(code, otp.code_hash):
        otp.attempts += 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Kod hatali.")

    otp.consumed_at = datetime.now(timezone.utc)
    db.commit()
    return otp
