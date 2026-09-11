from sqlalchemy.orm import Session

from app.models import AccessLog


def log_access(
    db: Session, *, tenant_id: int, user_id: int, resource_type: str, resource_id: int, action: str
) -> None:
    """Tekil bir kayda erisimi denetim izine yazar ve HEMEN commit eder.

    Ayri bir commit gerekiyor: GET gibi salt-okunur endpoint'lerde zaten
    baska bir commit yok (bkz. app/db.py::get_db - session sadece
    kapatiliyor, commit edilmiyor) - bu satir olmadan eklenen AccessLog
    satiri, istek sonunda sessizce rollback edilirdi.
    """
    db.add(
        AccessLog(
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
        )
    )
    db.commit()
