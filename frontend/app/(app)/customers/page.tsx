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
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
