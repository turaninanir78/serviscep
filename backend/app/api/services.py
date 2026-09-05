from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Service
from app.schemas.service import ServiceCreate, ServiceOut, ServiceUpdate
from app.security import AuthContext, get_current_tenant

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    service = Service(tenant_id=auth.tenant_id, **payload.model_dump())
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("", response_model=list[ServiceOut])
def list_services(
    db: Session = Depends(get_db), auth: AuthContext = Depends(get_current_tenant)
):
    return db.query(Service).filter(Service.tenant_id == auth.tenant_id).all()


@router.get("/{service_id}", response_model=ServiceOut)
def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    service = (
        db.query(Service)
        .filter(Service.id == service_id, Service.tenant_id == auth.tenant_id)
        .first()
    )
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service


@router.patch("/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_current_tenant),
):
    service = (
        db.query(Service)
        .filter(Service.id == service_id, Service.tenant_id == auth.tenant_id)
        .first()
    )
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, field, value)

    db.commit()
    db.refresh(service)
    return service
