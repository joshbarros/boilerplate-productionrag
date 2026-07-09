// Thin client to the Python backend (packages/core → apps/web).
// Multi-niche: each niche has its own backend URL (see niches.ts).
// The active niche is selected via a runtime context (see api-context.tsx).

import type { AnswerResult, BudgetStatus, DocumentStatus } from "./types";
import { NICHES, DEFAULT_NICHE, type Niche } from "./niches";

const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "";

type AskInput = { question: string; top_k?: number };

let _active: Niche = NICHES[0] ?? {
  key: "core",
  label: "Core",
  backend: "/api/backend",
  enabled: true,
};

export function getActiveNiche(): Niche {
  if (typeof window !== "undefined") {
    const stored = window.localStorage.getItem("activeNiche");
    if (stored) {
      const found = NICHES.find((n) => n.key === stored && n.enabled);
      if (found) _active = found;
    }
  }
  return _active;
}

export function setActiveNiche(key: string) {
  const found = NICHES.find((n) => n.key === key && n.enabled);
  if (!found) return;
  _active = found;
  if (typeof window !== "undefined") {
    window.localStorage.setItem("activeNiche", key);
  }
}

function url(path: string): string {
  const niche = getActiveNiche();
  // For relative backends (proxied), prepend the niche prefix
  if (niche.backend.startsWith("/")) {
    return `${niche.backend}${path}`;
  }
  return `${niche.backend}/v1${path}`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(url(path), {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`backend ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  ask: (input: AskInput) =>
    request<AnswerResult>("/ask", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  search: (input: { query: string; top_k?: number; mode?: string }) =>
    request<{ results: unknown[] }>("/search", {
      method: "POST",
      body: JSON.stringify(input),
    }),

  ingest: (file_path: string) =>
    request<{
      status: string;
      fingerprint?: string;
      title?: string;
      chunks?: number;
    }>("/documents", { method: "POST", body: JSON.stringify({ file_path }) }),

  ingestBatch: (file_paths: string[]) =>
    request<{ results: DocumentStatus[] }>("/documents/batch", {
      method: "POST",
      body: JSON.stringify({ file_paths }),
    }),

  budget: () => request<BudgetStatus>("/budget"),

  health: () =>
    request<{
      status: string;
      provider: string;
      model: string;
      documents_indexed: number;
    }>("/health"),
};
