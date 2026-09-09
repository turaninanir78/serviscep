"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";

// Bu route sadece yonlendirme yapar - gercek panel ana ekrani /appointments,
// gercek auth dogrulamasi ise (app)/layout.tsx'teki guard'da yapiliyor. Auth
// httpOnly cookie ile tasindigi icin JS token'in var olup olmadigini
// okuyamaz - tek yol, cookie'yi otomatik gonderen bu istegin sonucuna
// bakmak: basarili -> girilmis, 401 -> girilmemis.
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;

    api
      .getMyTenant()
      .then(() => {
        if (!cancelled) router.replace("/appointments");
      })
      .catch(() => {
        if (!cancelled) router.replace("/login");
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
    </div>
  );
}
