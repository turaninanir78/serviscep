"""GOREV: Personel Davet + Aktif Isletme Baglami + Granuler Yetkiler
(Faz 1) testleri.

Akis: owner (isletme A) baska bir kayitli kullaniciyi (kendi ayri
isletmesi olan biri) telefonla davet eder -> davet edilen kendi
hesabiyla giris yapip bekleyen daveti gorup kabul eder -> artik isletme
A'da bir "staff" TenantMembership'i vardir, AYNI JWT ile (yeniden giris
YAPMADAN) bir sonraki istekte otomatik isletme A baglaminda calisir.
Yetkiler (can_view_customers vb.) owner tarafindan acilip kapanana
kadar KAPALI baslar - klinik/berber senaryosundaki esneklik boyle
saglaniyor (bkz. gorev ozeti).

Diger testlerle ayni yaklasim: calisan sunucuya gercek HTTP istekleri,
DB temizligi tenant/telefon uzerinden manuel.
"""
import random
import string

import requests

from app.db import SessionLocal
from app.models import Tenant, User
from app.phone import normalize_phone

BASE_URL = "http://localhost:8000"
COUNTRY_CODE = "+90"


def _random_phone_raw() -> str:
    return "05" + "".join(random.choices(string.digits, k=9))


def _register_phone_only_user(phone_raw: str, tenant_name: str, password: str) -> requests.Session:
    session = requests.Session()
    otp_res = session.post(
        f"{BASE_URL}/auth/register/request-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
    )
    assert otp_res.status_code == 200, otp_res.text
    code = otp_res.json()["debug_code"]

    verify_res = session.post(
        f"{BASE_URL}/auth/register/verify-otp",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw, "code": code},
    )
    assert verify_res.status_code == 200, verify_res.text
    registration_token = verify_res.json()["registration_token"]

    complete_res = session.post(
        f"{BASE_URL}/auth/register/complete",
        json={
            "registration_token": registration_token,
            "tenant_name": tenant_name,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert complete_res.status_code == 201, complete_res.text
    return session


def _cleanup_by_phone(phone_raw: str) -> None:
    normalized = normalize_phone(COUNTRY_CODE, phone_raw)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.phone == normalized).first()
        if user is not None:
            db.query(Tenant).filter(Tenant.id == user.tenant_id).delete()
            db.commit()
    finally:
        db.close()


def _invite(owner_session: requests.Session, phone_raw: str) -> requests.Response:
    return owner_session.post(
        f"{BASE_URL}/staff_invitations",
        json={"country_code": COUNTRY_CODE, "phone_number": phone_raw},
    )


class _TwoTenants:
    """Ortak kurulum: isletme A (owner_session) ve kendi ayri isletmesi
    olan bir kullanici (employee_session, employee_phone) - ikincisi
    isletme A'ya davet edilecek."""

    def __init__(self):
        self.owner_phone = _random_phone_raw()
        self.employee_phone = _random_phone_raw()
        self.owner_session = _register_phone_only_user(
            self.owner_phone, "Davet Test Isletmesi A", "Owner-pw1!"
        )
        self.employee_session = _register_phone_only_user(
            self.employee_phone, "Davet Test Isletmesi B (kendi)", "Employee-pw1!"
        )

    def cleanup(self) -> None:
        _cleanup_by_phone(self.owner_phone)
        _cleanup_by_phone(self.employee_phone)


def test_owner_can_invite_existing_registered_user_by_phone():
    ctx = _TwoTenants()
    try:
        res = _invite(ctx.owner_session, ctx.employee_phone)
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["status"] == "pending"
        assert body["phone"] == normalize_phone(COUNTRY_CODE, ctx.employee_phone)
    finally:
        ctx.cleanup()


def test_inviting_unregistered_phone_returns_clear_404():
    ctx = _TwoTenants()
    try:
        unregistered_phone = _random_phone_raw()
        res = _invite(ctx.owner_session, unregistered_phone)
        assert res.status_code == 404
    finally:
        ctx.cleanup()


def test_owner_cannot_invite_self():
    ctx = _TwoTenants()
    try:
        res = _invite(ctx.owner_session, ctx.owner_phone)
        assert res.status_code == 400
    finally:
        ctx.cleanup()


def test_duplicate_pending_invitation_returns_409():
    ctx = _TwoTenants()
    try:
        first = _invite(ctx.owner_session, ctx.employee_phone)
        assert first.status_code == 201
        second = _invite(ctx.owner_session, ctx.employee_phone)
        assert second.status_code == 409
    finally:
        ctx.cleanup()


def test_non_owner_staff_cannot_send_invitations():
    """Personel ekleme/davet HER ZAMAN owner'a ozel - bkz. gorev ozeti."""
    ctx = _TwoTenants()
    try:
        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]
        accept_res = ctx.employee_session.post(
            f"{BASE_URL}/staff_invitations/{invitation_id}/accept"
        )
        assert accept_res.status_code == 200, accept_res.text

        third_phone = _random_phone_raw()
        # employee_session artik isletme A'da "staff" - baska birini
        # davet etmeye calissin, owner olmadigi icin reddedilmeli.
        res = _invite(ctx.employee_session, third_phone)
        assert res.status_code == 403
    finally:
        ctx.cleanup()


