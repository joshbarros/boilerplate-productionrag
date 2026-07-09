"use client";

import { useEffect, useState } from "react";
import { TopNav } from "@/components/top-nav";
import { api } from "@/lib/api";
import type { BudgetStatus } from "@/lib/types";
import { TrendingUp, AlertOctagon, Activity, RefreshCw } from "lucide-react";

export default function BudgetPage() {
  const [status, setStatus] = useState<BudgetStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .budget()
      .then(setStatus)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Unknown error"),
      );
  }, []);

  return (
    <>
      <TopNav />
      <main className="mx-auto max-w-3xl px-6 py-16">
        <header className="mb-12 flex items-end justify-between">
          <div>
            <div className="eyebrow">Budget</div>
            <h1 className="mt-2 font-serif text-4xl italic tracking-tight">
              Daily ledger
            </h1>
            <p className="mt-3 text-sm text-text-muted">
              Resets at midnight UTC. Queries are rejected when projected cost
              would breach the cap.
            </p>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="hairline rounded-md bg-surface p-2 text-text-muted hover:text-text"
            aria-label="Refresh"
          >
            <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.5} />
          </button>
        </header>

        {error && (
          <div className="hairline rounded-md border-error/30 bg-error/5 px-4 py-3 text-sm text-error">
            {error}
          </div>
        )}

        {status && (
          <div className="space-y-8">
            <ConsumedCap status={status} />
            <StatRow status={status} />
          </div>
        )}

        {!status && !error && (
          <p className="text-sm text-text-faint">Loading…</p>
        )}
      </main>
    </>
  );
}

function ConsumedCap({ status }: { status: BudgetStatus }) {
  const pct = Math.min(100, (status.consumed_usd / status.cap_usd) * 100);
  return (
    <section className="hairline rounded-lg bg-surface p-8">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="eyebrow">{status.period}</div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="mono-num text-6xl font-medium tracking-tight">
              ${status.consumed_usd.toFixed(2)}
            </span>
            <span className="mono-num text-lg text-text-faint">
              / ${status.cap_usd.toFixed(2)}
            </span>
          </div>
        </div>
        <div className="text-right">
          <div className="eyebrow">Remaining</div>
          <div className="mono-num mt-1 text-2xl text-success">
            ${(status.cap_usd - status.consumed_usd).toFixed(2)}
          </div>
        </div>
      </div>
      <div className="mt-6 h-1.5 w-full overflow-hidden rounded-full bg-bg">
        <div
          className="accent-gradient h-full transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="mt-2 flex justify-between text-xs text-text-faint">
        <span className="mono-num">{pct.toFixed(1)}% used</span>
        <span>scope: {status.scope}</span>
      </div>
    </section>
  );
}

function StatRow({ status }: { status: BudgetStatus }) {
  return (
    <section className="grid grid-cols-2 gap-4">
      <StatCard
        icon={<TrendingUp className="h-4 w-4" strokeWidth={1.5} />}
        label="Per-query cap"
        value={`$${(status.cap_usd / 50).toFixed(2)}`}
        hint="Hard ceiling per single ask"
      />
      <StatCard
        icon={<AlertOctagon className="h-4 w-4" strokeWidth={1.5} />}
        label="Rejected"
        value={String(status.rejected_count)}
        hint={
          status.rejected_count === 0
            ? "No rejections yet"
            : "Over cap this period"
        }
        tone={status.rejected_count > 0 ? "warning" : "neutral"}
      />
    </section>
  );
}

function StatCard({
  icon,
  label,
  value,
  hint,
  tone = "neutral",
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint: string;
  tone?: "neutral" | "warning";
}) {
  return (
    <div className="hairline rounded-lg bg-surface p-5">
      <div className="flex items-center gap-2 text-text-muted">
        {icon}
        <span className="eyebrow">{label}</span>
      </div>
      <div
        className={`mono-num mt-3 text-3xl tracking-tight ${
          tone === "warning" ? "text-warning" : "text-text"
        }`}
      >
        {value}
      </div>
      <p className="mt-1 text-xs text-text-faint">{hint}</p>
    </div>
  );
}
