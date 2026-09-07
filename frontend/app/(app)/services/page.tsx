"use client";

import { useEffect, useState, type FormEvent } from "react";

import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { describeApiError } from "@/lib/errors";
import type { Service } from "@/lib/types";

export default function ServicesPage() {
  const [services, setServices] = useState<Service[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [duration, setDuration] = useState("");
  const [price, setPrice] = useState("");
  const [buffer, setBuffer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  function loadServices(token: string) {
    api
      .getServices(token)
      .then(setServices)
      .catch((err) => setError(describeApiError(err)));
  }

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    loadServices(token);
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const token = getToken();
    if (!token) return;

    setError(null);
    setSubmitting(true);
    try {
      await api.createService(token, {
        name,
        duration_minutes: Number(duration),
        price: price ? Number(price) : undefined,
        default_buffer_minutes: buffer ? Number(buffer) : undefined,
      });
      setName("");
      setDuration("");
      setPrice("");
      setBuffer("");
      loadServices(token);
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(service: Service) {
    const token = getToken();
    if (!token) return;

    setError(null);
    setTogglingId(service.id);
    try {
      await api.updateService(token, service.id, { is_active: !service.is_active });
      loadServices(token);
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Hizmetler</h1>

      <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label htmlFor="serviceName" className="block text-sm text-zinc-700 dark:text-zinc-300">
            Ad
          </label>
          <input
            id="serviceName"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-40 rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="serviceDuration" className="block text-sm text-zinc-700 dark:text-zinc-300">
            Süre (dk)
          </label>
          <input
            id="serviceDuration"
            type="number"
            min={1}
            required
            value={duration}
            onChange={(e) => setDuration(e.target.value)}
            className="w-28 rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="servicePrice" className="block text-sm text-zinc-700 dark:text-zinc-300">
            Fiyat (opsiyonel)
          </label>
          <input
            id="servicePrice"
            type="number"
            min={0}
            step="0.01"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            className="w-28 rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
          />
        </div>
        <div className="space-y-1">
          <label htmlFor="serviceBuffer" className="block text-sm text-zinc-700 dark:text-zinc-300">
            Buffer (dk, opsiyonel)
          </label>
          <input
            id="serviceBuffer"
            type="number"
            min={0}
            value={buffer}
            onChange={(e) => setBuffer(e.target.value)}
            className="w-32 rounded border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-50"
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

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {services === null && !error && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
      )}

      {services !== null && services.length === 0 && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Henüz hizmet yok.</p>
      )}

      {services !== null && services.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="w-full min-w-[640px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-800 dark:bg-zinc-900">
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Ad</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Süre (dk)</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Fiyat</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Buffer (dk)</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Durum</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {services.map((service) => (
                <tr
                  key={service.id}
                  className="border-b border-zinc-100 last:border-0 dark:border-zinc-900"
                >
                  <td className="px-4 py-2 text-black dark:text-zinc-50">{service.name}</td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {service.duration_minutes}
                  </td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {service.price ?? "-"}
                  </td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {service.default_buffer_minutes}
                  </td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {service.is_active ? "Aktif" : "Pasif"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => handleToggle(service)}
                      disabled={togglingId === service.id}
                      className="rounded border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                    >
                      {service.is_active ? "Pasif Yap" : "Aktif Yap"}
                    </button>
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
