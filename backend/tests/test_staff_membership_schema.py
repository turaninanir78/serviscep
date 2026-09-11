"""Personel / cok kullanicili tenant uyeligi - sema iskeleti testleri.

Bu gorevde HENUZ hicbir endpoint/servis katmani eklenmedi (bkz.
app/models.py'deki TenantMembership/StaffInvitation/StaffServiceAssignment
ustundeki blok yorum) - bu yuzden testler HTTP uzerinden degil, dogrudan
SQLAlchemy session'i ile modellerin/kisitlamalarin (constraint) DB
seviyesinde iddia ettikleri gibi davrandigini dogruluyor:
- Partial unique index'lerin GERCEKTEN kismi (sadece belirli satirlari)
  kapsadigini,
- Composite FK'lerin (staff_member_id/service_id + tenant_id) farkli bir
  tenant'a ait bir kaydin yanlislikla baglanmasini engelledigini.

test_appointment_lifecycle.py ile ayni yaklasim: dogrudan DB fixture'i,
HTTP degil.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import (
    Service,
    StaffInvitation,
    StaffMember,
    StaffServiceAssignment,
    Tenant,
    TenantMembership,
    User,
)


@pytest.fixture
def fixtures():
    db = SessionLocal()
    tenant_a = Tenant(name="Membership Schema Tenant A")
    tenant_b = Tenant(name="Membership Schema Tenant B")
    db.add_all([tenant_a, tenant_b])
    db.flush()

    user = User(
        tenant_id=tenant_a.id,
        email=f"membership-schema-{uuid.uuid4().hex}@example.com",
        password_hash="not-a-real-hash",
        role="owner",
    )
    staff_a = StaffMember(tenant_id=tenant_a.id, name="Staff A")
    staff_b = StaffMember(tenant_id=tenant_b.id, name="Staff B")
    service_a = Service(tenant_id=tenant_a.id, name="Service A", duration_minutes=30)
    service_b = Service(tenant_id=tenant_b.id, name="Service B", duration_minutes=30)
    db.add_all([user, staff_a, staff_b, service_a, service_b])
    db.commit()
    db.refresh(user)
    db.refresh(staff_a)
    db.refresh(staff_b)
    db.refresh(service_a)
    db.refresh(service_b)

    yield db, tenant_a, tenant_b, user, staff_a, staff_b, service_a, service_b

    db.rollback()
    db.query(Tenant).filter(Tenant.id.in_([tenant_a.id, tenant_b.id])).delete(
        synchronize_session=False
    )
    db.commit()
    db.close()


def test_owner_membership_can_be_created_without_a_staff_member(fixtures):
    db, tenant_a, _tenant_b, user, *_ = fixtures
    membership = TenantMembership(user_id=user.id, tenant_id=tenant_a.id, role="owner")
    db.add(membership)
    db.commit()
    db.refresh(membership)

    assert membership.status == "active"
    assert membership.staff_member_id is None


def test_staff_membership_can_link_to_a_staff_member_in_the_same_tenant(fixtures):
    db, tenant_a, _tenant_b, user, staff_a, *_ = fixtures
    membership = TenantMembership(
        user_id=user.id, tenant_id=tenant_a.id, role="staff", staff_member_id=staff_a.id
    )
    db.add(membership)
    db.commit()  # IntegrityError firlatmamali


def test_staff_membership_cannot_link_to_a_staff_member_in_a_different_tenant(fixtures):
    db, tenant_a, _tenant_b, user, _staff_a, staff_b, *_ = fixtures
    membership = TenantMembership(
        user_id=user.id, tenant_id=tenant_a.id, role="staff", staff_member_id=staff_b.id
    )
    db.add(membership)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_invalid_role_is_rejected_by_check_constraint(fixtures):
    db, tenant_a, _tenant_b, user, *_ = fixtures
    membership = TenantMembership(user_id=user.id, tenant_id=tenant_a.id, role="superadmin")
    db.add(membership)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_user_cannot_have_two_active_memberships_in_the_same_tenant(fixtures):
    db, tenant_a, _tenant_b, user, *_ = fixtures
    db.add(TenantMembership(user_id=user.id, tenant_id=tenant_a.id, role="owner"))
    db.commit()

    db.add(TenantMembership(user_id=user.id, tenant_id=tenant_a.id, role="owner"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_a_left_membership_does_not_block_a_new_active_one_in_the_same_tenant(fixtures):
    """Partial unique index SADECE status='active' satirlarini kapsiyor -
    ayrilmis (status='left') bir kayit, ayni (user, tenant) icin yeni bir
    aktif uyelik olusturulmasini ENGELLEMEMELI (orn. personel ayrilip
    sonra tekrar katilirsa)."""
    db, tenant_a, _tenant_b, user, *_ = fixtures
    left_membership = TenantMembership(
        user_id=user.id,
        tenant_id=tenant_a.id,
        role="staff",
        status="left",
        left_at=datetime.now(timezone.utc),
    )
    db.add(left_membership)
    db.commit()

    db.add(TenantMembership(user_id=user.id, tenant_id=tenant_a.id, role="staff"))
    db.commit()  # IntegrityError firlatmamali


def test_user_cannot_have_two_active_staff_memberships_in_different_tenants(fixtures):
    db, tenant_a, tenant_b, user, staff_a, staff_b, *_ = fixtures
    db.add(
        TenantMembership(
            user_id=user.id, tenant_id=tenant_a.id, role="staff", staff_member_id=staff_a.id
        )
    )
    db.commit()

    db.add(
        TenantMembership(
            user_id=user.id, tenant_id=tenant_b.id, role="staff", staff_member_id=staff_b.id
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_user_can_be_active_owner_in_one_tenant_and_active_staff_in_another():
    """Sadece "iki AKTIF STAFF" kisitlaniyor - bir kisi kendi tenant'inda
    owner OLARAK KALIRKEN, BASKA bir tenant'ta staff olabilmeli (gorev
    ozetindeki "kendi tenant'i" ile "su an calistigi isletme" ayrimi)."""
    db = SessionLocal()
    tenant_own = Tenant(name="Own Tenant")
    tenant_other = Tenant(name="Other Tenant")
    db.add_all([tenant_own, tenant_other])
    db.flush()
    staff_row = StaffMember(tenant_id=tenant_other.id, name="Staff Row")
    user = User(
        tenant_id=tenant_own.id,
        email=f"dual-role-{uuid.uuid4().hex}@example.com",
        password_hash="not-a-real-hash",
        role="owner",
    )
    db.add_all([staff_row, user])
    db.commit()
    db.refresh(staff_row)
    db.refresh(user)

    try:
        db.add(TenantMembership(user_id=user.id, tenant_id=tenant_own.id, role="owner"))
        db.commit()

        db.add(
            TenantMembership(
                user_id=user.id,
                tenant_id=tenant_other.id,
                role="staff",
                staff_member_id=staff_row.id,
            )
        )
        db.commit()  # IntegrityError firlatmamali
    finally:
        db.rollback()
        db.query(Tenant).filter(Tenant.id.in_([tenant_own.id, tenant_other.id])).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def test_staff_invitation_can_be_created(fixtures):
    db, tenant_a, _tenant_b, user, *_ = fixtures
    invitation = StaffInvitation(
        tenant_id=tenant_a.id,
        invited_by_user_id=user.id,
        phone="+905551234567",
        token_hash="not-a-real-hash",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)

    assert invitation.status == "pending"


def test_only_one_pending_invitation_per_tenant_and_phone(fixtures):
    db, tenant_a, _tenant_b, user, *_ = fixtures
    phone = "+905551234568"
    db.add(
        StaffInvitation(
            tenant_id=tenant_a.id,
            invited_by_user_id=user.id,
            phone=phone,
            token_hash="hash-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    db.commit()

    db.add(
        StaffInvitation(
            tenant_id=tenant_a.id,
            invited_by_user_id=user.id,
            phone=phone,
            token_hash="hash-2",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_a_revoked_invitation_does_not_block_a_new_pending_one(fixtures):
    db, tenant_a, _tenant_b, user, *_ = fixtures
    phone = "+905551234569"
    db.add(
        StaffInvitation(
            tenant_id=tenant_a.id,
            invited_by_user_id=user.id,
            phone=phone,
            status="revoked",
            token_hash="hash-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    db.commit()

    db.add(
        StaffInvitation(
            tenant_id=tenant_a.id,
            invited_by_user_id=user.id,
            phone=phone,
            token_hash="hash-2",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    db.commit()  # IntegrityError firlatmamali


def test_invalid_invitation_status_is_rejected(fixtures):
    db, tenant_a, _tenant_b, user, *_ = fixtures
    db.add(
        StaffInvitation(
            tenant_id=tenant_a.id,
            invited_by_user_id=user.id,
            phone="+905551234570",
            status="not-a-real-status",
            token_hash="hash-1",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_staff_service_assignment_can_be_created_within_the_same_tenant(fixtures):
    db, tenant_a, _tenant_b, _user, staff_a, _staff_b, service_a, _service_b = fixtures
    assignment = StaffServiceAssignment(
        tenant_id=tenant_a.id, staff_member_id=staff_a.id, service_id=service_a.id
    )
    db.add(assignment)
    db.commit()  # IntegrityError firlatmamali


def test_staff_service_assignment_rejects_cross_tenant_pairing(fixtures):
    db, tenant_a, _tenant_b, _user, staff_a, _staff_b, _service_a, service_b = fixtures
    assignment = StaffServiceAssignment(
        tenant_id=tenant_a.id, staff_member_id=staff_a.id, service_id=service_b.id
    )
    db.add(assignment)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_staff_service_assignment_is_unique_per_staff_and_service(fixtures):
    db, tenant_a, _tenant_b, _user, staff_a, _staff_b, service_a, _service_b = fixtures
    db.add(
        StaffServiceAssignment(
            tenant_id=tenant_a.id, staff_member_id=staff_a.id, service_id=service_a.id
        )
    )
    db.commit()

    db.add(
        StaffServiceAssignment(
            tenant_id=tenant_a.id, staff_member_id=staff_a.id, service_id=service_a.id
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
