"use client";

import { useEffect, useState, type FormEvent } from "react";

import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { User } from "@/lib/types";

type EmailStep = { name: "view" } | { name: "enter-email" } | { name: "enter-code"; email: string };

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [step, setStep] = useState<EmailStep>({ name: "view" });
  const [emailInput, setEmailInput] = useState("");
  const [code, setCode] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api
      .getMe()
      .then(setUser)
      .catch((err) => setLoadError(describeApiError(err)));
  }, []);

  async function handleRequestOtp(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await api.requestAddEmailOtp(emailInput);
      setStep({ name: "enter-code", email: emailInput });
    } catch (err) {
      setFormError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerifyCode(event: FormEvent) {
    if (step.name !== "enter-code") return;
    event.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      const updated = await api.verifyAddEmail(step.email, code);
      setUser(updated);
      setStep({ name: "view" });
      setCode("");
      setEmailInput("");
    } catch (err) {
      setFormError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  if (loadError) {
    return <p className="text-sm text-red-600 dark:text-red-400">{loadError}</p>;
  }

  if (!user) {
    return <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>;
  }

  return (
    <div className="max-w-md space-y-6">
      <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Hesap Bilgileri</h1>

      <div className="space-y-2 rounded-lg border border-zinc-200 bg-white p-4 text-sm dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex justify-between">
          <span className="text-zinc-500 dark:text-zinc-400">Telefon</span>
          <span className="text-black dark:text-zinc-50">{user.phone ?? "—"}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500 dark:text-zinc-400">E-posta</span>
          <span className="text-black dark:text-zinc-50">{user.email ?? "Eklenmemiş"}</span>
        </div>
      </div>

      {user.email === null && step.name === "view" && (
        <button
          onClick={() => setStep({ name: "enter-email" })}
          className="rounded bg-black px-3 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
        >
          E-posta Ekle
        </button>
      )}

      {step.name === "enter-email" && (
        <form onSubmit={handleRequestOtp} className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="space-y-1">
            <label htmlFor="newEmail" className="block text-sm text-zinc-700 dark:text-zinc-300">
              E-posta Adresi
            </label>
            <input
              id="newEmail"
              type="email"
              required
              autoComplete="email"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </div>

          {formError && <p className="text-sm text-red-600 dark:text-red-400">{formError}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {submitting ? "Kod gönderiliyor..." : "Kod Gönder"}
            </button>
            <button
              type="button"
              onClick={() => setStep({ name: "view" })}
              className="rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            >
              Vazgeç
            </button>
          </div>
        </form>
      )}

      {step.name === "enter-code" && (
        <form onSubmit={handleVerifyCode} className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {step.email} adresine gönderilen kodu girin.
          </p>
          <div className="space-y-1">
            <label htmlFor="emailOtp" className="block text-sm text-zinc-700 dark:text-zinc-300">
              Doğrulama Kodu
            </label>
            <input
              id="emailOtp"
              type="text"
              inputMode="numeric"
              required
              autoComplete="one-time-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </div>

          {formError && <p className="text-sm text-red-600 dark:text-red-400">{formError}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={submitting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {submitting ? "Doğrulanıyor..." : "Doğrula"}
            </button>
            <button
              type="button"
              onClick={() => setStep({ name: "view" })}
              className="rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            >
              Vazgeç
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
