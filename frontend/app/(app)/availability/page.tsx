"use client";

import { useEffect, useState, type FormEvent } from "react";

import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { describeApiError } from "@/lib/errors";
import type { AvailabilityRule, StaffMember } from "@/lib/types";

const WEEKDAY_LABELS = [
  "Pazartesi",
  "Salı",
  "Çarşamba",
  "Perşembe",
  "Cuma",
  "Cumartesi",
  "Pazar",
];

export default function AvailabilityPage() {
  const [rules, setRules] = useState<AvailabilityRule[] | null>(null);
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [staffId, setStaffId] = useState("");
  const [weekday, setWeekday] = useState("0");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function loadRules(token: string) {
    api
      .getAvailabilityRules(token)
      .then(setRules)
      .catch((err) => setError(describeApiError(err)));
  }

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    loadRules(token);
    api
      .getStaffMembers(token)
      .then((data) => {
        setStaffMembers(data);
        if (data.length > 0) setStaffId(String(data[0].id));
      })
      .catch((err) => setError(describeApiError(err)));
  }, []);

  function staffLabel(id: number): string {
    return staffMembers.find((s) => s.id === id)?.name ?? `#${id}`;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    // Backend zaten CHECK ile reddediyor, ama kullanıcıya API hatası
    // beklemeden anında geri bildirim vermek daha iyi bir deneyim.
    if (startTime && endTime && startTime >= endTime) {
      setFormError("Bitiş saati başlangıç saatinden sonra olmalı.");
      return;
    }

    const token = getToken();
    if (!token || !staffId) return;

    setError(null);
    setSubmitting(true);
    try {
      await api.createAvailabilityRule(token, {
        staff_id: Number(staffId),
        weekday: Number(weekday),
        start_time: startTime,
        end_time: endTime,
      });
      setStartTime("");
      setEndTime("");
      loadRules(token);
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Çalışma Saatleri</h1>

      {staffMembers.length === 0 ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Çalışma saati eklemeden önce en az bir personel oluşturmalısınız.
        </p>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
          <div className="space-y-1">
            <label htmlFor="ruleStaff" className="block text-sm text-zinc-700 dark:text-zinc-300">
              Personel
            </label>
            <select
              id="ruleStaff"
              value={staffId}
              onChange={(e) => setStaffId(e.target.value)}
              className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            >
              {staffMembers.map((staff) => (
                <option key={staff.id} value={staff.id}>
                  {staff.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor="ruleWeekday" className="block text-sm text-zinc-700 dark:text-zinc-300">
              Gün
            </label>
            <select
              id="ruleWeekday"
              value={weekday}
              onChange={(e) => setWeekday(e.target.value)}
              className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            >
              {WEEKDAY_LABELS.map((label, index) => (
                <option key={index} value={index}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1">
            <label htmlFor="ruleStart" className="block text-sm text-zinc-700 dark:text-zinc-300">
              Başlangıç
            </label>
            <input
              id="ruleStart"
              type="time"
              required
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor="ruleEnd" className="block text-sm text-zinc-700 dark:text-zinc-300">
              Bitiş
            </label>
            <input
              id="ruleEnd"
              type="time"
              required
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
          >
            {submitting ? "Ekleniyor..." : "Ekle"}
          </button>
        </form>
      )}

      {formError && <p className="text-sm text-red-600 dark:text-red-400">{formError}</p>}
      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {rules === null && !error && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
      )}

      {rules !== null && rules.length === 0 && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Henüz çalışma saati yok.</p>
      )}

      {rules !== null && rules.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="w-full min-w-[480px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-800 dark:bg-zinc-900">
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Personel</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Gün</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Başlangıç</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Bitiş</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr
                  key={rule.id}
                  className="border-b border-zinc-100 last:border-0 dark:border-zinc-900"
                >
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {staffLabel(rule.staff_id)}
                  </td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {WEEKDAY_LABELS[rule.weekday] ?? rule.weekday}
                  </td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {rule.start_time.slice(0, 5)}
                  </td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {rule.end_time.slice(0, 5)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
