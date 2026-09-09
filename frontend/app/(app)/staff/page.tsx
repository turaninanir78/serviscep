"use client";

import { useEffect, useState, type FormEvent } from "react";

import { api } from "@/lib/api";
import { describeApiError } from "@/lib/errors";
import type { StaffMember } from "@/lib/types";

export default function StaffPage() {
  const [staffMembers, setStaffMembers] = useState<StaffMember[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  function loadStaffMembers() {
    api
      .getStaffMembers()
      .then(setStaffMembers)
      .catch((err) => setError(describeApiError(err)));
  }

  useEffect(() => {
    loadStaffMembers();
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();

    setError(null);
    setSubmitting(true);
    try {
      await api.createStaffMember({ name });
      setName("");
      loadStaffMembers();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(staff: StaffMember) {
    setError(null);
    setTogglingId(staff.id);
    try {
      await api.updateStaffMember(staff.id, { is_active: !staff.is_active });
      loadStaffMembers();
    } catch (err) {
      setError(describeApiError(err));
    } finally {
      setTogglingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold text-black dark:text-zinc-50">Personel</h1>

      <form onSubmit={handleSubmit} className="flex items-end gap-3">
        <div className="space-y-1">
          <label htmlFor="staffName" className="block text-sm text-zinc-700 dark:text-zinc-300">
            Ad
          </label>
          <input
            id="staffName"
            type="text"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
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

      {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}

      {staffMembers === null && !error && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
      )}

      {staffMembers !== null && staffMembers.length === 0 && (
        <p className="text-sm text-zinc-500 dark:text-zinc-400">Henüz personel yok.</p>
      )}

      {staffMembers !== null && staffMembers.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
          <table className="w-full min-w-[480px] border-collapse text-sm">
            <thead>
              <tr className="border-b border-zinc-200 bg-zinc-50 text-left dark:border-zinc-800 dark:bg-zinc-900">
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Ad</th>
                <th className="px-4 py-2 font-medium text-zinc-600 dark:text-zinc-400">Durum</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {staffMembers.map((staff) => (
                <tr
                  key={staff.id}
                  className="border-b border-zinc-100 last:border-0 dark:border-zinc-900"
                >
                  <td className="px-4 py-2 text-black dark:text-zinc-50">{staff.name}</td>
                  <td className="px-4 py-2 text-black dark:text-zinc-50">
                    {staff.is_active ? "Aktif" : "Pasif"}
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button
                      onClick={() => handleToggle(staff)}
                      disabled={togglingId === staff.id}
                      className="rounded border border-zinc-300 px-3 py-1 text-xs text-zinc-700 hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-900"
                    >
                      {staff.is_active ? "Pasif Yap" : "Aktif Yap"}
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
