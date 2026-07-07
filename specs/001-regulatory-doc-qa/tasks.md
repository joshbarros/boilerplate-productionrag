# Tasks: Regulatory Document QA (Production RAG)

**Input**: Design documents from `/specs/001-regulatory-doc-qa/`
**Prerequisites**: plan.md, spec.md, research.md (D1–D15), data-model.md, contracts/interfaces.md

**Format**: `[ID] [P?] [Story] Description` — [P] = parallelizable (different files, no dependency). Every task names exact paths. **Every phase ends with a commit** (constitution: ship-ugly-first).

## Phase 1: Setup

- [ ] T001 Initialize uv project: `pyproject.toml` (python 3.12; deps per plan Technical Context), `src/ragcore/__init__.py`, `.env.example` (all knobs from research D7/D11/D12), extend `.gitignore` (fixtures artifacts, `evals/results/*.json` kept, `.env` already ignored)
- [ ] T002 [P] `infra/docker-compose.yml` v0: `app` (Dockerfile), `postgres` (pgvector/pgvector:pg17, healthcheck), volumes; Makefile targets `up/down/logs/test/eval`
- [ ] T003 [P] CI skeleton `.github/workflows/ci.yml`: uv sync, ruff, pytest, gitleaks secret scan (constitution VI)
- [ ] T004 [P] `src/ragcore/config.py` — pydantic-settings: providers, models (pinned ids from research D6/D7/D8), budgets, rate limits, feature flags (`LOCAL_LLM_ENABLED`, `RERANK_ENABLED`, `QDRANT_BENCH_ENABLED`)
- [ ] T005 Commit: "phase 1: project skeleton, compose v0, CI with secret scan"

**Checkpoint**: `docker compose up postgres` healthy; CI green on empty test suite.

## Phase 2: Foundational (blocks all stories)

- [ ] T006 SQLAlchemy models per data-model.md in `src/ragcore/models/` (documents, chunks, queries, answers, citations, golden_cases, eval_runs, budget_ledger, response_cache) + Alembic init and migration 0001 (extensions: vector, pg_trgm; HNSW + GIN indexes; tsvector generated column)
- [ ] T007 [P] OTel plumbing `src/ragcore/obs/otel.py`: `@stage_span(name)` decorator recording `tokens.*`, `cost.usd`, `config.*` attrs; propagate trace id → `X-Request-Id` (contracts §OTel)
- [ ] T008 [P] `src/ragcore/service.py` skeleton with use-case signatures (`ask`, `search`, `ingest_batch`, `document_status`, `budget_status`) so API/MCP/tests code against one seam (D13)
- [ ] T009 [P] Test fixtures: `tests/fixtures/pdfs/` — assemble 20 PDFs (digital PT-BR fiscal samples with codes/acronyms, scanned pages, table-heavy, 1 corrupted, 1 password-protected) + `tests/fixtures/README.md` documenting provenance/licensing (constitution: no third-party corpus content — owner-generated/public-domain only)
- [ ] T010 Commit: "phase 2: schema, OTel seam, service layer, fixture corpus"

**Checkpoint**: `alembic upgrade head` clean; fixtures documented.

## Phase 3: User Story 1 — cited answers (P1) 🎯 MVP

