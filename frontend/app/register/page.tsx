"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { setToken } from "@/lib/auth";
import { describeApiError } from "@/lib/errors";

export default function RegisterPage() {
  const router = useRouter();
  const [tenantName, setTenantName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { access_token } = await api.register(tenantName, email, password);
      setToken(access_token);
      router.push("/appointments");
    } catch (err) {
      setError(describeApiError(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-black">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
      >
        <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Firma Kaydı</h1>

        <div className="space-y-1">
          <label htmlFor="tenantName" className="block text-sm text-zinc-700 dark:text-zinc-300">
            Firma Adı
          </label>
          <input
            id="tenantName"
            type="text"
            required
            value={tenantName}
            onChange={(e) => setTenantName(e.target.value)}
            className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="email" className="block text-sm text-zinc-700 dark:text-zinc-300">
            E-posta
          </label>
          <input
            id="email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
        </div>

        <div className="space-y-1">
          <label htmlFor="password" className="block text-sm text-zinc-700 dark:text-zinc-300">
            Şifre
          </label>
          <input
            id="password"
            type="password"
            required
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
        </div>

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          {submitting ? "Kaydediliyor..." : "Kayıt Ol"}
        </button>

        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Zaten hesabınız var mı?{" "}
          <a href="/login" className="underline">
            Giriş yapın
          </a>
        </p>
      </form>
    </div>
  );
}
