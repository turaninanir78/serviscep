"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { LegalDocumentModal } from "@/components/LegalDocumentModal";
import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { LegalDocument, PendingStaffInvitation } from "@/lib/types";

const NAV_LINKS = [
  { href: "/appointments", label: "Randevular" },
  { href: "/staff", label: "Personel" },
  { href: "/services", label: "Hizmetler" },
  { href: "/availability", label: "Çalışma Planı" },
  { href: "/customers", label: "Müşteriler" },
  { href: "/profile", label: "Hesabım" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [tenantName, setTenantName] = useState<string | null>(null);
  const [pendingDocuments, setPendingDocuments] = useState<LegalDocument[]>([]);
  const [viewingDocumentType, setViewingDocumentType] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [pendingInvitations, setPendingInvitations] = useState<PendingStaffInvitation[]>([]);
  const [invitationError, setInvitationError] = useState<string | null>(null);
  const [respondingInvitationId, setRespondingInvitationId] = useState<number | null>(null);

  function loadPendingInvitations() {
    api
      .getPendingInvitationsForMe()
      .then(setPendingInvitations)
      .catch(() => {
        // Bekleyen davet YOKSA veya gecici bir hata olursa kullaniciyi
        // panelden ALIKOYMUYORUZ - bu tamamen opsiyonel bir bildirim.
      });
  }

  useEffect(() => {
    let cancelled = false;

    // Panel icerigi, /tenants/me BASARIYLA donene kadar hic gosterilmez.
    // Auth artik httpOnly cookie ile tasindigi icin JS'in "token var mi"
    // diye senkron bir on-kontrol yapmasi mumkun degil (cookie okunamaz) -
    // tek yol, cookie'yi otomatik gonderen bu istegin basarili olup
    // olmadigina bakmak. Basarisiz olursa (401 dahil herhangi bir hata)
    // /login'e yonlendirilir.
    api
      .getMyTenant()
      .then(async (tenant) => {
        if (cancelled) return;
        setTenantName(tenant.name);

        // Bir hukuki dokuman yeni bir versiyona guncellenmisse (bkz.
        // backend/app/legal.py), kullaniciyi panele sokmadan once
        // onaylatmasi gerekiyor - basit bir tetikleme mantigi: durum
        // alinamazsa (orn. gecici bir hata) kullaniciyi KILITLEMIYORUZ,
        // sessizce devam ediyoruz.
        try {
          const status = await api.getConsentStatus();
          if (!cancelled) setPendingDocuments(status.pending_documents);
        } catch {
          // yut - asagida aciklandigi gibi
        }

        loadPendingInvitations();
        if (!cancelled) setReady(true);
      })
      .catch(() => {
        if (cancelled) return;
        router.replace("/login");
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  async function handleLogout() {
    try {
      // Cookie httpOnly oldugu icin JS onu temizleyemez - backend'in
      // Set-Cookie ile expire etmesi gerekir.
      await api.logout();
    } finally {
      router.replace("/login");
    }
  }

  async function handleAcceptInvitation(invitation: PendingStaffInvitation) {
    setInvitationError(null);
    setRespondingInvitationId(invitation.id);
    try {
      await api.acceptStaffInvitation(invitation.id);
      // Aktif isletme baglami degisti (bkz. backend/app/security.py::
      // _resolve_auth_context) - baslikta gorunen isletme adini
      // GUNCELLEMEK icin tekrar cekiyoruz, ayrica giris yapmaya gerek yok.
      const tenant = await api.getMyTenant();
      setTenantName(tenant.name);
      loadPendingInvitations();
    } catch (err) {
      setInvitationError(describeApiError(err));
    } finally {
      setRespondingInvitationId(null);
    }
  }

  async function handleDeclineInvitation(invitation: PendingStaffInvitation) {
    setInvitationError(null);
    setRespondingInvitationId(invitation.id);
    try {
      await api.declineStaffInvitation(invitation.id);
      loadPendingInvitations();
    } catch (err) {
      setInvitationError(describeApiError(err));
    } finally {
      setRespondingInvitationId(null);
    }
  }

  async function handleAcceptPendingDocuments() {
    setAccepting(true);
    try {
      for (const document of pendingDocuments) {
        await api.acceptDocument(document.id);
      }
      setPendingDocuments([]);
    } finally {
      setAccepting(false);
    }
  }

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
      </div>
    );
  }

  if (pendingDocuments.length > 0) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-black">
        <div className="w-full max-w-md space-y-4 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
          <h1 className="text-lg font-semibold text-black dark:text-zinc-50">
            Güncellenen şartları onaylayın
          </h1>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Devam etmeden önce aşağıdaki güncellenen belgeleri onaylamanız gerekiyor.
          </p>
          <ul className="space-y-1">
            {pendingDocuments.map((document) => (
              <li key={document.id}>
                <button
                  type="button"
                  onClick={() => setViewingDocumentType(document.type)}
                  className="text-sm text-black underline dark:text-zinc-50"
                >
                  {document.type} ({document.version})
                </button>
              </li>
            ))}
          </ul>
          <button
            onClick={handleAcceptPendingDocuments}
            disabled={accepting}
            className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
          >
            {accepting ? "Kaydediliyor..." : "Kabul Ediyorum"}
          </button>
          <button
            onClick={handleLogout}
            className="w-full text-sm text-zinc-500 underline dark:text-zinc-400"
          >
            Çıkış Yap
          </button>
        </div>

        {viewingDocumentType && (
          <LegalDocumentModal
            type={viewingDocumentType}
            onClose={() => setViewingDocumentType(null)}
          />
        )}
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-black">
      <header className="border-b border-zinc-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-black dark:text-zinc-50">{tenantName}</span>
          <button
            onClick={handleLogout}
            className="rounded border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
          >
            Çıkış Yap
          </button>
        </div>
        <nav className="mt-3 flex flex-wrap gap-4">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-zinc-600 hover:text-black hover:underline dark:text-zinc-400 dark:hover:text-zinc-50"
            >
              {link.label}
            </Link>
          ))}
        </nav>
      </header>

      {pendingInvitations.length > 0 && (
        <div className="space-y-2 border-b border-amber-200 bg-amber-50 px-6 py-3 dark:border-amber-900 dark:bg-amber-950">
          {invitationError && (
            <p className="text-sm text-red-600 dark:text-red-400">{invitationError}</p>
          )}
          {pendingInvitations.map((invitation) => (
            <div
              key={invitation.id}
              className="flex flex-wrap items-center justify-between gap-2 text-sm text-amber-900 dark:text-amber-200"
            >
              <span>
                <strong>{invitation.tenant_name}</strong> sizi personel olarak davet etti.
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => handleAcceptInvitation(invitation)}
                  disabled={respondingInvitationId === invitation.id}
                  className="rounded bg-black px-3 py-1 text-xs font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
                >
                  Kabul Et
                </button>
                <button
                  onClick={() => handleDeclineInvitation(invitation)}
                  disabled={respondingInvitationId === invitation.id}
                  className="rounded border border-amber-300 px-3 py-1 text-xs text-amber-900 disabled:opacity-50 dark:border-amber-800 dark:text-amber-200"
                >
                  Reddet
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
