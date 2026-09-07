"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { describeApiError } from "@/lib/errors";
import type { Appointment, Customer, Service, StaffMember } from "@/lib/types";
import NewAppointmentForm from "./NewAppointmentForm";

const STATUS_LABELS: Record<string, string> = {
  pending: "Beklemede",
  confirmed: "Onaylandı",
  cancelled: "İptal Edildi",
  completed: "Tamamlandı",
  no_show: "Gelmedi",
};

const CANCELLABLE_STATUSES = new Set(["pending", "confirmed"]);

export default function AppointmentsPage() {
  const [appointments, setAppointments] = useState<Appointment[] | null>(null);
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [services, setServices] = useState<Service[]>([]);
  const [staffMembers, setStaffMembers] = useState<StaffMember[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  function loadAll() {
    const token = getToken();
    if (!token) return;

    Promise.all([
      api.getAppointments(token),
      api.getCustomers(token),
      api.getServices(token),
      api.getStaffMembers(token),
    ])
      .then(([appointmentsData, customersData, servicesData, staffData]) => {
        setAppointments(appointmentsData);
        setCustomers(customersData);
        setServices(servicesData);
        setStaffMembers(staffData);
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
    return new Date(iso).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
  }

  function handleCreated() {
    setShowForm(false);
    loadAll();
  }

  async function handleCancel(appointment: Appointment) {
    const token = getToken();
    if (!token) return;

    const customerName = customerLabel(appointment.customer_id);
    const when = formatDateTime(appointment.start_at);
    if (!window.confirm(`${customerName} - ${when} randevusunu iptal etmek istediğinize emin misiniz?`)) {
      return;
    }

    setError(null);
    setCancellingId(appointment.id);
    try {
      await api.cancelAppointment(token, appointment.id);
      loadAll();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Randevular</h1>
        {!showForm && (
          <button
            onClick={() => setShowForm(true)}
            className="rounded bg-black px-3 py-2 text-sm font-medium text-white dark:bg-white dark:text-black"
          >
            Yeni Randevu
          </button>
        )}
      </div>

      {showForm && (
        <NewAppointmentForm
          token={getToken() ?? ""}
          staffMembers={staffMembers}
          services={services}
          customers={customers}
          onCreated={handleCreated}
          onCancel={() => setShowForm(false)}
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
          <table className="w-full min-w-[720px] border-collapse text-sm">
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
              {appointments.map((appointment) => (
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
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {STATUS_LABELS[appointment.status] ?? appointment.status}
                  </td>
                  <td className="px-4 py-2 text-right">
                    {CANCELLABLE_STATUSES.has(appointment.status) && (
                      <button
                        onClick={() => handleCancel(appointment)}
                        disabled={cancellingId === appointment.id}
                        className="rounded border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                      >
                        İptal Et
                      </button>
                    )}
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
