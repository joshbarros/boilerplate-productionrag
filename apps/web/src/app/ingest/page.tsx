"use client";

import { useRef, useState } from "react";
import {
  FileUp,
  CheckCircle2,
  AlertCircle,
  Copy,
  Loader2,
  Upload,
} from "lucide-react";
import { TopNav } from "@/components/top-nav";
import { api } from "@/lib/api";
import type { DocumentStatus } from "@/lib/types";
import { cn } from "@/lib/cn";

export default function IngestPage() {
  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-3xl px-6 py-16">
        <header className="mb-10">
          <div className="eyebrow">Documents</div>
          <h1 className="mt-2 font-serif text-4xl italic tracking-tight">
            Ingest documents
          </h1>
          <p className="mt-3 text-sm text-text-muted">
            Upload PDFs from your browser, or paste server paths for batch
            jobs. Each file is hashed, chunked, embedded, and indexed. OCR
            fallback handles scanned PDFs automatically.
          </p>
        </header>
        <div className="space-y-10">
          <UploadForm />
          <PathForm />
        </div>
      </main>
    </>
  );
}

function UploadForm() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [results, setResults] = useState<DocumentStatus[] | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  function onPick(list: FileList | null) {
    if (!list) return;
    setFiles(Array.from(list));
    setResults(null);
    setError(null);
  }

  async function submit() {
    if (files.length === 0) return;
    setPending(true);
    setError(null);
    try {
      const out = await api.upload(files);
      setResults(out.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="eyebrow">Browser upload</div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          onPick(e.dataTransfer.files);
        }}
        className={cn(
          "hairline-strong flex flex-col items-center justify-center rounded-lg bg-surface px-6 py-12 text-center transition-colors",
          dragging && "border-accent/50 bg-accent/5",
        )}
      >
        <Upload className="mb-3 h-8 w-8 text-text-muted" strokeWidth={1.5} />
        <p className="text-sm text-text">
          Drop PDF, Markdown, or text files here
        </p>
        <p className="mt-1 text-xs text-text-faint">or</p>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="mt-3 hairline rounded-md bg-bg px-3 py-1.5 text-xs text-text-muted hover:text-text"
        >
          Choose files
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.md,.txt,application/pdf,text/markdown,text/plain"
          multiple
          className="hidden"
          onChange={(e) => onPick(e.target.files)}
        />
        {files.length > 0 && (
          <ul className="mt-4 w-full max-w-md space-y-1 text-left">
            {files.map((f) => (
              <li
                key={`${f.name}-${f.size}`}
                className="mono-num truncate text-xs text-text-muted"
              >
                {f.name} · {(f.size / 1024).toFixed(1)} KB
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="flex items-center justify-between">
        <div className="eyebrow">{files.length} file(s) selected</div>
        <button
          onClick={submit}
          disabled={pending || files.length === 0}
          className="accent-gradient flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium text-white transition-opacity disabled:opacity-30"
        >
          {pending ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Uploading…
            </>
          ) : (
            <>
              <FileUp className="h-3.5 w-3.5" strokeWidth={2} />
              Upload &amp; ingest
            </>
          )}
        </button>
      </div>
      {error && (
        <div className="hairline rounded-md border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}
      {results && <ResultsList results={results} />}
    </section>
  );
}

function PathForm() {
  const [paths, setPaths] = useState("");
  const [results, setResults] = useState<DocumentStatus[] | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const list = paths
      .split("\n")
      .map((p) => p.trim())
      .filter(Boolean);
    if (list.length === 0) return;
    setPending(true);
    setError(null);
    try {
      const out = await api.ingestBatch(list);
      setResults(out.results);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="space-y-4">
      <div className="eyebrow">Server paths (advanced)</div>
      <div className="hairline-strong rounded-lg bg-surface p-4">
        <textarea
          value={paths}
          onChange={(e) => setPaths(e.target.value)}
          placeholder={
            "/Users/me/papers/tax-law-2026.pdf\n/Users/me/papers/q1-circular.pdf"
          }
          rows={4}
          className="mono-num w-full resize-none bg-transparent text-sm outline-none placeholder:text-text-faint"
        />
        <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
          <div className="eyebrow">
            {paths.split("\n").filter((p) => p.trim()).length} path(s)
          </div>
          <button
            onClick={submit}
            disabled={pending || !paths.trim()}
            className="hairline flex items-center gap-2 rounded-md bg-bg px-4 py-2 text-sm text-text-muted transition-colors hover:text-text disabled:opacity-30"
          >
            {pending ? (
              <>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Ingesting…
              </>
            ) : (
              "Ingest paths"
            )}
          </button>
        </div>
      </div>
      {error && (
        <div className="hairline rounded-md border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
          {error}
        </div>
      )}
      {results && <ResultsList results={results} />}
    </section>
  );
}

function ResultsList({ results }: { results: DocumentStatus[] }) {
  return (
    <div className="hairline rounded-lg bg-surface">
      <div className="border-b border-border px-4 py-3">
        <div className="eyebrow">Results</div>
      </div>
      <ul>
        {results.map((r, i) => (
          <li
            key={`${r.id}-${i}`}
            className="flex items-center justify-between border-b border-border px-4 py-3 last:border-0"
          >
            <div className="flex min-w-0 items-center gap-3">
              <StatusIcon status={r.status} />
              <div className="min-w-0">
                <div className="mono-num truncate text-sm">{r.filename}</div>
                {r.failure_reason && (
                  <div className="mt-0.5 truncate text-xs text-text-faint">
                    {r.failure_reason}
                  </div>
                )}
              </div>
            </div>
            <div className="mono-num flex shrink-0 items-center gap-4 text-xs text-text-muted">
              <span>p. {r.page_count}</span>
              <span
                className={cn(
                  "uppercase tracking-wider",
                  statusColor(r.status),
                )}
              >
                {r.status}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

function StatusIcon({ status }: { status: string }) {
  if (status === "succeeded")
    return <CheckCircle2 className="h-4 w-4 text-success" strokeWidth={1.5} />;
  if (status === "duplicate")
    return <Copy className="h-4 w-4 text-text-faint" strokeWidth={1.5} />;
  return <AlertCircle className="h-4 w-4 text-error" strokeWidth={1.5} />;
}

function statusColor(status: string): string {
  if (status === "succeeded") return "text-success";
  if (status === "duplicate") return "text-text-faint";
  return "text-error";
}
