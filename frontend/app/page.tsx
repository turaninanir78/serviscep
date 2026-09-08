"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { getToken } from "@/lib/auth";

// Bu route sadece yonlendirme yapar - gercek panel ana ekrani /appointments,
// gercek auth dogrulamasi ise (app)/layout.tsx'teki guard'da yapiliyor.
// Token localStorage'da var gorunse bile gecersiz/suresi dolmus olabilir;
// bu durumda kullanici /appointments'a gider ama oradaki guard onu tekrar
// /login'e atar.
export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const token = getToken();
    router.replace(token ? "/appointments" : "/login");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
    </div>
  );
}