- [ ] T011 [US1] `src/ragcore/chunking/base.py` (interface: `chunk(document) -> list[Chunk]`) + `recursive.py` (v1 default; fixed/semantic stubs raise NotImplemented with pointer to Phase 7)
- [ ] T012 [P] [US1] `src/ragcore/embedding/provider.py`: openai text-embedding-3-small + model-id pinning; mixed-model guard (refuse search when chunk.embedding_model ≠ query model — course failure #2, research D6)
- [ ] T013 [P] [US1] `src/ragcore/ingestion/loader.py` fast-path only (PyMuPDF digital text extraction) — enough to load fixtures; full Docling path is US2
- [ ] T014 [US1] Retrieval arms: `retrieval/vector_pg.py` (HNSW cosine), `retrieval/fts.py` (websearch_to_tsquery, portuguese+english), `retrieval/fusion.py` (RRF k=60) — each stage span-decorated
- [ ] T015 [US1] `src/ragcore/generation/router.py` (anthropic haiku default → sonnet escalation flag; openai alt) + `prompts.py` (grounded-answer prompt: answer ONLY from passages, cite chunk ids, else refuse) + `grounding.py` (parse citations, verify excerpt containment, compose Answer)
- [ ] T016 [US1] `generation/` cite-or-refuse enforcement: `answered ⇒ ≥1 verified citation` else downgrade to `not_found` (FR-002/003) + cost report assembly on every answer (FR-010)
- [ ] T017 [US1] Wire `service.ask()` end-to-end; `api/` FastAPI app + routes `/v1/ask`, `/v1/search`, `/v1/health` with bearer auth (contracts §HTTP)
- [ ] T018 [P] [US1] Unit tests: fusion ranking math, mixed-model guard, citation containment verifier (`tests/unit/`)
- [ ] T019 [US1] Integration test `tests/integration/test_ask.py`: ingest fixtures → 10 answerable + 3 unanswerable questions → assert citations resolve & zero fabrication (US1 independent test)
- [ ] T020 [US1] Commit: "US1 MVP: hybrid retrieval + grounded generation with citations and cost"

**Checkpoint**: US1 acceptance scenarios 1–4 pass against fixture corpus. **This is the first demo.**

## Phase 4: User Story 3 — evals (P3, pulled early per Constitution I)

- [ ] T021 [US3] `evals/golden/golden.yaml`: ≥50 cases (≥35 PT-BR, ≥10 EN, ≥8 unanswerable, ≥10 exact-code/acronym questions) authored from fixture corpus; schema per data-model golden_cases
- [ ] T022 [P] [US3] Metrics: `evals/metrics/recall.py` (recall@k from expected sources), `citation.py` (containment + fuzzy), `judge.py` (LLM-as-judge, pinned model + prompt, temp 0, double-judge disagreement flag — research D9)
- [ ] T023 [US3] `evals/runner.py`: config-matrix execution, results JSON + rendered md table per contracts §Eval artifact; persist eval_runs row
- [ ] T024 [US3] `evals/regression.py`: baseline comparison, −2pt gate; CI job `eval-gate` (runs on PR label `eval` + on release) failing on regression (FR-009, SC-008)
- [ ] T025 [US3] Baseline run committed to `evals/results/` + README section "Current eval table" linking it
- [ ] T026 [US3] Commit: "US3: golden set, eval runner, regression gate, first baseline"

**Checkpoint**: intentionally degraded config (chunk_size=50) → gate flags regression (US3 independent test).

## Phase 5: User Story 2 — messy ingestion (P2)

- [ ] T027 [US2] `ingestion/loader.py` full: Docling primary (layout+tables), routing born-digital → PyMuPDF fast-path (research D4); per-page `extraction_summary`
- [ ] T028 [P] [US2] OCR path: Docling+Tesseract (por+eng) for scanned pages; span-instrumented (`ingest.ocr`)
- [ ] T029 [P] [US2] `ingestion/dedup.py` (sha256 fingerprint, 409 semantics) + `ingestion/status.py` (batch tracking, graceful per-file failure — corrupted file never aborts batch)
- [ ] T030 [US2] Routes `/v1/documents`, `/v1/documents/{id}`, `/v1/batches/{id}` + `scripts/ingest.sh`
- [ ] T031 [US2] Integration test: 20-fixture batch → status report accuracy, corrupted file isolated, 19 queryable (US2 independent test); extend golden set with 5 scanned-page cases
- [ ] T032 [US2] Commit: "US2: Docling/OCR ingestion, dedup, batch status"

**Checkpoint**: messy fixtures ingest cleanly; eval re-run shows scanned-page recall.

## Phase 6: User Story 4 — operations (P4)

- [ ] T033 [US4] `budget/estimator.py` (pre-call token estimate per provider tokenizer) + `ledger.py` (per-query/daily caps, reject-pre-call 402, consumed tracking) wired into `service.ask` (FR-011)
- [ ] T034 [P] [US4] `budget/cache.py`: content-hash(masked_text+config) response cache with TTL (FR-012)
- [ ] T035 [P] [US4] Ollama fallback: `generation/router.py` degraded mode (qwen3:8b), `degraded` status labeling; `ollama` service in compose (FR-013)
- [ ] T036 [US4] Security gate `security/`: slowapi rate limit → `injection.py` (heuristics + pattern set, tested against OWASP LLM01 samples) → `pii.py` (CPF/CNPJ/phone/email masking pre-external-call) → `output_validator.py` (citation presence, schema) as FastAPI middleware chain (FR-014/015)
- [ ] T037 [P] [US4] Full compose: otel-collector, prometheus, tempo, grafana + provisioned dashboards (`infra/grafana/`: RAG Overview — latency, tokens, $/query, eval trend) + alert rules (cost drift, eval regression) (FR-016)
- [ ] T038 [US4] Integration tests: $0 budget → 402 pre-call + zero external calls (mock transport assertion); provider-down → degraded answer; rate-limit 429; injection blocked 400
- [ ] T039 [US4] Commit: "US4: budgets, cache, local fallback, security gate, dashboards"

**Checkpoint**: US4 independent test passes from clean host (quickstart.md steps 1–6).

## Phase 7: User Story 5 + configuration matrix (P5)

- [ ] T040 [US5] `mcp_server/`: FastMCP tools `ask_documents`, `search_documents`, `get_document_status`, `get_budget_status` calling `service.py`; structured tool errors mirror 402/429/400 (contracts §MCP)
- [ ] T041 [P] [US5] MCP parity test: same guarantees via MCP client as HTTP (US5 independent test)
- [ ] T042 [P] [US5] `chunking/fixed.py` + `chunking/semantic.py` (embedding-similarity boundaries)
- [ ] T043 [P] [US5] `retrieval/rerank.py`: bge-reranker-v2-m3 cross-encoder stage (flag-gated)
- [ ] T044 [US5] `retrieval/vector_qdrant.py` + compose `qdrant` + benchmark writer (eval-pipeline-only, never serving path — data-model note)
- [ ] T045 [US5] Local embedding arm: bge-m3 via sentence-transformers behind `embedding/provider.py` (air-gap mode complete: local embed + Ollama generate)
- [ ] T046 [US5] **Full matrix eval run**: 3 chunking × 3 retrieval × ±rerank × 2 backends → committed table; verify SC-003 (hybrid ≥ +25% recall on code/acronym subset) and pgvector-vs-Qdrant comparison published
- [ ] T047 [US5] Commit: "US5: MCP surface + full configuration matrix with published eval table"

**Checkpoint**: all 5 user stories' independent tests pass; eval table README-linked.

## Phase 8: Polish & ship

- [ ] T048 [P] README.md: value proposition, Mermaid architecture diagram, quickstart link, **latest eval table embedded**, Grafana screenshots, cost-per-query evidence
- [ ] T049 [P] Performance validation: p95 < 10s at fixture scale + documented 500k-chunk extrapolation (SC-005); `docs/limits.md` graceful-degradation notes
- [ ] T050 [P] Repo-history secret/PII audit (gitleaks full-history + manual fixture review) — SC-007
- [ ] T051 Quickstart dry-run on a clean VM, timed < 30 min (SC-004); fix friction found
- [ ] T052 Tag v0.1.0, publish repo public, LinkedIn post (content bank #73: "Everyone has a RAG demo; almost nobody publishes eval numbers")

## Dependencies & parallel guide

```
Setup(1) → Foundational(2) → US1(3) → US3(4) → US2(5) → US4(6) → US5(7) → Polish(8)
Within phases: [P] tasks parallel-safe (different files).
MVP scope = Phases 1–3 (demo) · Credibility scope = +Phase 4 (eval table) · "Production" claim = +Phase 6.
```

**Sequencing note**: US3 before US2/US4 is a constitution-driven deviation from priority order (evals exist before anything is optimized). Documented in plan.md.
