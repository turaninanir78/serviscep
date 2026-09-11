"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { LegalDocument } from "@/lib/types";

const TYPE_LABELS: Record<string, string> = {
  terms_of_service: "Kullanım Şartları",
  privacy_notice: "Aydınlatma Metni",
};

export function LegalDocumentModal({ type, onClose }: { type: string; onClose: () => void }) {
  const [document, setDocument] = useState<LegalDocument | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getLegalDocument(type)
      .then((doc) => {
        if (!cancelled) setDocument(doc);
      })
      .catch(() => {
        if (!cancelled) setError("Doküman yüklenemedi.");
      });
    return () => {
      cancelled = true;
    };
  }, [type]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-lg bg-white p-6 dark:bg-zinc-950"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-black dark:text-zinc-50">
            {TYPE_LABELS[type] ?? type}
            {document && ` (${document.version})`}
          </h2>
          <button
            onClick={onClose}
            className="text-sm text-zinc-500 underline hover:text-black dark:hover:text-zinc-50"
          >
            Kapat
          </button>
        </div>

        {error && <p className="text-sm text-red-600 dark:text-red-400">{error}</p>}
        {!error && !document && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">Yükleniyor...</p>
        )}
        {document && (
          <p className="whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-300">
            {document.content}
          </p>
        )}
      </div>
    </div>
  );
}
