"use client";

import { useEffect, useState, type FormEvent } from "react";

import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type {
  AvailabilityOverride,
  AvailabilityRule,
  ScheduleMode,
  StaffMember,
  Tenant,
} from "@/lib/types";

const WEEKDAY_LABELS = [
  "Pazartesi",
  "Salı",
  "Çarşamba",
  "Perşembe",
  "Cuma",
  "Cumartesi",
  "Pazar",
];

function ModeFields({
  idPrefix,
  mode,
  setMode,
  slotDuration,
  setSlotDuration,
  gapMinutes,
  setGapMinutes,
}: {
  idPrefix: string;
  mode: ScheduleMode;
  setMode: (m: ScheduleMode) => void;
  slotDuration: string;
  setSlotDuration: (v: string) => void;
  gapMinutes: string;
  setGapMinutes: (v: string) => void;
}) {
  const durationId = `${idPrefix}-slot-duration`;
  const gapId = `${idPrefix}-gap-minutes`;
  return (
    <div className="space-y-2">
      <div className="flex gap-4 text-sm">
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            checked={mode === "flexible"}
            onChange={() => setMode("flexible")}
          />
          Esnek (hizmet süresine göre)
        </label>
        <label className="flex items-center gap-1.5">
          <input
            type="radio"
            checked={mode === "standard"}
            onChange={() => setMode("standard")}
          />
          Standart (sabit randevu izgarası)
        </label>
      </div>
      {mode === "standard" && (
        <div className="flex gap-3">
          <div className="space-y-1">
            <label htmlFor={durationId} className="block text-xs text-zinc-500 dark:text-zinc-400">
              Randevu Süresi (dk)
            </label>
            <input
              id={durationId}
              type="number"
              min={1}
              required
              value={slotDuration}
              onChange={(e) => setSlotDuration(e.target.value)}
              className="w-28 rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </div>
          <div className="space-y-1">
            <label htmlFor={gapId} className="block text-xs text-zinc-500 dark:text-zinc-400">
              Aradaki Boşluk (dk)
            </label>
            <input
              id={gapId}
              type="number"
              min={0}
              value={gapMinutes}
              onChange={(e) => setGapMinutes(e.target.value)}
              className="w-28 rounded border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default function AvailabilityPage() {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [rules, setRules] = useState<AvailabilityRule[] | null>(null);
  const [overrides, setOverrides] = useState<AvailabilityOverride[] | null>(null);
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [error, setError] = useState<string | null>(null);

  const isOwner = tenant === null || tenant.my_role === "owner";

  // --- Haftalık plan formu ---
  const [staffId, setStaffId] = useState("");
  const [weekday, setWeekday] = useState("0");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [mode, setMode] = useState<ScheduleMode>("flexible");
  const [slotDuration, setSlotDuration] = useState("60");
  const [gapMinutes, setGapMinutes] = useState("0");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // --- Tarihe özel istisna formu ---
  const [overrideDate, setOverrideDate] = useState("");
  const [overrideStart, setOverrideStart] = useState("");
  const [overrideEnd, setOverrideEnd] = useState("");
  const [overrideMode, setOverrideMode] = useState<ScheduleMode>("flexible");
  const [overrideSlotDuration, setOverrideSlotDuration] = useState("60");
  const [overrideGapMinutes, setOverrideGapMinutes] = useState("0");
  const [overrideError, setOverrideError] = useState<string | null>(null);
  const [overrideSubmitting, setOverrideSubmitting] = useState(false);

  // --- Randevu açık kalma süresi ---
  const [horizonUnlimited, setHorizonUnlimited] = useState(true);
  const [horizonDays, setHorizonDays] = useState("7");
  const [horizonSaving, setHorizonSaving] = useState(false);
  const [horizonError, setHorizonError] = useState<string | null>(null);
  const [horizonSaved, setHorizonSaved] = useState(false);

  function loadRules() {
    api
      .getAvailabilityRules()
      .then(setRules)
      .catch((err) => setError(describeApiError(err)));
  }

  function loadOverrides() {
    api
      .getAvailabilityOverrides()
      .then(setOverrides)
      .catch((err) => setError(describeApiError(err)));
  }

  useEffect(() => {
    loadRules();
    loadOverrides();
    api
      .getStaffMembers()
      .then((data) => {
        setStaffMembers(data);
        if (data.length > 0) setStaffId(String(data[0].id));
      })
      .catch((err) => setError(describeApiError(err)));
    api
      .getMyTenant()
      .then((t) => {
        setTenant(t);
        if (t.my_role === "staff" && t.my_staff_member_id !== null) {
          setStaffId(String(t.my_staff_member_id));
        }
        setHorizonUnlimited(t.max_advance_booking_days === null);
        if (t.max_advance_booking_days !== null) {
          setHorizonDays(String(t.max_advance_booking_days));
        }
      })
      .catch((err) => setError(describeApiError(err)));
  }, []);

  function staffLabel(id: number): string {
    return staffMembers.find((s) => s.id === id)?.name ?? `#${id}`;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);

    if (startTime && endTime && startTime >= endTime) {
      setFormError("Bitiş saati başlangıç saatinden sonra olmalı.");
      return;
    }
    if (mode === "standard" && !slotDuration) {
      setFormError("Standart modda randevu süresi zorunlu.");
      return;
    }
    if (!staffId) return;

    setError(null);
    setSubmitting(true);
    try {
      await api.createAvailabilityRule({
        staff_id: Number(staffId),
        weekday: Number(weekday),
        start_time: startTime,
        end_time: endTime,
        mode,
        slot_duration_minutes: mode === "standard" ? Number(slotDuration) : null,
        gap_minutes: mode === "standard" ? Number(gapMinutes) : 0,
      });
      setStartTime("");
      setEndTime("");
      loadRules();
    } catch (err) {
      setFormError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCreateOverride(applyToWeeklyTemplate: boolean) {
    setOverrideError(null);

    if (!overrideDate || !overrideStart || !overrideEnd) {
      setOverrideError("Tarih, başlangıç ve bitiş saati zorunlu.");
      return;
    }
    if (overrideStart >= overrideEnd) {
      setOverrideError("Bitiş saati başlangıç saatinden sonra olmalı.");
      return;
    }
    if (!staffId) return;

    setOverrideSubmitting(true);
    try {
      await api.createAvailabilityOverride({
        staff_id: Number(staffId),
        date: overrideDate,
        start_time: overrideStart,
        end_time: overrideEnd,
        mode: overrideMode,
        slot_duration_minutes: overrideMode === "standard" ? Number(overrideSlotDuration) : null,
        gap_minutes: overrideMode === "standard" ? Number(overrideGapMinutes) : 0,
        apply_to_weekly_template: applyToWeeklyTemplate,
      });
      setOverrideDate("");
      setOverrideStart("");
      setOverrideEnd("");
      loadOverrides();
      if (applyToWeeklyTemplate) loadRules();
    } catch (err) {
      setOverrideError(describeApiError(err));
    } finally {
      setOverrideSubmitting(false);
    }
  }

  async function handleRemoveOverride(id: number) {
    try {
      await api.removeAvailabilityOverride(id);
      loadOverrides();
    } catch (err) {
      setOverrideError(describeApiError(err));
    }
  }

  async function handleSaveHorizon(event: FormEvent) {
    event.preventDefault();
    setHorizonError(null);
    setHorizonSaved(false);
    setHorizonSaving(true);
    try {
      const value = horizonUnlimited ? null : Number(horizonDays);
      const updated = await api.updateBookingSettings(value);
      setTenant(updated);
      setHorizonSaved(true);
    } catch (err) {
      setHorizonError(describeApiError(err));
    } finally {
      setHorizonSaving(false);
    }
  }

  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Çalışma Planı</h1>

      {isOwner && (
        <section className="max-w-sm space-y-3 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Randevu Açık Kalma Süresi
          </h2>
          <form onSubmit={handleSaveHorizon} className="space-y-2">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={horizonUnlimited}
                onChange={(e) => setHorizonUnlimited(e.target.checked)}
              />
              Sınırsız
            </label>
            {!horizonUnlimited && (
              <div className="flex items-center gap-2 text-sm">
                <span>En fazla</span>
                <input
                  type="number"
                  min={1}
                  value={horizonDays}
                  onChange={(e) => setHorizonDays(e.target.value)}
                  className="w-20 rounded border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                />
                <span>gün öncesinden randevu alınabilir</span>
              </div>
            )}
            {horizonError && <p className="text-sm text-red-600 dark:text-red-400">{horizonError}</p>}
            {horizonSaved && (
              <p className="text-sm text-green-600 dark:text-green-400">Kaydedildi.</p>
            )}
            <button
              type="submit"
              disabled={horizonSaving}
              className="rounded bg-black px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {horizonSaving ? "Kaydediliyor..." : "Kaydet"}
            </button>
          </form>
        </section>
      )}

      <section className="space-y-3">
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Haftalık Plan</h2>

        {staffMembers.length === 0 ? (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            Çalışma saati eklemeden önce en az bir personel oluşturmalısınız.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
            {isOwner ? (
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
            ) : (
              <p className="text-sm text-zinc-500 dark:text-zinc-400">Kendi çalışma planınız</p>
            )}
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

            <div className="w-full">
              <ModeFields
                idPrefix="rule"
                mode={mode}
                setMode={setMode}
                slotDuration={slotDuration}
                setSlotDuration={setSlotDuration}
                gapMinutes={gapMinutes}
                setGapMinutes={setGapMinutes}
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
            <table className="w-full min-w-[600px] border-collapse text-sm">
              <thead>
                <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-800 dark:bg-zinc-900">
                  <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Personel</th>
                  <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Gün</th>
                  <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Saat</th>
                  <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Mod</th>
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
                      {rule.start_time.slice(0, 5)}–{rule.end_time.slice(0, 5)}
                    </td>
                    <td className="px-4 py-2 text-black dark:text-zinc-50">
                      {rule.mode === "standard"
                        ? `Standart (${rule.slot_duration_minutes} dk + ${rule.gap_minutes} dk boşluk)`
                        : "Esnek"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {staffMembers.length > 0 && (
        <section className="space-y-3 border-t border-zinc-200 pt-6 dark:border-zinc-800">
          <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Tarihe Özel Değişiklik
          </h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Sadece seçtiğiniz tarih için geçerli olur, haftalık planı değiştirmez — isterseniz
            kalıcı da yapabilirsiniz.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <label htmlFor="overrideDate" className="block text-sm text-zinc-700 dark:text-zinc-300">
                Tarih
              </label>
              <input
                id="overrideDate"
                type="date"
                value={overrideDate}
                onChange={(e) => setOverrideDate(e.target.value)}
                className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="overrideStart" className="block text-sm text-zinc-700 dark:text-zinc-300">
                Başlangıç
              </label>
              <input
                id="overrideStart"
                type="time"
                value={overrideStart}
                onChange={(e) => setOverrideStart(e.target.value)}
                className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </div>
            <div className="space-y-1">
              <label htmlFor="overrideEnd" className="block text-sm text-zinc-700 dark:text-zinc-300">
                Bitiş
              </label>
              <input
                id="overrideEnd"
                type="time"
                value={overrideEnd}
                onChange={(e) => setOverrideEnd(e.target.value)}
                className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </div>
          </div>

          <ModeFields
            idPrefix="override"
            mode={overrideMode}
            setMode={setOverrideMode}
            slotDuration={overrideSlotDuration}
            setSlotDuration={setOverrideSlotDuration}
            gapMinutes={overrideGapMinutes}
            setGapMinutes={setOverrideGapMinutes}
          />

          {overrideError && <p className="text-sm text-red-600 dark:text-red-400">{overrideError}</p>}

          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => handleCreateOverride(false)}
              disabled={overrideSubmitting}
              className="rounded bg-black px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              Sadece Bu Tarih İçin Kaydet
            </button>
            <button
              type="button"
              onClick={() => handleCreateOverride(true)}
              disabled={overrideSubmitting}
              className="rounded border border-zinc-300 px-3 py-2 text-sm text-zinc-700 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300"
            >
              Kalıcı Yap (Bu Günü Her Hafta Böyle Yap)
            </button>
          </div>

          {overrides !== null && overrides.length > 0 && (
            <ul className="space-y-1 text-sm">
              {overrides.map((override) => (
                <li
                  key={override.id}
                  className="flex items-center justify-between rounded border border-zinc-200 px-3 py-2 dark:border-zinc-800"
                >
                  <span className="text-black dark:text-zinc-50">
                    {staffLabel(override.staff_id)} — {override.date} {override.start_time.slice(0, 5)}
                    –{override.end_time.slice(0, 5)}
                  </span>
                  <button
                    onClick={() => handleRemoveOverride(override.id)}
                    className="text-xs text-red-600 underline dark:text-red-400"
                  >
                    Kaldır
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}
