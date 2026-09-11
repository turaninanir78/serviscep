"use client";

import { useEffect, useState, type FormEvent } from "react";

import { api } from "@/lib/api";
import { COUNTRY_CODES, DEFAULT_COUNTRY_CODE } from "@/lib/countryCodes";
import { describeApiError } from "@/lib/errors";
import type { User } from "@/lib/types";

const PASSWORD_HINT =
  "En az 6 karakter, 1 büyük harf, 1 küçük harf ve 1 özel karakter içermeli.";

type EmailStep = { name: "closed" } | { name: "enter-email" } | { name: "enter-code"; email: string };
type PhoneStep =
  | { name: "closed" }
  | { name: "enter-phone" }
  | { name: "enter-code"; countryCode: string; phoneNumber: string };
type PasswordStep = { name: "closed" } | { name: "open" };

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [emailStep, setEmailStep] = useState<EmailStep>({ name: "closed" });
  const [emailInput, setEmailInput] = useState("");
  const [emailCode, setEmailCode] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [emailSubmitting, setEmailSubmitting] = useState(false);

  const [phoneStep, setPhoneStep] = useState<PhoneStep>({ name: "closed" });
  const [phoneCountryCode, setPhoneCountryCode] = useState(DEFAULT_COUNTRY_CODE);
  const [phoneNumberInput, setPhoneNumberInput] = useState("");
  const [phoneCode, setPhoneCode] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [phoneSubmitting, setPhoneSubmitting] = useState(false);

  const [passwordStep, setPasswordStep] = useState<PasswordStep>({ name: "closed" });
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSubmitting, setPasswordSubmitting] = useState(false);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  useEffect(() => {
    api
      .getMe()
      .then(setUser)
      .catch((err) => setLoadError(describeApiError(err)));
  }, []);

  // --- E-posta değiştirme/ekleme ---

  async function handleRequestEmailOtp(event: FormEvent) {
    event.preventDefault();
    setEmailError(null);
    setEmailSubmitting(true);
    try {
      await api.requestAddEmailOtp(emailInput);
      setEmailStep({ name: "enter-code", email: emailInput });
    } catch (err) {
      setEmailError(describeApiError(err));
    } finally {
      setEmailSubmitting(false);
    }
  }

  async function handleVerifyEmailCode(event: FormEvent) {
    if (emailStep.name !== "enter-code") return;
    event.preventDefault();
    setEmailError(null);
    setEmailSubmitting(true);
    try {
      const updated = await api.verifyAddEmail(emailStep.email, emailCode);
      setUser(updated);
      setEmailStep({ name: "closed" });
      setEmailCode("");
      setEmailInput("");
    } catch (err) {
      setEmailError(describeApiError(err));
    } finally {
      setEmailSubmitting(false);
    }
  }

  // --- Telefon değiştirme ---

  async function handleRequestPhoneOtp(event: FormEvent) {
    event.preventDefault();
    setPhoneError(null);
    setPhoneSubmitting(true);
    try {
      await api.requestChangePhoneOtp(phoneCountryCode, phoneNumberInput);
      setPhoneStep({
        name: "enter-code",
        countryCode: phoneCountryCode,
        phoneNumber: phoneNumberInput,
      });
    } catch (err) {
      setPhoneError(describeApiError(err));
    } finally {
      setPhoneSubmitting(false);
    }
  }

  async function handleVerifyPhoneCode(event: FormEvent) {
    if (phoneStep.name !== "enter-code") return;
    event.preventDefault();
    setPhoneError(null);
    setPhoneSubmitting(true);
    try {
      const updated = await api.verifyChangePhoneOtp(
        phoneStep.countryCode,
        phoneStep.phoneNumber,
        phoneCode,
      );
      setUser(updated);
      setPhoneStep({ name: "closed" });
      setPhoneCode("");
      setPhoneNumberInput("");
    } catch (err) {
      setPhoneError(describeApiError(err));
    } finally {
      setPhoneSubmitting(false);
    }
  }

  // --- Şifre değiştirme ---

  async function handleChangePassword(event: FormEvent) {
    event.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(false);
    setPasswordSubmitting(true);
    try {
      await api.changePassword(currentPassword, newPassword);
      setPasswordSuccess(true);
      setCurrentPassword("");
      setNewPassword("");
      setPasswordStep({ name: "closed" });
    } catch (err) {
      setPasswordError(describeApiError(err));
    } finally {
      setPasswordSubmitting(false);
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

      {passwordSuccess && (
        <p className="text-sm text-green-600 dark:text-green-400">Şifreniz güncellendi.</p>
      )}

      {/* --- E-posta --- */}
      {emailStep.name === "closed" && (
        <button
          onClick={() => setEmailStep({ name: "enter-email" })}
          className="rounded bg-black px-3 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
        >
          {user.email === null ? "E-posta Ekle" : "E-postamı Değiştir"}
        </button>
      )}

      {emailStep.name === "enter-email" && (
        <form
          onSubmit={handleRequestEmailOtp}
          className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
        >
          <div className="space-y-1">
            <label htmlFor="newEmail" className="block text-sm text-zinc-700 dark:text-zinc-300">
              Yeni E-posta Adresi
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

          {emailError && <p className="text-sm text-red-600 dark:text-red-400">{emailError}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={emailSubmitting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {emailSubmitting ? "Kod gönderiliyor..." : "Kod Gönder"}
            </button>
            <button
              type="button"
              onClick={() => setEmailStep({ name: "closed" })}
              className="rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            >
              Vazgeç
            </button>
          </div>
        </form>
      )}

      {emailStep.name === "enter-code" && (
        <form
          onSubmit={handleVerifyEmailCode}
          className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
        >
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {emailStep.email} adresine gönderilen kodu girin.
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
              value={emailCode}
              onChange={(e) => setEmailCode(e.target.value)}
              className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </div>

          {emailError && <p className="text-sm text-red-600 dark:text-red-400">{emailError}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={emailSubmitting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {emailSubmitting ? "Doğrulanıyor..." : "Doğrula"}
            </button>
            <button
              type="button"
              onClick={() => setEmailStep({ name: "closed" })}
              className="rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            >
              Vazgeç
            </button>
          </div>
        </form>
      )}

      {/* --- Telefon --- */}
      {phoneStep.name === "closed" && (
        <button
          onClick={() => setPhoneStep({ name: "enter-phone" })}
          className="rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
        >
          Telefon Numaramı Değiştir
        </button>
      )}

      {phoneStep.name === "enter-phone" && (
        <form
          onSubmit={handleRequestPhoneOtp}
          className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
        >
          <div className="space-y-1">
            <label className="block text-sm text-zinc-700 dark:text-zinc-300">
              Yeni Telefon Numarası
            </label>
            <div className="flex gap-2">
              <select
                value={phoneCountryCode}
                onChange={(e) => setPhoneCountryCode(e.target.value)}
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
                value={phoneNumberInput}
                onChange={(e) => setPhoneNumberInput(e.target.value)}
                className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </div>
          </div>

          {phoneError && <p className="text-sm text-red-600 dark:text-red-400">{phoneError}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={phoneSubmitting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {phoneSubmitting ? "Kod gönderiliyor..." : "Kod Gönder"}
            </button>
            <button
              type="button"
              onClick={() => setPhoneStep({ name: "closed" })}
              className="rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            >
              Vazgeç
            </button>
          </div>
        </form>
      )}

      {phoneStep.name === "enter-code" && (
        <form
          onSubmit={handleVerifyPhoneCode}
          className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
        >
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {phoneStep.countryCode} {phoneStep.phoneNumber} numarasına gönderilen kodu girin.
          </p>
          <div className="space-y-1">
            <label htmlFor="phoneOtp" className="block text-sm text-zinc-700 dark:text-zinc-300">
              Doğrulama Kodu
            </label>
            <input
              id="phoneOtp"
              type="text"
              inputMode="numeric"
              required
              autoComplete="one-time-code"
              value={phoneCode}
              onChange={(e) => setPhoneCode(e.target.value)}
              className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </div>

          {phoneError && <p className="text-sm text-red-600 dark:text-red-400">{phoneError}</p>}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={phoneSubmitting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {phoneSubmitting ? "Doğrulanıyor..." : "Doğrula"}
            </button>
            <button
              type="button"
              onClick={() => setPhoneStep({ name: "closed" })}
              className="rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
            >
              Vazgeç
            </button>
          </div>
        </form>
      )}

      {/* --- Şifre --- */}
      {passwordStep.name === "closed" && (
        <button
          onClick={() => {
            setPasswordSuccess(false);
            setPasswordStep({ name: "open" });
          }}
          className="rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 dark:border-zinc-700 dark:text-zinc-300"
        >
          Şifremi Değiştir
        </button>
      )}

      {passwordStep.name === "open" && (
        <form
          onSubmit={handleChangePassword}
          className="space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950"
        >
          <div className="space-y-1">
            <label
              htmlFor="currentPassword"
              className="block text-sm text-zinc-700 dark:text-zinc-300"
            >
              Mevcut Şifre
            </label>
            <input
              id="currentPassword"
              type="password"
              required
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </div>

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
            <p className="text-xs text-zinc-500 dark:text-zinc-400">{PASSWORD_HINT}</p>
          </div>

          {passwordError && (
            <p className="text-sm text-red-600 dark:text-red-400">{passwordError}</p>
          )}

          <div className="flex gap-2">
            <button
              type="submit"
              disabled={passwordSubmitting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {passwordSubmitting ? "Kaydediliyor..." : "Şifreyi Güncelle"}
            </button>
            <button
              type="button"
              onClick={() => setPasswordStep({ name: "closed" })}
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
