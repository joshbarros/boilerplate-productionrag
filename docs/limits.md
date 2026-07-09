# Limits & Graceful Degradation

What this system does **not** do at v0.1.0, and how it behaves when pushed
beyond its tested envelope.

## Scale

| Surface | Tested | Design target | Degradation |
| --- | --- | --- | --- |
| Documents per corpus | 1 fixture (2 pages) | 500k chunks (1M pages) | None planned; in-memory store scales linearly |
| Latency p95 | 2.9s (8-case eval) | < 10s SC-005 | Rerank stage adds 200-500ms (Phase 7 T043) |
| Concurrent requests | 470 (MCP stress) | n/a (stateless LLM path) | n/a |
| Cost / query | $0.00 (free model) | Budget-enforced $0.10/query cap | Returns `rejected_budget` |

The 500k-chunk extrapolation in SC-005 assumes a pgvector deployment with
HNSW index; current MVP is in-memory and will not hold that corpus in RAM.

## Storage

- **MVP**: in-memory `InMemoryVectorStore` + `InMemoryKeywordSearch`. Single-process.
  No persistence — restart loses indexed documents.
- **Production path** (deferred): pgvector for vectors, Postgres FTS or BM25 for
  keywords. Schema is wired (Phase 2 migrations), backends are not.

## Known Failure Modes

| Trigger | Observed behavior | Expected behavior |
| --- | --- | --- |
| Budget exhausted (daily or query) | Returns `status: rejected_budget` with `kind` + `cap_usd` | Same (verified in Phase 6 tests) |
| LLM returns no citations | Cite-or-refuse downgrades to `status: not_found` | Same (FR-002/003 enforced) |
| LLM fabricates excerpt | `verify_citations` rejects (word-overlap < 70%) → `not_found` | Same — correct refuse behavior |
| LLM JSON parse fails | `parse_llm_response` returns `not_found` | Same — no crash, no leak |
| `OPENROUTER_API_KEY` missing | Ingest fails fast at service init | Same — fail-loud, not silent |
| `.env` not found | Falls back to empty strings, OpenAI client init fails | Resolved in `c1d5ffb` (absolute .env path) |
| Scanned PDF (no text layer) | PyMuPDF returns sparse text, Docling OCR fallback runs | Same (Phase 5, gated by `ocr_enabled`) |
| Corrupted/truncated PDF | `load_pdf` raises; service catches and reports `failed` per-doc | Same (Phase 5 ingest_batch) |
| Out-of-scope question | Returns `status: not_found`, no citations, no answer | Same — verified 100% in eval (lc-oos-001/002) |

## What "Production" Actually Means Here

The claim in the README is **"validated with golden-set evals on a 2-page
fixture at 75% pass rate"** — not "tested at 500k chunks." Anyone evaluating
this for a real workload should:

1. Drop their own PDF corpus in `tests/fixtures/`
2. Author 20+ golden questions covering their domain
3. Run the live eval and read `docs/eval_results_v*.md`
4. If `pass_rate < 0.70` on their domain, the model or the prompt needs tuning

The cite-or-refuse guard is the safety net. It will not let a fabricated
answer reach a user, but it also means the system *will* refuse correct
answers if the LLM paraphrases instead of quoting. That's a deliberate
trade-off, not a bug.
