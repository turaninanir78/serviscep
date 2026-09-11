import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access_log import log_access
from app.db import get_db
from app.models import Customer
from app.schemas.customer import CustomerCreate, CustomerOut
from app.security import AuthContext, get_current_tenant

# KVKK unutulma hakki kapsaminda anonimlestirilen musterilerin gorunecegi
# isim - gercek isim/telefon kalici olarak degistirilir (bkz.
# request_customer_deletion). Randevu gecmisinde musteri baglantisi hala
# GECERLI (appointments.customer_id silinmiyor) - sadece bu isim gorunur.
ANONYMIZED_DISPLAY_NAME = "Silinmiş Müşteri"

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    customer = Customer(tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(customer)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Customer with this whatsapp_number already exists",
        )
    db.refresh(customer)
    return customer


@router.get("", response_model=list[CustomerOut])
def list_customers(
    db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_tenant)
):
    # Silinmis (anonimlestirilmis) musteriler normal listede gorunmez -
    # hala DB'de var (randevu gecmisi icin, bkz. request_customer_deletion)
    # ama artik aktif bir musteri degiller. Randevu detayinda
    # customer_id uzerinden ayrica cekilip "Silinmis Musteri" olarak
    # gosterilebilirler (bkz. get_customer - ORADA filtrelenmiyor).
    return (
        db.query(Customer)
        .filter(Customer.tenant_id == auth.tenant_id, Customer.deleted_at.is_(None))
        .all()
    )


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == auth.tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    log_access(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        resource_type="customer",
        resource_id=customer.id,
        action="GET",
    )
    return customer


@router.post("/{customer_id}/request-deletion", response_model=CustomerOut)
def request_customer_deletion(
    customer_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    """KVKK madde 7 (unutulma hakki) - musterinin kisisel verilerini
    (isim, telefon) kalici olarak anonimlestirir. GERI ALINAMAZ.

    Randevu kayitlari (appointments) SILINMEZ - customer_id baglantisi
    korunur, sadece bu musteriye ait gorunen bilgi anonimlestirilmis
    olur (istatistik/gecmis butunlugu icin, bkz. gorev ozeti).

    whatsapp_number'i (dolayisiyla whatsapp_number_hash'i, bkz.
    app/models.py::_sync_customer_whatsapp_number_hash event listener'i)
    rastgele bir yer tutucuyla degistiriyoruz - aksi halde ayni gercek
    numaradan gelen bir sonraki WhatsApp mesaji (bkz.
    app/api/webhooks.py::_store_inbound_message) bu anonimlestirilmis
    kayda tekrar eslesirdi. Silme sonrasi ayni numaradan gelen bir mesaj
    artik YENI bir Customer satiri olusturur - bu dogru davranistir.
    """
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == auth.tenant_id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if customer.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Customer data already deleted"
        )

    now = datetime.now(timezone.utc)
    customer.deletion_requested_at = now
    customer.display_name = ANONYMIZED_DISPLAY_NAME
    customer.whatsapp_number = f"deleted:{customer.id}:{secrets.token_hex(8)}"
    customer.deleted_at = now
    db.commit()
    db.refresh(customer)

    log_access(
        db,
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        resource_type="customer",
        resource_id=customer.id,
        action="DELETE",
    )
    return customer
