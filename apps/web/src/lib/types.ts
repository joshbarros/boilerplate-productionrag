// Shared types — mirror the Python service layer (src/ragcore/types.py)

export type Citation = {
  document_id: string;
  title: string;
  page: number;
  excerpt: string;
  support_score: number | null;
};

export type CostReport = {
  prompt_tokens: number;
  completion_tokens: number;
  embed_tokens: number;
  usd_estimate: number;
};

export type AnswerResult = {
  status:
    | "answered"
    | "not_found"
    | "degraded"
    | "rejected_budget"
    | "rejected_security";
  answer: string | null;
  citations: Citation[];
  cost: CostReport;
  latency_ms: number;
  config: Record<string, unknown>;
};

export type BudgetStatus = {
  period: string;
  scope: string;
  cap_usd: number;
  consumed_usd: number;
  rejected_count: number;
};

export type DocumentStatus = {
  id: string;
  filename: string;
  status: "succeeded" | "duplicate" | "failed";
  page_count: number;
  failure_reason: string | null;
};
