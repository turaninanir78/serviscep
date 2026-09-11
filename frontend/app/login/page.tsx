"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";

export default function LoginPage() {
  const router = useRouter();
  const [emailOrPhone, setEmailOrPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.login(emailOrPhone, password);
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
        <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Giriş Yap</h1>

        <div className="space-y-1">
          <label htmlFor="emailOrPhone" className="block text-sm text-zinc-700 dark:text-zinc-300">
            E-posta veya Telefon
          </label>
          <input
            id="emailOrPhone"
            type="text"
            required
            autoComplete="username"
            value={emailOrPhone}
            onChange={(e) => setEmailOrPhone(e.target.value)}
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
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
          <a href="/forgot-password" className="block text-right text-xs text-zinc-500 underline dark:text-zinc-400">
            Şifremi unuttum
          </a>
        </div>

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
        >
          {submitting ? "Giriş yapılıyor..." : "Giriş Yap"}
        </button>

        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Hesabınız yok mu?{" "}
          <a href="/register" className="underline">
            Kayıt olun
          </a>
        </p>
      </form>
    </div>
  );
}
