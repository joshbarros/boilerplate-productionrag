# Phase 0 Research: Regulatory Document QA

**Date**: 2026-07-07 · All decisions checked against `.specify/memory/constitution.md`. Evidence sources: practitioner scan (`docs/research/reddit-rag-scan-2026-07.md`, n=139), freeCodeCamp production-RAG course notes (`~/CAREER-RESEARCH/RAG-COURSE-GOLD.md`), job-market analysis (`~/CAREER-RESEARCH/`, N=1,894).

## D1. Language & runtime — Python 3.12 + uv
**Rationale**: Python is in 33% of target job postings and every AI-eng library's first-class citizen; uv gives deterministic, fast envs. **Alternatives**: TypeScript (kept for MCP client examples only); Go (no ecosystem for evals/rerankers).

## D2. Vector backends — pgvector (primary) + Qdrant (benchmark arm)
**Rationale (Constitution II)**: Postgres is already the system-of-record; HNSW on pgvector is production-adequate at the 500k-chunk target; TCO evidence: self-hosted pgvector cheapest at every scale ($300 vs $1,500+/mo at 50M vectors). Qdrant stays in compose as a measured comparison — the published pgvector-vs-Qdrant table (recall@k, p95, RAM) is a deliverable. **Alternatives rejected**: Chroma (dev-toy tier, tutorial default = zero differentiation), Pinecone/Weaviate-cloud (violates self-host).

## D3. Keyword arm — Postgres full-text search (tsvector, `portuguese` + `english` configs), fused via Reciprocal Rank Fusion (RRF)
**Rationale (Constitution IV)**: BM25-class keyword retrieval without adding an Elasticsearch container; RRF is simple, tunable, explainable — traceable in a span. **Alternatives**: Elasticsearch/OpenSearch (another JVM service on a single VPS — cost without measured need; revisit if FTS recall disappoints in evals), ParadeDB pg_search (BM25-proper in Postgres; flagged as an experiment task).

## D4. PDF parsing — Docling (primary) with PyMuPDF fast-path; OCR via Docling's engine (Tesseract por+eng)
**Rationale**: messy-PDF parsing is practitioner pain #3 (64/139); Docling handles layout + tables + scanned pages in one self-hosted tool. PyMuPDF fast-path for born-digital PDFs keeps ingestion cheap. **Alternatives**: pypdf/pdfplumber patchwork (weak on tables), cloud parsers (violate self-host boundary), fine-tuned VLM (Reddit-hot but out of v1 scope).

## D5. Chunking — three strategies behind one interface: fixed, recursive, semantic; choice is an eval outcome, not a default
**Rationale (Constitution IV)**: course's own demo showed recursive beating semantic on topic separation — "test, don't assume." Late chunking noted as future experiment (needs specific embedding models).

## D6. Embeddings — OpenAI `text-embedding-3-small` (default) + local `bge-m3` via sentence-transformers (fallback/air-gap arm); both multilingual (PT-BR + EN)
**Rationale**: corpus is bilingual; bge-m3 is the strongest self-hostable multilingual embedder and satisfies the local-mode requirement. Same model MUST be used for indexing and querying (course failure-mode #2); enforced by storing the embedding model id on every chunk and refusing mixed-model search.

## D7. Generation — provider-routed: Anthropic `claude-sonnet-4-6` (quality) / `claude-haiku-4-5-20251001` (cheap default), OpenAI `gpt-4o-mini` (alt), Ollama `qwen3:8b` (degraded/local)
**Rationale (Constitution V + II)**: cheap-first routing with escalation; local fallback is a hard requirement (FR-013). Multi-provider parity mirrors the market (Claude=OpenAI at 5.6% each).

## D8. Reranking — local cross-encoder `BAAI/bge-reranker-v2-m3` (CPU), optional stage measured in evals
**Rationale**: practitioner consensus "reranking + metadata beat model swapping"; must run self-hosted; its uplift must appear in the eval table (Constitution IV) — if it doesn't pay for its latency, evals will show it.

## D9. Evals — custom lightweight runner (Constitution VII), golden set as versioned YAML in repo
Metrics: recall@k (deterministic, from expected-source annotations), citation accuracy (string containment + fuzzy match), faithfulness & relevance (LLM-as-judge with pinned judge model + prompt, temperature 0, judged twice — disagreement flags for human review). Regression gate: any metric −2pts vs baseline (0–100 scale) blocks; runs persisted as JSON + rendered markdown table committed to `evals/results/`. **Alternatives**: ragas (heavier dependency graph, harder to trace; kept as a comparison experiment), promptfoo (JS; better for prompt diffs than pipeline evals).

## D10. Observability — OTel SDK → otel-collector → Prometheus (metrics) + Tempo (traces) + Grafana (dashboards/alerts)
**Rationale (Constitution III)**: real spans per pipeline stage with token/cost attributes; Grafana provisioned dashboards committed to repo. LangSmith explicitly not a runtime dependency. **Alternatives**: Langfuse (good, but vendor-shaped; the OTel story is the owner's differentiation), logs-only (fails Principle III).

## D11. Cache & budget — Postgres tables (content-hash response cache; budget ledger with per-query/daily caps)
**Rationale (Constitution V)**: no Redis container needed at this scale; the ledger IS a feature (FR-010/011). Token estimation pre-call via provider tokenizers; reject-if-over-budget spends $0.

## D12. Security gate — slowapi rate limiting; regex+heuristic injection screen; PII masking (BR patterns: CPF, CNPJ, phone, email) pre-external-call; output validator (citation-presence + schema)
**Rationale (Constitution VI)**: v1 is deterministic and testable; Presidio noted as v2 upgrade. Pre-commit secret scan (gitleaks) required.

## D13. API & MCP — FastAPI (HTTP) + FastMCP (Python MCP SDK) sharing one service layer
**Rationale (Constitution VII)**: both surfaces call identical use-case functions so guarantees can't drift; MCP tools: `ask_documents`, `search_documents`, `get_document_status`, `get_budget_status`.

## D14. Orchestration — plain Python service layer; NO LangChain in the core pipeline
**Rationale (Constitution VII)**: every mechanism explainable/traceable; LangChain used only in `experiments/` for comparisons. This is a deliberate, documented divergence from the course scaffolding.

## D15. Migrations & testing — Alembic; pytest (unit) + compose-based integration tests in GitHub Actions; golden-path e2e = quickstart script
**Rationale**: boring, standard, CI-provable. Eval run on PR = the special addition (Constitution I).
