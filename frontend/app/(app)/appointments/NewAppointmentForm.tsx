"use client";

import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { Customer, Service, StaffMember } from "@/lib/types";

function todayDateString(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function formatSlotTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

interface NewAppointmentFormProps {
  token: string;
  staffMembers: StaffMember[];
  services: Service[];
  customers: Customer[];
  onCreated: () => void;
  onCancel: () => void;
}

export default function NewAppointmentForm({
  token,
  staffMembers,
  services,
  customers,
  onCreated,
  onCancel,
}: NewAppointmentFormProps) {
  const activeStaff = staffMembers.filter((s) => s.is_active);
  const activeServices = services.filter((s) => s.is_active);

  const [staffId, setStaffId] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [date, setDate] = useState(todayDateString());

  const [slots, setSlots] = useState<string[] | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slotsError, setSlotsError] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);

  const [customerSearch, setCustomerSearch] = useState("");
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function loadSlots() {
    if (!staffId || !serviceId || !date) {
      setSlots(null);
      return;
    }
    setSlotsLoading(true);
    setSlotsError(null);
    setSelectedSlot(null);
    api
      .getAvailableSlots(token, Number(staffId), Number(serviceId), date)
      .then((res) => setSlots(res.slots))
      .catch((err) => {
        setSlots(null);
        setSlotsError(describeApiError(err));
      })
      .finally(() => setSlotsLoading(false));
  }

  useEffect(() => {
    loadSlots();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [staffId, serviceId, date]);

  const selectedService = activeServices.find((s) => String(s.id) === serviceId);

  const filteredCustomers =
    customerSearch.trim() === ""
      ? []
      : customers
          .filter((c) => {
            const term = customerSearch.trim().toLowerCase();
            return (
              (c.display_name ?? "").toLowerCase().includes(term) ||
              c.whatsapp_number.includes(term)
            );
          })
          .slice(0, 20);

  async function handleSubmit() {
    if (!staffId || !serviceId || !selectedSlot || !selectedCustomer) return;

    setFormError(null);
    setSubmitting(true);
    try {
      await api.createAppointment(token, {
        staff_id: Number(staffId),
        service_id: Number(serviceId),
        customer_id: selectedCustomer.id,
        start_at: selectedSlot,
      });
      onCreated();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setFormError("Bu slot az önce başka biri tarafından alındı. Slot listesi yenilendi, lütfen başka bir saat seçin.");
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
        <h2 className="text-lg font-semibold text-black dark:text-zinc-50">Yeni Randevu</h2>
        <button
          onClick={onCancel}
          className="text-sm text-zinc-500 hover:underline dark:text-zinc-400"
        >
          Vazgeç
        </button>
      </div>

      {activeStaff.length === 0 || activeServices.length === 0 ? (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Randevu oluşturmak için en az bir aktif personel ve bir aktif hizmet gerekiyor.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <label className="block text-sm text-zinc-700 dark:text-zinc-300">Personel</label>
              <select
                value={staffId}
                onChange={(e) => setStaffId(e.target.value)}
                className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              >
                <option value="">Seçiniz</option>
                {activeStaff.map((staff) => (
                  <option key={staff.id} value={staff.id}>
                    {staff.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="block text-sm text-zinc-700 dark:text-zinc-300">Hizmet</label>
              <select
                value={serviceId}
                onChange={(e) => setServiceId(e.target.value)}
                className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              >
                <option value="">Seçiniz</option>
                {activeServices.map((service) => (
                  <option key={service.id} value={service.id}>
                    {service.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1">
              <label className="block text-sm text-zinc-700 dark:text-zinc-300">Tarih</label>
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
              />
            </div>
          </div>

          {selectedService && (
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Süre: {selectedService.duration_minutes} dk, Buffer:{" "}
              {selectedService.default_buffer_minutes} dk
            </p>
          )}

          {staffId && serviceId && date && (
            <div className="space-y-2">
              <p className="text-sm text-zinc-700 dark:text-zinc-300">Müsait Saatler</p>
              {slotsLoading && (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
              )}
              {slotsError && <p className="text-sm text-red-600 dark:text-red-400">{slotsError}</p>}
              {!slotsLoading && !slotsError && slots !== null && slots.length === 0 && (
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  Bu tarihte müsait saat yok.
                </p>
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
          )}

          {selectedSlot && (
            <div className="space-y-2">
              <label className="block text-sm text-zinc-700 dark:text-zinc-300">Müşteri</label>
              {selectedCustomer ? (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-black dark:text-zinc-50">
                    {selectedCustomer.display_name || selectedCustomer.whatsapp_number}
                  </span>
                  <button
                    onClick={() => {
                      setSelectedCustomer(null);
                      setCustomerSearch("");
                    }}
                    className="text-zinc-500 hover:underline dark:text-zinc-400"
                  >
                    Değiştir
                  </button>
                </div>
              ) : (
                <div className="relative max-w-sm">
                  <input
                    type="text"
                    placeholder="Ad veya WhatsApp numarası ile ara..."
                    value={customerSearch}
                    onChange={(e) => setCustomerSearch(e.target.value)}
                    className="w-full rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
                  />
                  {customerSearch.trim() !== "" && (
                    <div className="mt-1 max-h-48 overflow-y-auto rounded border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
                      {filteredCustomers.length === 0 ? (
                        <p className="px-3 py-2 text-sm text-zinc-500 dark:text-zinc-400">
                          Sonuç yok.
                        </p>
                      ) : (
                        filteredCustomers.map((customer) => (
                          <button
                            key={customer.id}
                            onClick={() => {
                              setSelectedCustomer(customer);
                              setCustomerSearch("");
                            }}
                            className="block w-full px-3 py-2 text-left text-sm hover:bg-zinc-100 dark:hover:bg-zinc-900"
                          >
                            {customer.display_name || "-"} ({customer.whatsapp_number})
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {formError && <p className="text-sm text-red-600 dark:text-red-400">{formError}</p>}

          <button
            onClick={handleSubmit}
            disabled={!selectedSlot || !selectedCustomer || submitting}
            className="rounded bg-black px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
          >
            {submitting ? "Oluşturuluyor..." : "Randevuyu Oluştur"}
          </button>
        </>
      )}
    </div>
  );
}
