"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

import { LegalDocumentModal } from "@/components/LegalDocumentModal";
import { api } from "@/lib/api";
import { COUNTRY_CODES, DEFAULT_COUNTRY_CODE } from "@/lib/countryCodes";
import { describeApiError } from "@/lib/errors";

type Step =
  | { name: "phone" }
  | { name: "otp"; countryCode: string; phoneNumber: string }
  | { name: "password"; countryCode: string; phoneNumber: string; registrationToken: string };

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>({ name: "phone" });
  const [countryCode, setCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [phoneNumber, setPhoneNumber] = useState("");
  const [code, setCode] = useState("");
  const [tenantName, setTenantName] = useState("");
  const [password, setPassword] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [viewingDocumentType, setViewingDocumentType] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleRequestOtp(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.requestRegisterOtp(countryCode, phoneNumber);
      setStep({ name: "otp", countryCode, phoneNumber });
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
      const { registration_token } = await api.verifyRegisterOtp(
        step.countryCode,
        step.phoneNumber,
        code,
      );
      setStep({
        name: "password",
        countryCode: step.countryCode,
        phoneNumber: step.phoneNumber,
        registrationToken: registration_token,
      });
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
      await api.requestRegisterOtp(step.countryCode, step.phoneNumber);
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
      await api.completeRegister(step.registrationToken, tenantName, password, acceptedTerms);
      router.push("/appointments");
    } catch (err) {
      setError(describeApiError(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-black">
      <div className="w-full max-w-sm space-y-4 rounded-lg border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950">
        <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Firma Kaydı</h1>

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
              {submitting ? "Kod gönderiliyor..." : "Kod Gönder"}
            </button>
          </form>
        )}

        {step.name === "otp" && (
          <form onSubmit={handleVerifyOtp} className="space-y-4">
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              {step.countryCode} {step.phoneNumber} numarasına gönderilen kodu girin.
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

            <div className="flex items-start gap-2">
              <input
                id="acceptedTerms"
                type="checkbox"
                checked={acceptedTerms}
                onChange={(e) => setAcceptedTerms(e.target.checked)}
                className="mt-0.5"
              />
              <label htmlFor="acceptedTerms" className="text-sm text-zinc-700 dark:text-zinc-300">
                <button
                  type="button"
                  onClick={() => setViewingDocumentType("terms_of_service")}
                  className="underline"
                >
                  Kullanım Şartları
                </button>{" "}
                ve{" "}
                <button
                  type="button"
                  onClick={() => setViewingDocumentType("privacy_notice")}
                  className="underline"
                >
                  Aydınlatma Metni
                </button>
                &apos;ni okudum, kabul ediyorum.
              </label>
            </div>

            {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

            <button
              type="submit"
              disabled={submitting || !acceptedTerms}
              className="w-full rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {submitting ? "Kaydediliyor..." : "Kayıt Ol"}
            </button>
          </form>
        )}

        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Zaten hesabınız var mı?{" "}
          <a href="/login" className="underline">
            Giriş yapın
          </a>
        </p>
      </div>

      {viewingDocumentType && (
        <LegalDocumentModal
          type={viewingDocumentType}
          onClose={() => setViewingDocumentType(null)}
        />
      )}
    </div>
  );
}
