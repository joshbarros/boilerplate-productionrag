# Implementation Plan: Regulatory Document QA (Production RAG)

**Branch**: `001-regulatory-doc-qa` | **Date**: 2026-07-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-regulatory-doc-qa/spec.md`

## Summary

Self-hosted, citation-grounded document QA over messy regulatory/fiscal PDFs. Ingestion (Docling+OCR) → three chunking strategies → dual-indexed retrieval (pgvector HNSW + Postgres FTS, RRF fusion, optional local reranker) → provider-routed generation (Claude/OpenAI/Ollama fallback) with hard budget caps → answers that cite or refuse. Quality is enforced by a golden-dataset eval suite whose published table compares every configuration and gates releases; the whole system runs from one docker-compose file with OTel→Prometheus/Tempo/Grafana observability and a security gate at the boundary.

## Technical Context

**Language/Version**: Python 3.12 (uv-managed)

**Primary Dependencies**: FastAPI, FastMCP (MCP SDK), Docling + PyMuPDF, sentence-transformers (bge-m3, bge-reranker-v2-m3), anthropic + openai + ollama clients, SQLAlchemy + Alembic, opentelemetry-sdk, slowapi

**Storage**: PostgreSQL 17 + pgvector (system of record, vectors, FTS, cache, budget ledger, eval history); Qdrant (benchmark arm only)

**Testing**: pytest (unit), compose-based integration tests, eval suite as release gate — all in GitHub Actions

**Target Platform**: Linux single-VPS via docker-compose (dev = macOS, same compose)

**Project Type**: single project — web service + MCP server sharing one service layer

**Performance Goals**: p95 answer latency < 10s at 10k docs / 500k chunks (SC-005); ingestion ≥ 1 page/sec sustained on 4 vCPU

**Constraints**: median cost/query < $0.02 (SC-006); zero external calls once budget exhausted; documents never leave the host; single-command startup < 30 min to first answer (SC-004)

**Scale/Scope**: 10k documents / 500k chunks / single tenant (v1 ceiling, graceful degradation beyond)

## Constitution Check

| Principle | How this plan satisfies it | Status |
|---|---|---|
| I. Evals gate everything | Golden set YAML precedes pipeline code (Phase 3 tasks); eval runner + regression gate in CI; results table committed to `evals/results/` | PASS |
| II. Self-hosted, compose-first | Single `docker-compose.yml`: app, postgres+pgvector, qdrant, ollama, otel-collector, prometheus, tempo, grafana; no managed-cloud core deps; local arms for embed/generate | PASS |
| III. OTel, not vendor lock | Span-per-stage decorators with token/cost/latency attributes; provisioned Grafana dashboards + alert rules in repo; no LangSmith at runtime | PASS |
| IV. Hybrid by default | Retrieval defaults to RRF(vector, FTS); rerank measured; chunking strategy chosen by eval, all three implemented behind one interface | PASS |
| V. Cost is a feature | Pre-call token estimation + reject-over-budget; content-hash cache; per-answer cost report; router cheap-first | PASS |
| VI. Security at boundary | Gate middleware: slowapi rate limit → injection screen → PII mask → handler → output validation; gitleaks pre-commit + CI | PASS |
| VII. Framework-light, outcomes-first | No LangChain in core; plain service layer consumed by both FastAPI and FastMCP; every stage a traceable function | PASS |

**Deviation requiring note**: none. (LangChain appears only in `experiments/`, permitted by VII.)

## Project Structure

### Documentation (this feature)

```text
specs/001-regulatory-doc-qa/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 — 15 pinned decisions (D1–D15)
├── data-model.md        # Phase 1 — entities & tables
├── contracts/
│   └── interfaces.md    # Phase 1 — HTTP API + MCP tools + eval artifact schema
├── quickstart.md        # Phase 1 — clean host → first cited answer
├── checklists/requirements.md
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
src/ragcore/
├── config.py                 # pydantic-settings; every knob env-driven
├── models/                   # SQLAlchemy models (document, chunk, query, answer, citation, golden_case, eval_run, budget, cache)
├── ingestion/                # loader.py (Docling/PyMuPDF routing), ocr.py, dedup.py, status.py
├── chunking/                 # base.py (interface), fixed.py, recursive.py, semantic.py
├── embedding/                # provider.py (openai|bge-m3), model-id pinning & mixed-model guard
├── retrieval/                # vector_pg.py, vector_qdrant.py, fts.py, fusion.py (RRF), rerank.py
├── generation/               # router.py (claude|openai|ollama), prompts.py, grounding.py (cite-or-refuse)
├── budget/                   # estimator.py, ledger.py, cache.py
├── security/                 # gate.py (middleware), injection.py, pii.py (BR patterns), output_validator.py
├── evals/                    # runner.py, metrics/ (recall.py, citation.py, judge.py), regression.py, report.py
├── obs/                      # otel.py (span decorators, token/cost attrs), metrics.py
├── api/                      # FastAPI app, routes/ (documents, ask, search, budget, health)
├── mcp_server/               # FastMCP app exposing ask/search/status/budget tools
└── service.py                # shared use-case layer (the ONLY thing api/ and mcp_server/ call)

evals/
├── golden/golden.yaml        # ≥50 cases, PT-BR + EN
└── results/                  # committed eval tables (md + json)

infra/
├── docker-compose.yml
├── grafana/ (provisioned dashboards + alerts)
├── otel-collector.yaml
└── prometheus.yml

tests/ (unit/, integration/, fixtures/pdfs/)
experiments/                  # LangChain/ragas/ParadeDB comparisons — never imported by src/
```

## Phase 0 → 1 artifacts

- research.md: 15 decisions (D1–D15), each with rationale + rejected alternatives — **complete**
- data-model.md: 9 entities mapped to tables with key constraints — **complete**
- contracts/interfaces.md: HTTP endpoints, MCP tool schemas, eval artifact format — **complete**
- quickstart.md: clean-host runbook proving SC-004 — **complete**

## Implementation phasing (mirrors user-story priorities)

1. **Foundation**: compose skeleton (postgres+pgvector first), config, models, migrations, OTel plumbing, CI with gitleaks + pytest
2. **US1 (P1) MVP**: fixture corpus → recursive chunking → OpenAI embeddings → pgvector + FTS hybrid → Claude generation with cite-or-refuse → cost report. *Demo-able end of this phase.*
3. **US3 (P3) pulled early per Constitution I**: golden set + eval runner + regression gate (evals exist before optimization begins)
4. **US2 (P2)**: Docling ingestion, OCR, dedup, batch status
5. **US4 (P4)**: budget caps, cache, Ollama fallback, dashboards, alerts, security gate hardening
6. **US5 (P5)**: MCP server parity + configuration matrix completion (semantic/fixed chunking, Qdrant arm, reranker) + published comparison table

Note: evals (US3) intentionally precede ingestion hardening (US2) — Constitution I outranks story priority order for sequencing, and the spec's independent-test design permits it (US1+US3 run on the fixture corpus).

## Complexity Tracking

| Item | Why it's justified | Simpler alternative rejected because |
|---|---|---|
| 8 compose services | Prom+Tempo+Grafana+collector are Principle III's minimum honest implementation | logs-only fails "is it expensive/breaking" |
| Qdrant service | benchmark arm is a published deliverable (Principle II) | single-backend table proves nothing |
| Two embedding providers | air-gap requirement (FR-013/15) + eval arm | one provider can't demonstrate local mode |
