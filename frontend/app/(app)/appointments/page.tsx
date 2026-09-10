"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { formatDateTime as formatDateTimeInTimezone } from "@/lib/dates";
import { describeApiError } from "@/lib/errors";
import type { Appointment, Customer, Service, StaffMember } from "@/lib/types";
import NewAppointmentForm from "./NewAppointmentForm";
import RescheduleForm from "./RescheduleForm";

// Tenant timezone'i /tenants/me'den gelene kadar (ilk yukleme anindaki
// kisa an) kullanilacak baslangic degeri - backend'in kolon varsayilaniyla
// ayni (bkz. backend/app/models - Tenant.timezone server_default).
const DEFAULT_TIMEZONE = "Europe/Istanbul";

const STATUS_LABELS: Record<string, string> = {
  pending: "Beklemede",
  confirmed: "Onaylandı",
  cancelled: "İptal Edildi",
  completed: "Tamamlandı",
  no_show: "Gelmedi",
};

const STATUS_BADGE_STYLES: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300",
  confirmed: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300",
  cancelled: "bg-zinc-200 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  completed: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  no_show: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
};

// Bu durumlardaki randevularda aksiyon butonları (iptal, tamamlandı,
// gelmedi, yeniden planla) gösterilir - backend de reschedule/cancel/
// complete/no-show'u sadece bu iki durumdan kabul ediyor.
const ACTIVE_STATUSES = new Set(["pending", "confirmed"]);

type ActiveForm = { type: "create" } | { type: "reschedule"; appointment: Appointment };

export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [timezone, setTimezone] = useState(DEFAULT_TIMEZONE);
  const [error, setError] = useState<string | null>(null);
  const [activeForm, setActiveForm] = useState<ActiveForm | null>(null);
  const [actingOnId, setActingOnId] = useState<number | null>(null);

  function loadAll() {
    Promise.all([
      api.getAppointments(),
      api.getCustomers(),
      api.getServices(),
      api.getStaffMembers(),
      api.getMyTenant(),
    ])
      .then(([appointmentsData, customersData, servicesData, staffData, tenant]) => {
        setAppointments(appointmentsData);
        setCustomers(customersData);
        setServices(servicesData);
        setStaffMembers(staffData);
        setTimezone(tenant.timezone);
      })
      .catch((err) => {
        setError(describeApiError(err));
      });
  }

  useEffect(() => {
    loadAll();
  }, []);

  function customerLabel(id: number): string {
    const customer = customers.find((c) => c.id === id);
    return customer?.display_name || customer?.whatsapp_number || `#${id}`;
  }

  function serviceLabel(id: number): string {
    return services.find((s) => s.id === id)?.name ?? `#${id}`;
  }

  function staffLabel(id: number): string {
    return staffMembers.find((s) => s.id === id)?.name ?? `#${id}`;
  }

  function formatDateTime(iso: string): string {
    return formatDateTimeInTimezone(iso, timezone);
  }

  function handleFormDone() {
    setActiveForm(null);
    loadAll();
  }

  async function handleCancel(appointment: Appointment) {
    const when = formatDateTime(appointment.start_at);
    if (
      !window.confirm(
        `${customerLabel(appointment.customer_id)} - ${when} randevusunu iptal etmek istediğinize emin misiniz?`,
      )
    ) {
      return;
    }

    setError(null);
    setActingOnId(appointment.id);
    try {
      await api.cancelAppointment(appointment.id);
      loadAll();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setActingOnId(null);
    }
  }

  async function handleConfirm(appointment: Appointment) {
    if (!window.confirm("Bu randevu onaylandı olarak işaretlensin mi?")) return;

    setError(null);
    setActingOnId(appointment.id);
    try {
      await api.confirmAppointment(appointment.id);
      loadAll();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setActingOnId(null);
    }
  }

  async function handleComplete(appointment: Appointment) {
    if (!window.confirm("Bu randevu tamamlandı olarak işaretlensin mi?")) return;

    setError(null);
    setActingOnId(appointment.id);
    try {
      await api.completeAppointment(appointment.id);
      loadAll();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setActingOnId(null);
    }
  }

  async function handleNoShow(appointment: Appointment) {
    if (!window.confirm("Bu randevu 'gelmedi' olarak işaretlensin mi?")) return;

    setError(null);
    setActingOnId(appointment.id);
    try {
      await api.markAppointmentNoShow(appointment.id);
      loadAll();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setActingOnId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Randevular</h1>
        {!activeForm && (
          <button
            onClick={() => setActiveForm({ type: "create" })}
            className="rounded bg-black px-3 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
          >
            Yeni Randevu
          </button>
        )}
      </div>

      {activeForm?.type === "create" && (
        <NewAppointmentForm
          staffMembers={staffMembers}
          services={services}
          customers={customers}
          timezone={timezone}
          onCreated={handleFormDone}
          onCancel={() => setActiveForm(null)}
        />
      )}

      {activeForm?.type === "reschedule" && (
        <RescheduleForm
          appointment={activeForm.appointment}
          staffMembers={staffMembers}
          services={services}
          customers={customers}
          timezone={timezone}
          onRescheduled={handleFormDone}
          onCancel={() => setActiveForm(null)}
        />
      )}

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {!error && appointments === null && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
      )}

      {!error && appointments !== null && appointments.length === 0 && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Henüz randevu yok.</p>
      )}

      {!error && appointments !== null && appointments.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="w-full min-w-[820px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-800 dark:bg-zinc-900">
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Müşteri</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Hizmet</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Personel</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Tarih/Saat</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Durum</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {appointments.map((appointment) => {
                const isActive = ACTIVE_STATUSES.has(appointment.status);
                const busy = actingOnId === appointment.id;
                return (
                  <tr
                    key={appointment.id}
                    className="border-b border-zinc-100 last:border-0 dark:border-zinc-900"
                  >
                    <td className="px-4 py-2 text-black dark:text-zinc-50">
                      {customerLabel(appointment.customer_id)}
                    </td>
                    <td className="px-4 py-2 text-black dark:text-zinc-50">
                      {serviceLabel(appointment.service_id)}
                    </td>
                    <td className="px-4 py-2 text-black dark:text-zinc-50">
                      {staffLabel(appointment.staff_id)}
                    </td>
                    <td className="px-4 py-2 text-black dark:text-zinc-50">
                      {formatDateTime(appointment.start_at)}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          STATUS_BADGE_STYLES[appointment.status] ??
                          "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                        }`}
                      >
                        {STATUS_LABELS[appointment.status] ?? appointment.status}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      {isActive && (
                        <div className="flex flex-wrap justify-end gap-1">
                          {appointment.status === "pending" && (
                            <button
                              onClick={() => handleConfirm(appointment)}
                              disabled={busy}
                              className="rounded border border-zinc-300 px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                            >
                              Onayla
                            </button>
                          )}
                          <button
                            onClick={() => setActiveForm({ type: "reschedule", appointment })}
                            disabled={busy}
                            className="rounded border border-zinc-300 px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                          >
                            Yeniden Planla
                          </button>
                          <button
                            onClick={() => handleComplete(appointment)}
                            disabled={busy}
                            className="rounded border border-zinc-300 px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                          >
                            Tamamlandı
                          </button>
                          <button
                            onClick={() => handleNoShow(appointment)}
                            disabled={busy}
                            className="rounded border border-zinc-300 px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                          >
                            Gelmedi
                          </button>
                          <button
                            onClick={() => handleCancel(appointment)}
                            disabled={busy}
                            className="rounded border border-zinc-300 px-2 py-1 text-xs text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                          >
                            İptal Et
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
