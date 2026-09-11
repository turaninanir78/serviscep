from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.access_log import log_access
from app.db import get_db
from app.models import Customer
from app.schemas.customer import CustomerCreate, CustomerOut
from app.security import AuthContext, get_current_tenant

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
    return db.query(Customer).filter(Customer.tenant_id == auth.tenant_id).all()


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
