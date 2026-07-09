// Thin client to the Python backend (apps/backend → apps/web)
// Routes through Next.js rewrites in dev (see next.config.js).
// In prod, the backend sits behind the same domain via reverse proxy.

import type { AnswerResult, BudgetStatus, DocumentStatus } from "./types";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || ""; // empty → use /api/backend proxy
const TOKEN = process.env.NEXT_PUBLIC_API_TOKEN || "";

type AskInput = { question: string; top_k?: number };

function url(path: string): string {
  return BACKEND ? `${BACKEND}/v1${path}` : `/api/backend${path}`;
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
