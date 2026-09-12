"""Personel (staff) yetki kontrolu - bkz. app/models.py::TenantMembership
docstring'i (her isletmeye uyabilecek esneklik icin sabit bir rol yerine
personel basina ac/kapa yetki anahtarlari) ve app/security.py::AuthContext
(role/staff_member_id/permissions buradan gelir, her istekte TAZE
cozumlenir).

Owner HER ZAMAN tam yetkilidir - asagidaki iki fonksiyon SADECE
role="staff" icin gercek bir kontrol yapar, owner icin hep sessizce
gecer.
"""
from fastapi import HTTPException, status

from app.security import AuthContext


def require_owner(auth: AuthContext) -> None:
    """Personel ekleme/cikarma/davet yonetimi ve izin duzenleme HER ZAMAN
    owner'a ozeldir - bu, yetki listesinde (bkz. gorev ozeti) hicbir
    zaman personele devredilemeyecek TEK sabit kural."""
    if auth.role != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için yetkiniz yok."
        )


def require_permission(auth: AuthContext, permission: str) -> None:
    if auth.role == "owner":
        return
    if permission not in auth.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için yetkiniz yok."
        )


def require_own_staff_resource(auth: AuthContext, staff_id: int) -> None:
    """Personel, yetkisi acik olsa bile SADECE KENDI staff_member_id'sine
    ait kaynaklari (randevu, calisma plani) yonetebilir - baskasi adina
    islem yapamaz. Var olmayan bir kaynakla ayni 404'u donuyoruz (bkz.
    diger endpoint'lerdeki "not found" deseni) - hangi staff_id'lerin
    gercekten var oldugunu sizdirmemek icin 403 yerine 404."""
    if auth.role == "staff" and staff_id != auth.staff_member_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
