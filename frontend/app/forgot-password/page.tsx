"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { COUNTRY_CODES, DEFAULT_COUNTRY_CODE } from "@/lib/countryCodes";
import { describeApiError } from "@/lib/errors";

type Channel = "sms" | "email";

type Step =
  | { name: "phone" }
  | { name: "channel"; countryCode: string; phoneNumber: string }
  | { name: "otp"; countryCode: string; phoneNumber: string; channel: Channel | null }
  | { name: "password"; resetToken: string }
  | { name: "done" };

export default function ForgotPasswordPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>({ name: "phone" });
  const [countryCode, setCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleRequestOtp(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const res = await api.requestPasswordResetOtp(countryCode, phoneNumber);
      if (res.channel_choice_required) {
        setStep({ name: "channel", countryCode, phoneNumber });
      } else {
        setStep({ name: "otp", countryCode, phoneNumber, channel: null });
      }
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handlePickChannel(channel: Channel) {
    if (step.name !== "channel") return;
    setError(null);
    setSubmitting(true);
    try {
      await api.requestPasswordResetOtp(step.countryCode, step.phoneNumber, channel);
      setStep({ name: "otp", countryCode: step.countryCode, phoneNumber: step.phoneNumber, channel });
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleVerifyOtp(event: FormEvent) {
    if (step.name !== "otp") return;
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { reset_token } = await api.verifyPasswordResetOtp(
        step.countryCode,
        step.phoneNumber,
        code,
      );
      setStep({ name: "password", resetToken: reset_token });
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleResendOtp() {
    if (step.name !== "otp") return;
    setError(null);
    try {
      await api.requestPasswordResetOtp(
        step.countryCode,
        step.phoneNumber,
        step.channel ?? undefined,
      );
    } catch (err) {
      setError(describeApiError(err));
    }
  }

  async function handleComplete(event: FormEvent) {
    if (step.name !== "password") return;
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.completePasswordReset(step.resetToken, newPassword);
      setStep({ name: "done" });
    } catch (err) {
      setError(describeApiError(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-black">
      <div className="w-full max-w-sm space-y-4 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Şifremi Unuttum</h1>

        {step.name === "phone" && (
          <form onSubmit={handleRequestOtp} className="space-y-4">
            <div className="space-y-1">
              <label className="block text-sm text-zinc-700 dark:text-zinc-300">
                Telefon Numarası
              </label>
              <div className="flex gap-2">
                <select
                  value={countryCode}
                  onChange={(e) => setCountryCode(e.target.value)}
                  className="rounded border border-zinc-300 px-2 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                >
                  {COUNTRY_CODES.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.flag} {c.code}
                    </option>
                  ))}
                </select>
                <input
                  type="tel"
                  required
                  placeholder="5XX XXX XX XX"
                  autoComplete="tel-national"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                />
              </div>
            </div>

            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {submitting ? "Gönderiliyor..." : "Devam Et"}
            </button>
          </form>
        )}

        {step.name === "channel" && (
          <div className="space-y-4">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Doğrulama kodunu nereye göndermek istersiniz?
            </p>

            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

            <div className="space-y-2">
              <button
                type="button"
                disabled={submitting}
                onClick={() => handlePickChannel("sms")}
                className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
              >
                SMS ile Gönder
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={() => handlePickChannel("email")}
                className="w-full rounded border border-zinc-300 px-3 py-2 text-sm font-medium text-black disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-50"
              >
                E-posta ile Gönder
              </button>
            </div>
          </div>
        )}

        {step.name === "otp" && (
          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              {step.channel === "email"
                ? "E-postanıza gönderilen kodu girin."
                : `${step.countryCode} ${step.phoneNumber} numarasına gönderilen kodu girin.`}
            </p>

            <div className="space-y-1">
              <label htmlFor="otpCode" className="block text-sm text-zinc-700 dark:text-zinc-300">
                Doğrulama Kodu
              </label>
              <input
                id="otpCode"
                type="text"
                inputMode="numeric"
                required
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </div>

            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {submitting ? "Doğrulanıyor..." : "Doğrula"}
            </button>

            <button
              type="button"
              onClick={handleResendOtp}
              className="w-full text-sm text-zinc-500 underline dark:text-zinc-400"
            >
              Kodu tekrar gönder
            </button>
          </form>
        )}

        {step.name === "password" && (
          <form onSubmit={handleComplete} className="space-y-4">
            <div className="space-y-1">
              <label htmlFor="newPassword" className="block text-sm text-zinc-700 dark:text-zinc-300">
                Yeni Şifre
              </label>
              <input
                id="newPassword"
                type="password"
                required
                autoComplete="new-password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                En az 6 karakter, 1 büyük harf, 1 küçük harf ve 1 özel karakter içermeli.
              </p>
            </div>

            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {submitting ? "Kaydediliyor..." : "Şifreyi Güncelle"}
            </button>
          </form>
        )}

        {step.name === "done" && (
          <div className="space-y-4">
            <p className="text-sm text-zinc-700 dark:text-zinc-300">
              Şifreniz güncellendi. Yeni şifrenizle giriş yapabilirsiniz.
            </p>
            <button
              type="button"
              onClick={() => router.push("/login")}
              className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
            >
              Giriş Yap
            </button>
          </div>
        )}

        {step.name !== "done" && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            <a href="/login" className="underline">
              Giriş ekranına dön
            </a>
          </p>
        )}
      </div>
    </div>
  );
}