def test_invited_user_sees_pending_invitation_with_tenant_name():
    ctx = _TwoTenants()
    try:
        _invite(ctx.owner_session, ctx.employee_phone)
        res = ctx.employee_session.get(f"{BASE_URL}/staff_invitations/pending")
        assert res.status_code == 200
        pending = res.json()
        assert len(pending) == 1
        assert pending[0]["tenant_name"] == "Davet Test Isletmesi A"
    finally:
        ctx.cleanup()


def test_accepting_invitation_switches_active_tenant_without_relogin():
    """Davet kabul edilince, AYNI oturum (yeniden giris yapmadan) bir
    sonraki istekte otomatik isletme A baglaminda calismali - bkz.
    app/security.py::_resolve_auth_context (JWT'deki tenant_id degil,
    TenantMembership her istekte taze okunuyor)."""
    ctx = _TwoTenants()
    try:
        before = ctx.employee_session.get(f"{BASE_URL}/tenants/me")
        assert before.json()["name"] == "Davet Test Isletmesi B (kendi)"

        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]
        accept_res = ctx.employee_session.post(
            f"{BASE_URL}/staff_invitations/{invitation_id}/accept"
        )
        assert accept_res.status_code == 200, accept_res.text

        after = ctx.employee_session.get(f"{BASE_URL}/tenants/me")
        assert after.status_code == 200
        assert after.json()["name"] == "Davet Test Isletmesi A"
    finally:
        ctx.cleanup()


def test_staff_can_view_only_own_appointments_by_default_without_any_permission():
    """Klinik senaryosu (gorev ozeti): hekim hicbir yetkisi acilmasa bile
    en azindan KENDI randevularini gorebilmeli - bu bir izin anahtariyla
    korunmuyor, otomatik daralma."""
    ctx = _TwoTenants()
    try:
        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]
        ctx.employee_session.post(f"{BASE_URL}/staff_invitations/{invitation_id}/accept")

        res = ctx.employee_session.get(f"{BASE_URL}/appointments")
        assert res.status_code == 200
        assert res.json() == []
    finally:
        ctx.cleanup()


def test_staff_without_permission_cannot_create_appointment():
    ctx = _TwoTenants()
    try:
        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]
        accept_res = ctx.employee_session.post(
            f"{BASE_URL}/staff_invitations/{invitation_id}/accept"
        )
        staff_member_id = accept_res.json()["staff_member_id"]

        service_res = ctx.owner_session.post(
            f"{BASE_URL}/services", json={"name": "Saç Kesimi", "duration_minutes": 30}
        )
        customer_res = ctx.owner_session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905551112233"}
        )

        create_res = ctx.employee_session.post(
            f"{BASE_URL}/appointments",
            json={
                "staff_id": staff_member_id,
                "service_id": service_res.json()["id"],
                "customer_id": customer_res.json()["id"],
                "start_at": "2026-11-02T09:00:00Z",
            },
        )
        assert create_res.status_code == 403
    finally:
        ctx.cleanup()


def test_owner_grants_permission_then_staff_can_create_own_appointment_but_not_for_others():
    ctx = _TwoTenants()
    try:
        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]
        accept_res = ctx.employee_session.post(
            f"{BASE_URL}/staff_invitations/{invitation_id}/accept"
        )
        staff_member_id = accept_res.json()["staff_member_id"]

        perm_res = ctx.owner_session.patch(
            f"{BASE_URL}/staff_members/{staff_member_id}/permissions",
            json={"can_create_appointments": True},
        )
        assert perm_res.status_code == 200, perm_res.text
        assert perm_res.json()["can_create_appointments"] is True

        service_id = ctx.owner_session.post(
            f"{BASE_URL}/services", json={"name": "Sakal Tıraşı", "duration_minutes": 20}
        ).json()["id"]
        customer_id = ctx.owner_session.post(
            f"{BASE_URL}/customers", json={"whatsapp_number": "905552223344"}
        ).json()["id"]

        own_create = ctx.employee_session.post(
            f"{BASE_URL}/appointments",
            json={
                "staff_id": staff_member_id,
                "service_id": service_id,
                "customer_id": customer_id,
                "start_at": "2026-11-02T10:00:00Z",
            },
        )
        assert own_create.status_code == 201, own_create.text

        # Kendi disindaki bir staff_id icin (ornegin owner'in "Ben"
        # kaydi) randevu olusturmaya calissa bile - yetkisi olsa da
        # SADECE kendi staff_id'sine izinli.
        owner_staff_list = ctx.owner_session.get(f"{BASE_URL}/staff_members").json()
        other_staff_id = next(s["id"] for s in owner_staff_list if s["id"] != staff_member_id)

        other_create = ctx.employee_session.post(
            f"{BASE_URL}/appointments",
            json={
                "staff_id": other_staff_id,
                "service_id": service_id,
                "customer_id": customer_id,
                "start_at": "2026-11-02T11:00:00Z",
            },
        )
        assert other_create.status_code == 404
    finally:
        ctx.cleanup()


