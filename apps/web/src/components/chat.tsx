"use client";

import { useState } from "react";
import { ArrowUp, FileText, Sparkles } from "lucide-react";
import type { AnswerResult, Citation } from "@/lib/types";
import { api } from "@/lib/api";
import { CitationRail } from "./citation-rail";
import { RefusalCard } from "./refusal-card";

type Message =
  { role: "user"; text: string } | { role: "assistant"; result: AnswerResult };

const SUGGESTIONS = [
  "What is the role of a vector store?",
  "How does a Document Loader read a PDF?",
  "Why are PDFs important for AI applications?",
  "Which Python class loads PDFs in LangChain?",
];

export function Chat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);
  const [selectedCitations, setSelectedCitations] = useState<Citation[] | null>(
    null,
  );

  async function send(text: string) {
    if (!text.trim() || pending) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setPending(true);
    try {
      const result = await api.ask({ question: text });
      setMessages((m) => [...m, { role: "assistant", result }]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          result: {
            status: "rejected_security",
            answer: null,
            citations: [],
            cost: {
              prompt_tokens: 0,
              completion_tokens: 0,
              embed_tokens: 0,
              usd_estimate: 0,
            },
            latency_ms: 0,
            config: { error: message },
          },
        },
      ]);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex h-[calc(100vh-3.5rem)]">
      {/* Conversation */}
      <div className="flex flex-1 flex-col">
        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-6 py-12">
            {messages.length === 0 ? (
              <EmptyState onPrompt={send} />
            ) : (
              <ul className="space-y-10">
                {messages.map((m, i) => (
                  <li key={i} className="fade-in">
                    {m.role === "user" ? (
                      <UserBubble text={m.text} />
                    ) : (
                      <AssistantBubble
                        result={m.result}
                        onShowCitations={(c) => setSelectedCitations(c)}
                      />
                    )}
                  </li>
                ))}
                {pending && <PendingBubble />}
              </ul>
            )}
          </div>
        </div>
        <Composer
          value={input}
          onChange={setInput}
          onSend={() => send(input)}
          pending={pending}
        />
      </div>

      {/* Citation rail */}
      {selectedCitations && (
        <CitationRail
          citations={selectedCitations}
          onClose={() => setSelectedCitations(null)}
        />
      )}
    </div>
  );
}

// ─── Sub-components ──────────────────────────────────────────────────────

function EmptyState({ onPrompt }: { onPrompt: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center pt-16 text-center">
      <div className="accent-gradient mb-6 flex h-12 w-12 items-center justify-center rounded-lg">
        <Sparkles className="h-6 w-6 text-white" strokeWidth={1.5} />
      </div>
      <h1 className="font-serif text-5xl italic tracking-tight">
        Ask a document.
      </h1>
      <p className="mt-3 max-w-md text-sm text-text-muted">
        Every answer carries a citation back to a real page. If the document
        doesn&apos;t say it, we&apos;ll say so.
      </p>
      <div className="mt-12 grid w-full max-w-2xl grid-cols-2 gap-2 text-left">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            onClick={() => onPrompt(s)}
            className="hairline rounded-md bg-surface px-4 py-3 text-sm text-text-muted transition-colors hover:border-border-strong hover:text-text"
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="rounded-lg bg-surface px-4 py-2.5 text-sm">{text}</div>
    </div>
  );
}

function AssistantBubble({
  result,
  onShowCitations,
}: {
  result: AnswerResult;
  onShowCitations: (c: Citation[]) => void;
}) {
  if (result.status === "answered" && result.answer) {
    return (
      <div className="space-y-4">
        <div className="prose prose-invert max-w-none text-[15px] leading-relaxed">
          {result.answer}
        </div>
        <CitationsRow
          citations={result.citations}
          onShow={() => onShowCitations(result.citations)}
        />
        <FooterStats
          latencyMs={result.latency_ms}
          cost={result.cost.usd_estimate}
        />
      </div>
    );
  }
  if (result.status === "not_found") {
    return <RefusalCard reason="No cited passage supports this answer." />;
  }
  if (result.status === "rejected_budget") {
    const kind = (result.config.kind as string) || "query";
    const cap = result.config.cap_usd as number | undefined;
    return (
      <RefusalCard
        reason="Budget cap reached."
        detail={`${kind} cap${cap ? ` of $${cap.toFixed(2)}` : ""} blocked this request. Reset at midnight UTC.`}
        tone="warning"
      />
    );
  }
  if (result.status === "rejected_security") {
    return (
      <RefusalCard
        reason="Request rejected."
        detail={(result.config.error as string) || "See server logs."}
        tone="error"
      />
    );
  }
  return (
    <RefusalCard reason={`Unexpected status: ${result.status}`} tone="error" />
  );
}

function CitationsRow({
  citations,
  onShow,
}: {
  citations: Citation[];
  onShow: () => void;
}) {
  if (citations.length === 0) return null;
  return (
    <button
      onClick={onShow}
      className="group flex items-center gap-2 rounded-md border border-border bg-surface/50 px-3 py-2 text-xs text-text-muted transition-colors hover:border-border-strong hover:text-text"
    >
      <FileText className="h-3.5 w-3.5" strokeWidth={1.5} />
      <span>
        {citations.length} citation{citations.length === 1 ? "" : "s"}
      </span>
      <span className="mono-num ml-2 text-text-faint">
        p.{citations.map((c) => c.page).join(", ")}
      </span>
      <span className="ml-2 text-text-faint group-hover:text-text-muted">
        open →
      </span>
    </button>
  );
}

function FooterStats({ latencyMs, cost }: { latencyMs: number; cost: number }) {
  return (
    <div className="mono-num flex items-center gap-3 text-xs text-text-faint">
      <span>{(latencyMs / 1000).toFixed(2)}s</span>
      <span>·</span>
      <span>${cost.toFixed(6)}</span>
    </div>
  );
}

function PendingBubble() {
  return (
    <li className="fade-in">
      <div className="flex items-center gap-2 text-xs text-text-muted">
        <span className="pulse-dot inline-block h-1.5 w-1.5 rounded-full bg-accent" />
        Retrieving and grounding…
      </div>
    </li>
  );
}

function Composer({
  value,
  onChange,
  onSend,
  pending,
}: {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  pending: boolean;
}) {
  return (
    <div className="border-t border-border bg-bg">
      <div className="mx-auto max-w-3xl px-6 py-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSend();
          }}
          className="hairline-strong flex items-end gap-2 rounded-lg bg-surface p-2 transition-colors focus-within:border-accent/50"
        >
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                onSend();
              }
            }}
            placeholder="Ask a question…"
            rows={1}
            className="flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-text-faint"
          />
          <button
            type="submit"
            disabled={pending || !value.trim()}
            className="accent-gradient flex h-8 w-8 items-center justify-center rounded-md text-white transition-opacity disabled:opacity-30"
            aria-label="Send"
          >
            <ArrowUp className="h-4 w-4" strokeWidth={2} />
          </button>
        </form>
        <p className="mt-2 text-center text-[11px] text-text-faint">
          ⌘+Enter to send · answers cite source pages
        </p>
      </div>
    </div>
  );
}
