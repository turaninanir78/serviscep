"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  status: string;
  database: boolean;
};

type HealthState =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error" };

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL ?? "";

export default function Home() {
  const [health, setHealth] = useState<HealthState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;

    fetch(`${BACKEND_URL}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<HealthResponse>;
      })
      .then((data) => {
        if (!cancelled) setHealth({ kind: "ok", data });
      })
      .catch(() => {
        if (!cancelled) setHealth({ kind: "error" });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 bg-zinc-50 font-sans dark:bg-black">
      <h1 className="text-2xl font-semibold text-black dark:text-zinc-50">
        ServisCep
      </h1>
      {health.kind === "loading" && (
        <p className="text-zinc-600 dark:text-zinc-400">Backend: checking...</p>
      )}
      {health.kind === "ok" && (
        <p className="text-zinc-600 dark:text-zinc-400">
          Backend: OK (database: {health.data.database ? "connected" : "unreachable"})
        </p>
      )}
      {health.kind === "error" && (
        <p className="text-zinc-600 dark:text-zinc-400">Backend: unreachable</p>
      )}
    </div>
  );
}