def test_staff_without_permission_cannot_view_customers():
    ctx = _TwoTenants()
    try:
        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]
        ctx.employee_session.post(f"{BASE_URL}/staff_invitations/{invitation_id}/accept")

        res = ctx.employee_session.get(f"{BASE_URL}/customers")
        assert res.status_code == 403
    finally:
        ctx.cleanup()


def test_owner_can_grant_all_permissions_individually_and_staff_gains_access():
    ctx = _TwoTenants()
    try:
        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]
        accept_res = ctx.employee_session.post(
            f"{BASE_URL}/staff_invitations/{invitation_id}/accept"
        )
        staff_member_id = accept_res.json()["staff_member_id"]

        all_permissions = {
            "can_view_customers": True,
            "can_create_appointments": True,
            "can_cancel_appointments": True,
            "can_confirm_complete_appointments": True,
            "can_manage_availability": True,
            "can_manage_services": True,
        }
        perm_res = ctx.owner_session.patch(
            f"{BASE_URL}/staff_members/{staff_member_id}/permissions", json=all_permissions
        )
        assert perm_res.status_code == 200
        assert all(perm_res.json()[k] is True for k in all_permissions)

        assert ctx.employee_session.get(f"{BASE_URL}/customers").status_code == 200
    finally:
        ctx.cleanup()


def test_declining_invitation_lets_owner_invite_again():
    ctx = _TwoTenants()
    try:
        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]

        decline_res = ctx.employee_session.post(
            f"{BASE_URL}/staff_invitations/{invitation_id}/decline"
        )
        assert decline_res.status_code == 204

        second_invite = _invite(ctx.owner_session, ctx.employee_phone)
        assert second_invite.status_code == 201
    finally:
        ctx.cleanup()


def test_user_cannot_accept_someone_elses_invitation():
    ctx = _TwoTenants()
    other_phone = _random_phone_raw()
    other_session = _register_phone_only_user(other_phone, "Alakasız Kullanıcı", "Other-pw1!")
    try:
        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]

        res = other_session.post(f"{BASE_URL}/staff_invitations/{invitation_id}/accept")
        assert res.status_code == 404
    finally:
        ctx.cleanup()
        _cleanup_by_phone(other_phone)


def test_accepting_second_invitation_while_already_staff_elsewhere_is_rejected():
    ctx = _TwoTenants()
    third_phone = _random_phone_raw()
    third_owner_session = _register_phone_only_user(third_phone, "Davet Test Isletmesi C", "Third-pw1!")
    try:
        first_invite = _invite(ctx.owner_session, ctx.employee_phone)
        ctx.employee_session.post(f"{BASE_URL}/staff_invitations/{first_invite.json()['id']}/accept")

        second_invite = _invite(third_owner_session, ctx.employee_phone)
        assert second_invite.status_code == 201
        second_accept = ctx.employee_session.post(
            f"{BASE_URL}/staff_invitations/{second_invite.json()['id']}/accept"
        )
        assert second_accept.status_code == 409
    finally:
        ctx.cleanup()
        _cleanup_by_phone(third_phone)


def test_owner_ending_membership_reverts_staff_to_their_own_tenant():
    ctx = _TwoTenants()
    try:
        invite_res = _invite(ctx.owner_session, ctx.employee_phone)
        invitation_id = invite_res.json()["id"]
        accept_res = ctx.employee_session.post(
            f"{BASE_URL}/staff_invitations/{invitation_id}/accept"
        )
        staff_member_id = accept_res.json()["staff_member_id"]

        while_employed = ctx.employee_session.get(f"{BASE_URL}/tenants/me")
        assert while_employed.json()["name"] == "Davet Test Isletmesi A"

        end_res = ctx.owner_session.post(f"{BASE_URL}/staff_members/{staff_member_id}/end-membership")
        assert end_res.status_code == 200, end_res.text
        assert end_res.json()["is_active"] is False

        after_leaving = ctx.employee_session.get(f"{BASE_URL}/tenants/me")
        assert after_leaving.json()["name"] == "Davet Test Isletmesi B (kendi)"
    finally:
        ctx.cleanup()


def test_local_unlinked_staff_member_has_no_membership_to_edit():
    """Davetsiz, sadece isim yazarak eklenen yerel bir StaffMember'in
    (bkz. gorev ozeti - "Ben" kaydi gibi) hicbir kullaniciya bagli
    olmadigi icin duzenlenecek bir yetkisi yok - 404 donmeli."""
    ctx = _TwoTenants()
    try:
        create_res = ctx.owner_session.post(
            f"{BASE_URL}/staff_members", json={"name": "Yerel Personel"}
        )
        local_staff_id = create_res.json()["id"]

        res = ctx.owner_session.get(f"{BASE_URL}/staff_members/{local_staff_id}/membership")
        assert res.status_code == 404
    finally:
        ctx.cleanup()
