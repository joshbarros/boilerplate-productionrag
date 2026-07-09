"use client";

import { X } from "lucide-react";
import type { Citation } from "@/lib/types";

export function CitationRail({
  citations,
  onClose,
}: {
  citations: Citation[];
  onClose: () => void;
}) {
  return (
    <aside className="w-[360px] shrink-0 border-l border-border bg-surface/30 fade-in">
      <div className="sticky top-0 flex items-center justify-between border-b border-border bg-bg/80 px-5 py-3 backdrop-blur">
        <div>
          <div className="eyebrow">Sources</div>
          <h2 className="mt-0.5 text-sm font-semibold">
            {citations.length} passage{citations.length === 1 ? "" : "s"}
          </h2>
        </div>
        <button
          onClick={onClose}
          className="rounded-md p-1.5 text-text-muted hover:bg-surface hover:text-text"
          aria-label="Close citations"
        >
          <X className="h-4 w-4" strokeWidth={1.5} />
        </button>
      </div>
      <ul className="space-y-4 p-5">
        {citations.map((c, i) => (
          <li
            key={`${c.document_id}-${c.page}-${i}`}
            className="hairline rounded-md bg-surface p-4"
          >
            <div className="flex items-center justify-between text-xs text-text-muted">
              <span className="truncate font-medium">
                {c.title || "Untitled"}
              </span>
              <span className="mono-num text-text-faint">p. {c.page}</span>
            </div>
            <blockquote className="mt-2.5 border-l-2 border-accent/60 pl-3 font-serif text-[15px] italic leading-relaxed text-text-muted">
              {c.excerpt}
            </blockquote>
            {c.support_score != null && (
              <div className="mono-num mt-2.5 text-[11px] text-text-faint">
                support {c.support_score.toFixed(2)}
              </div>
            )}
          </li>
        ))}
      </ul>
    </aside>
  );
}
