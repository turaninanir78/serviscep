"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { api, ApiError } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [tenantName, setTenantName] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login");
      return;
    }
    setReady(true);

    api
      .getMyTenant(token)
      .then((tenant) => setTenantName(tenant.name))
      .catch((err) => {
        if (err instanceof ApiError && err.status === 401) {
          clearToken();
          router.replace("/login");
        }
        // Firma adi alinamasa da (gecici bir hata olabilir) token gecerliyse
        // sayfa icerigi calismaya devam eder - basliktaki isim opsiyoneldir.
      });
  }, [router]);

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  if (!ready) {
    return null;
  }

  return (
    <div className="flex min-h-screen flex-col bg-zinc-50 dark:bg-black">
      <header className="flex items-center justify-between border-b border-zinc-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-950">
        <span className="font-semibold text-black dark:text-zinc-50">
          {tenantName ?? "ServisCep Panel"}
        </span>
        <button
          onClick={handleLogout}
          className="rounded border border-zinc-300 px-3 py-1.5 text-sm text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
        >
          Çıkış Yap
        </button>
      </header>
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
