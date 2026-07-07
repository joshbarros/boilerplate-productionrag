# Interface Contracts: Regulatory Document QA

**Date**: 2026-07-07 · Both surfaces call the same `ragcore.service` layer — guarantees cannot drift (FR-017).

## HTTP API (FastAPI, `/v1`)

Auth: `Authorization: Bearer <API_TOKEN>` (single shared token v1). All responses include `X-Request-Id` (= trace id).

### POST /v1/documents
Multipart upload (1..n PDFs). → `202 {batch_id, documents: [{id, filename, status}]}`
Errors: `409` duplicate (returns existing document id), `422` unreadable/password-protected (per-file, batch continues).

### GET /v1/documents/{id} · GET /v1/batches/{batch_id}
→ `200` document/batch status incl. `extraction_summary`, `failure_reason` (US2).

### POST /v1/ask
```json
{ "question": "string", "top_k": 8, "config_override": {"retrieval": "hybrid|vector|keyword", "rerank": true} }
```
→ `200`:
```json
{
  "status": "answered | not_found | degraded",
  "answer": "string | null",
  "citations": [{"document_id": "...", "title": "...", "page": 12, "excerpt": "...", "support_score": 0.91}],
  "cost": {"prompt_tokens": 0, "completion_tokens": 0, "embed_tokens": 0, "usd_estimate": 0.0041},
  "latency_ms": 3210,
  "config": {"chunking": "recursive", "retrieval": "hybrid", "rerank": false, "backend": "pgvector", "model": "claude-haiku-4-5"}
}
```
Guarantees: `answered` ⇒ `citations.length ≥ 1`; `not_found` ⇒ `answer = null`, no fabrication (FR-002/003).
Errors: `429` rate-limited; `402 {reason: "budget_exceeded", scope: "day", cap_usd, consumed_usd}` pre-call rejection (FR-011); `400 {reason: "injection_screen"}`.

### POST /v1/search
Same request shape → raw ranked chunks `[{chunk_id, document_id, page, text, scores: {vector, keyword, fused, rerank}}]` — the retrieval-only surface (debugging + MCP parity).

### GET /v1/budget · GET /v1/health
Ledger snapshot (caps, consumed, rejected_count) · liveness/readiness incl. provider reachability + degraded-mode flag.

## MCP Server (FastMCP, streamable-http on :8801)

| Tool | Input schema | Returns |
|---|---|---|
| `ask_documents` | `{question: str, top_k?: int}` | same JSON as /v1/ask (status, answer, citations, cost) |
| `search_documents` | `{query: str, top_k?: int, mode?: "hybrid"\|"vector"\|"keyword"}` | ranked chunks with scores + citation anchors |
| `get_document_status` | `{document_id?: str, batch_id?: str}` | ingestion status objects |
| `get_budget_status` | `{}` | ledger snapshot |

Rules: tool descriptions ≤ 3 sentences, results truncated to configurable token budget (context hygiene), same 402/429/400 semantics surfaced as structured tool errors (US5-AS2).

## Eval artifact contract (`evals/results/<timestamp>-<git_sha>.json` + `.md`)

```json
{
  "run_id": "...", "git_sha": "...", "started_at": "...",
  "golden_set": {"total": 50, "answerable": 42, "unanswerable": 8, "excluded": 0},
  "matrix": [
    {"config": {"chunking": "recursive", "retrieval": "hybrid", "rerank": true, "backend": "pgvector", "embedding": "text-embedding-3-small"},
     "scores": {"recall_at_8": 0.87, "faithfulness": 0.92, "relevance": 0.90, "citation_accuracy": 0.94},
     "cost_usd_total": 0.61, "p95_latency_ms": 4100}
  ],
  "baseline_run_id": "...", "verdict": "pass",
  "regressions": []
}
```
The rendered `.md` table is the publishable artifact (README links the latest). CI job `eval-gate` fails the build on `verdict: "regression"` (FR-009, SC-008).

## OTel span contract (per request)
`gate → retrieve.embed → retrieve.vector | retrieve.keyword → retrieve.fuse → retrieve.rerank? → generate → validate`
Required attributes on every span: `tokens.prompt`, `tokens.completion`, `cost.usd`, `config.*`; trace id returned to caller as `X-Request-Id`.
