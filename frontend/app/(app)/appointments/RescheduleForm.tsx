"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { Appointment, Customer, Service, StaffMember } from "@/lib/types";

function formatSlotTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

function localDateString(iso: string): string {
  const d = new Date(iso);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

interface RescheduleFormProps {
  token: string;
  appointment: Appointment;
  staffMembers: StaffMember[];
  services: Service[];
  customers: Customer[];
  onRescheduled: () => void;
  onCancel: () => void;
}

export default function RescheduleForm({
  token,
  appointment,
  staffMembers,
  services,
  customers,
  onRescheduled,
  onCancel,
}: RescheduleFormProps) {
  const staff = staffMembers.find((s) => s.id === appointment.staff_id);
  const service = services.find((s) => s.id === appointment.service_id);
  const customer = customers.find((c) => c.id === appointment.customer_id);

  const [date, setDate] = useState(localDateString(appointment.start_at));
  const [slots, setSlots] = useState<string[] | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function loadSlots(ignoreRef?: { current: boolean }) {
    setSlotsLoading(true);
    setSlotsError(null);
    setSelectedSlot(null);
    api
      .getAvailableSlots(token, appointment.staff_id, appointment.service_id, date)
      .then((res) => {
        if (!ignoreRef?.current) setSlots(res.slots);
      })
      .catch((err) => {
        if (!ignoreRef?.current) {
          setSlots(null);
          setSlotsError(describeApiError(err));
        }
      })
      .finally(() => {
        if (!ignoreRef?.current) setSlotsLoading(false);
      });
  }

  useEffect(() => {
    // loadSlots sets state synchronously at its start (loading indicator),
    // so it must be called through a nested closure rather than directly in
    // the effect body - see react-hooks/set-state-in-effect. The ignoreRef
    // also guards against a stale response overwriting a newer one.
    const ignoreRef = { current: false };
    function run() {
      loadSlots(ignoreRef);
    }
    run();
    return () => {
      ignoreRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [date]);

  async function handleSubmit() {
    if (!selectedSlot) return;

    setFormError(null);
    setSubmitting(true);
    try {
      await api.rescheduleAppointment(token, appointment.id, { start_at: selectedSlot });
      onRescheduled();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setFormError(
          "Bu slot dolu. Slot listesi yenilendi, lütfen başka bir saat seçin.",
        );
        loadSlots();
      } else {
        setFormError(describeApiError(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4 rounded-lg border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-black dark:text-zinc-50">
          Randevuyu Yeniden Planla
        </h2>
        <button
          onClick={onCancel}
          className="text-sm text-zinc-500 hover:underline dark:text-zinc-400"
        >
          Vazgeç
        </button>
      </div>

      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        {customer?.display_name || customer?.whatsapp_number || `#${appointment.customer_id}`}
        {" — "}
        {service?.name ?? `#${appointment.service_id}`}
        {" — "}
        {staff?.name ?? `#${appointment.staff_id}`}
      </p>

      <div className="space-y-1">
        <label className="block text-sm text-zinc-700 dark:text-zinc-300">Yeni Tarih</label>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
        />
      </div>

      <div className="space-y-2">
        <p className="text-sm text-zinc-700 dark:text-zinc-300">Müsait Saatler</p>
        {slotsLoading && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
        )}
        {slotsError && <p className="text-sm text-red-600 dark:text-red-400">{slotsError}</p>}
        {!slotsLoading && !slotsError && slots !== null && slots.length === 0 && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Bu tarihte müsait saat yok.</p>
        )}
        {!slotsLoading && slots !== null && slots.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {slots.map((slot) => (
              <button
                key={slot}
                onClick={() => setSelectedSlot(slot)}
                className={`rounded border px-3 py-1.5 text-sm ${
                  selectedSlot === slot
                    ? "border-black bg-black text-white dark:border-white dark:bg-white dark:text-black"
                    : "border-zinc-300 text-zinc-700 hover:bg-zinc-100 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                }`}
              >
                {formatSlotTime(slot)}
              </button>
            ))}
          </div>
        )}
      </div>

      {formError && <p className="text-sm text-red-600 dark:text-red-400">{formError}</p>}

      <button
        onClick={handleSubmit}
        disabled={!selectedSlot || submitting}
        className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
      >
        {submitting ? "Kaydediliyor..." : "Yeni Saati Kaydet"}
      </button>
    </div>
  );
}
