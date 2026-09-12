"use client";

import { useEffect, useState, type FormEvent } from "react";

import { api, ApiError } from "@/lib/api";
import { COUNTRY_CODES, DEFAULT_COUNTRY_CODE } from "@/lib/countryCodes";
import { describeApiError } from "@/lib/errors";
import type { StaffInvitation, StaffMember, StaffMembership, StaffPermissionKey } from "@/lib/types";

const PERMISSION_LABELS: Record<StaffPermissionKey, string> = {
  can_view_customers: "Müşterileri Görüntüleme",
  can_create_appointments: "Randevu Oluşturma",
  can_cancel_appointments: "Randevu İptal Etme",
  can_confirm_complete_appointments: "Randevu Onaylama / Tamamlama",
  can_manage_availability: "Çalışma Planını Oluşturma / Değiştirme",
  can_manage_services: "Hizmetleri Görüntüleme / Düzenleme",
};

const PERMISSION_KEYS = Object.keys(PERMISSION_LABELS) as StaffPermissionKey[];

const INVITATION_STATUS_LABELS: Record<string, string> = {
  pending: "Beklemede",
  accepted: "Kabul edildi",
  revoked: "İptal edildi / Reddedildi",
  expired: "Süresi doldu",
};

export default function StaffPage() {
  const [staffMembers, setStaffMembers] = useState<StaffMember[] | null>(null);
  const [invitations, setInvitations] = useState<StaffInvitation[] | null>(null);
  const [isOwner, setIsOwner] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const [inviteCountryCode, setInviteCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [invitePhone, setInvitePhone] = useState("");
  const [inviting, setInviting] = useState(false);
  const [inviteError, setInviteError] = useState<string | null>(null);

  const [permissionsFor, setPermissionsFor] = useState<StaffMember | null>(null);
  const [membership, setMembership] = useState<StaffMembership | "not-linked" | null>(null);
  const [permissionsError, setPermissionsError] = useState<string | null>(null);
  const [savingPermissions, setSavingPermissions] = useState(false);

  function loadStaffMembers() {
    api
      .getStaffMembers()
      .then(setStaffMembers)
      .catch((err) => setError(describeApiError(err)));
  }

  function loadInvitations() {
    api
      .getSentStaffInvitations()
      .then(setInvitations)
      .catch(() => {
        // Personel olmayan (staff rolündeki) bir kullanıcı bu sayfayı
        // görse bile (nav linki her zaman gösteriliyor) davet listesi
        // 403 dönebilir - sayfanın geri kalanını KİLİTLEMİYORUZ.
      });
  }

  useEffect(() => {
    loadStaffMembers();
    loadInvitations();
    // Personel ekleme/davet/duzenleme HER ZAMAN owner'a ozel (bkz.
    // backend/app/permissions.py::require_owner) - burada SADECE bu
    // bolumleri staff rolundeki bir kullanicidan gizlemek icin (backend
    // zaten bagimsiz olarak reddediyor, bu sadece kafa karistirici bir
    // "yetkiniz yok" hatasi almalarini onluyor).
    api
      .getMyTenant()
      .then((tenant) => setIsOwner(tenant.my_role === "owner"))
      .catch(() => {
        // olmazsa varsayilan (true) ile devam - en kotu ihtimalle owner
        // olmayan biri bir butonu gorup backend'den 403 alir.
      });
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    setError(null);
    setSubmitting(true);
    try {
      await api.createStaffMember({ name });
      setName("");
      loadStaffMembers();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(staff: StaffMember) {
    setError(null);
    setTogglingId(staff.id);
    try {
      await api.updateStaffMember(staff.id, { is_active: !staff.is_active });
      loadStaffMembers();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setTogglingId(null);
    }
  }

  async function handleInvite(event: FormEvent) {
    event.preventDefault();
    setInviteError(null);
    setInviting(true);
    try {
      await api.inviteStaffMember(inviteCountryCode, invitePhone);
      setInvitePhone("");
      loadInvitations();
    } catch (err) {
      setInviteError(describeApiError(err));
    } finally {
      setInviting(false);
    }
  }

  async function handleRevokeInvitation(invitation: StaffInvitation) {
    try {
      await api.revokeStaffInvitation(invitation.id);
      loadInvitations();
    } catch (err) {
      setInviteError(describeApiError(err));
    }
  }

  async function openPermissions(staff: StaffMember) {
    setPermissionsFor(staff);
    setMembership(null);
    setPermissionsError(null);
    try {
      const result = await api.getStaffMembership(staff.id);
      setMembership(result);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setMembership("not-linked");
      } else {
        setPermissionsError(describeApiError(err));
      }
    }
  }

  function closePermissions() {
    setPermissionsFor(null);
    setMembership(null);
    setPermissionsError(null);
  }

  async function handleTogglePermission(key: StaffPermissionKey) {
    if (membership === null || membership === "not-linked" || permissionsFor === null) return;
    setSavingPermissions(true);
    setPermissionsError(null);
    try {
      const updated = await api.updateStaffPermissions(permissionsFor.id, {
        [key]: !membership[key],
      });
      setMembership(updated);
    } catch (err) {
      setPermissionsError(describeApiError(err));
    } finally {
      setSavingPermissions(false);
    }
  }

  async function handleGrantAll() {
    if (permissionsFor === null) return;
    setSavingPermissions(true);
    setPermissionsError(null);
    try {
      const allTrue = Object.fromEntries(PERMISSION_KEYS.map((key) => [key, true]));
      const updated = await api.updateStaffPermissions(permissionsFor.id, allTrue);
      setMembership(updated);
    } catch (err) {
      setPermissionsError(describeApiError(err));
    } finally {
      setSavingPermissions(false);
    }
  }

  async function handleEndMembership() {
    if (permissionsFor === null) return;
    setSavingPermissions(true);
    setPermissionsError(null);
    try {
      await api.endStaffMembership(permissionsFor.id);
      closePermissions();
      loadStaffMembers();
    } catch (err) {
      setPermissionsError(describeApiError(err));
      setSavingPermissions(false);
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Personel</h1>

      {isOwner && (
        <section className="space-y-3">
          <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Yerel Personel Ekle
          </h2>
          <form onSubmit={handleSubmit} className="flex items-end gap-3">
            <div className="space-y-1">
              <label htmlFor="staffName" className="block text-sm text-zinc-700 dark:text-zinc-300">
                Ad
              </label>
              <input
                id="staffName"
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {submitting ? "Ekleniyor..." : "Ekle"}
            </button>
          </form>
        </section>
      )}

      {isOwner && (
        <section className="space-y-3 border-t border-zinc-200 pt-6 dark:border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Telefon ile Personel Davet Et
          </h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Davet edilecek kişinin Servisçep&apos;e kayıtlı olması gerekir. Davet kabul edilince
            kişi işletmenizin personeli olur ve siz ona yetki verebilirsiniz.
          </p>
          <form onSubmit={handleInvite} className="flex items-end gap-2">
            <select
              value={inviteCountryCode}
              onChange={(e) => setInviteCountryCode(e.target.value)}
              className="rounded border border-zinc-300 px-2 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            >
              {COUNTRY_CODES.map((c) => (
                <option key={c.code} value={c.code}>
                  {c.flag} {c.code}
                </option>
              ))}
            </select>
            <input
              type="tel"
              required
              placeholder="5XX XXX XX XX"
              value={invitePhone}
              onChange={(e) => setInvitePhone(e.target.value)}
              className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
            <button
              type="submit"
              disabled={inviting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {inviting ? "Gönderiliyor..." : "Davet Gönder"}
            </button>
          </form>
          {inviteError && <p className="text-sm text-red-600 dark:text-red-400">{inviteError}</p>}

          {invitations !== null && invitations.length > 0 && (
            <ul className="space-y-1 text-sm">
              {invitations.map((invitation) => (
                <li
                  key={invitation.id}
                  className="flex items-center justify-between rounded border border-zinc-200 px-3 py-2 dark:border-zinc-800"
                >
                  <span className="text-black dark:text-zinc-50">
                    {invitation.phone} —{" "}
                    <span className="text-zinc-500 dark:text-zinc-400">
                      {INVITATION_STATUS_LABELS[invitation.status] ?? invitation.status}
                    </span>
                  </span>
                  {invitation.status === "pending" && (
                    <button
                      onClick={() => handleRevokeInvitation(invitation)}
                      className="text-xs text-red-600 underline dark:text-red-400"
                    >
                      İptal Et
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {staffMembers === null && !error && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
      )}

      {staffMembers !== null && staffMembers.length === 0 && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Henüz personel yok.</p>
      )}

      {staffMembers !== null && staffMembers.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="w-full min-w-[560px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-800 dark:bg-zinc-900">
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Ad</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Durum</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {staffMembers.map((staff) => (
                <tr
                  key={staff.id}
                  className="border-b border-zinc-100 last:border-0 dark:border-zinc-900"
                >
                  <td className="px-4 py-2 text-black dark:text-zinc-50">{staff.name}</td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {staff.is_active ? "Aktif" : "Pasif"}
                  </td>
                  <td className="px-4 py-2 text-right space-x-2">
                    {isOwner && (
                      <>
                        <button
                          onClick={() => openPermissions(staff)}
                          className="rounded border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                        >
                          Yetkiler
                        </button>
                        <button
                          onClick={() => handleToggle(staff)}
                          disabled={togglingId === staff.id}
                          className="rounded border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                        >
                          {staff.is_active ? "Pasif Yap" : "Aktif Yap"}
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {permissionsFor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
          <div className="w-full max-w-sm space-y-4 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
            <h2 className="text-lg font-semibold text-black dark:text-zinc-50">
              {permissionsFor.name} — Yetkiler
            </h2>

            {membership === null && !permissionsError && (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
            )}

            {membership === "not-linked" && (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">
                Bu personel davetle eklenmemiş (yerel kayıt) — düzenlenecek bir yetkisi yok.
              </p>
            )}

            {membership !== null && membership !== "not-linked" && (
              <div className="space-y-3">
                <button
                  onClick={handleGrantAll}
                  disabled={savingPermissions}
                  className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
                >
                  Tüm Yetkileri Ver
                </button>

                <div className="space-y-2">
                  {PERMISSION_KEYS.map((key) => (
                    <label key={key} className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
                      <input
                        type="checkbox"
                        checked={membership[key]}
                        disabled={savingPermissions}
                        onChange={() => handleTogglePermission(key)}
                      />
                      {PERMISSION_LABELS[key]}
                    </label>
                  ))}
                </div>

                <button
                  onClick={handleEndMembership}
                  disabled={savingPermissions}
                  className="w-full rounded border border-red-300 px-3 py-2 text-sm text-red-600 disabled:opacity-50 dark:border-red-900 dark:text-red-400"
                >
                  İşten Çıkar
                </button>
              </div>
            )}

            {permissionsError && (
              <p className="text-sm text-red-600 dark:text-red-400">{permissionsError}</p>
            )}

            <button
              onClick={closePermissions}
              className="w-full text-sm text-zinc-500 underline dark:text-zinc-400"
            >
              Kapat
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
