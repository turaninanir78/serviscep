"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { clearToken, getToken } from "@/lib/auth";

const NAV_LINKS = [
  { href: "/appointments", label: "Randevular" },
  { href: "/staff", label: "Personel" },
  { href: "/services", label: "Hizmetler" },
  { href: "/availability", label: "Çalışma Saatleri" },
  { href: "/customers", label: "Müşteriler" },
];

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

    let cancelled = false;

    // Panel icerigi, /tenants/me BASARIYLA donene kadar hic gosterilmez -
    // token localStorage'da var gorunse bile gecersiz/suresi dolmus
    // olabilir. Basarisiz olursa (401 dahil herhangi bir hata) token
    // temizlenip /login'e yonlendirilir.
    api
      .getMyTenant(token)
      .then((tenant) => {
        if (cancelled) return;
        setTenantName(tenant.name);
        setReady(true);
      })
      .catch(() => {
        if (cancelled) return;
        clearToken();
        router.replace("/login");
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  function handleLogout() {
    clearToken();
    router.replace("/login");
  }

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
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
      <main className="flex-1 p-6">{children}</main>
    </div>
  );
}
