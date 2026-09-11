"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/dates";
import { describeApiError } from "@/lib/errors";
import type { Customer } from "@/lib/types";

// Tenant timezone'i /tenants/me'den gelene kadar (ilk yukleme anindaki
// kisa an) kullanilacak baslangic degeri - backend'in kolon varsayilaniyla
// ayni (bkz. backend/app/models - Tenant.timezone server_default).
const DEFAULT_TIMEZONE = "Europe/Istanbul";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<Customer[] | null>(null);
  const [timezone, setTimezone] = useState(DEFAULT_TIMEZONE);
  const [error, setError] = useState<string | null>(null);
  const [confirmingCustomer, setConfirmingCustomer] = useState<Customer | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getCustomers(), api.getMyTenant()])
      .then(([customersData, tenant]) => {
        setCustomers(customersData);
        setTimezone(tenant.timezone);
      })
      .catch((err) => setError(describeApiError(err)));
  }, []);

  function formatDate(iso: string): string {
    return formatDateTime(iso, timezone);
  }

  async function handleConfirmDeletion() {
    if (!confirmingCustomer) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await api.requestCustomerDeletion(confirmingCustomer.id);
      // Backend, silinen musteriyi GET /customers listesinden zaten
      // hariç tutuyor - burada da ayni sekilde listeden cikariyoruz,
      // sayfayi yeniden yuklemeye gerek yok.
      setCustomers((prev) => (prev ?? []).filter((c) => c.id !== confirmingCustomer.id));
      setConfirmingCustomer(null);
    } catch (err) {
      setDeleteError(describeApiError(err));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Müşteriler</h1>

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {customers === null && !error && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
      )}

      {customers !== null && customers.length === 0 && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Henüz müşteri yok.</p>
      )}

      {customers !== null && customers.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="w-full min-w-[480px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-800 dark:bg-zinc-900">
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Ad</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">
                  WhatsApp Numarası
                </th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">
                  İlk Görülme
                </th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">
                  İşlemler
                </th>
              </tr>
            </thead>
            <tbody>
              {customers.map((customer) => (
                <tr
                  key={customer.id}
                  className="border-b border-zinc-100 last:border-0 dark:border-zinc-900"
                >
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {customer.display_name || "-"}
                  </td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {customer.whatsapp_number}
                  </td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {formatDate(customer.first_seen_at)}
                  </td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => {
                        setDeleteError(null);
                        setConfirmingCustomer(customer);
                      }}
                      className="text-sm text-red-600 underline hover:text-red-700 dark:text-red-400"
                    >
                      Veriyi Sil
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {confirmingCustomer && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => !deleting && setConfirmingCustomer(null)}
        >
          <div
            className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 dark:bg-zinc-950"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold text-black dark:text-zinc-50">
              Müşteri Verisini Sil
            </h2>
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              <strong>{confirmingCustomer.display_name || confirmingCustomer.whatsapp_number}</strong>{" "}
              adlı müşterinin kişisel verileri (isim, telefon numarası) kalıcı olarak
              anonimleştirilecek.
            </p>
            <p className="text-sm font-medium text-red-600 dark:text-red-400">
              Bu işlem GERİ ALINAMAZ.
            </p>

            {deleteError && (
              <p className="text-sm text-red-600 dark:text-red-400">{deleteError}</p>
            )}

            <div className="flex gap-2">
              <button
                onClick={handleConfirmDeletion}
                disabled={deleting}
                className="flex-1 rounded bg-red-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
              >
                {deleting ? "Siliniyor..." : "Evet, Kalıcı Olarak Sil"}
              </button>
              <button
                onClick={() => setConfirmingCustomer(null)}
                disabled={deleting}
                className="flex-1 rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300"
              >
                Vazgeç
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
