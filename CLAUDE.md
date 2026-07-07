# production-rag — agent context

Self-hosted, citation-grounded document QA for messy regulatory/fiscal PDFs (PT-BR + EN). Spec-driven repo: **read the governing docs before writing code.**

## Read in this order
1. `.specify/memory/constitution.md` — 7 non-negotiable principles (evals gate merges; compose-first self-host; OTel not vendor-lock; hybrid retrieval; cost-as-feature; security gate; framework-light)
2. `specs/001-regulatory-doc-qa/spec.md` — 5 user stories, 18 FRs, 8 success criteria
3. `specs/001-regulatory-doc-qa/plan.md` — stack, structure, constitution check
4. `specs/001-regulatory-doc-qa/research.md` — 15 pinned decisions (D1–D15) with rationale; do not relitigate without updating the doc
5. `specs/001-regulatory-doc-qa/tasks.md` — **the work queue. Execute in order, T001 first.**

## Stack (pinned — see research.md)
Python 3.12 + uv · FastAPI + FastMCP · PostgreSQL 17 + pgvector (Qdrant = benchmark arm only) · Postgres FTS + RRF hybrid · Docling/PyMuPDF + Tesseract (por+eng) · anthropic (haiku default) / openai / Ollama qwen3:8b fallback · sentence-transformers (bge-m3, bge-reranker-v2-m3) · SQLAlchemy + Alembic · OTel → Prometheus/Tempo/Grafana · pytest

## Hard rules
- **NO LangChain/LangGraph in `src/`** — `experiments/` only (constitution VII)
- `api/` and `mcp_server/` call ONLY `src/ragcore/service.py` — never pipeline modules directly
- `answered` responses MUST carry ≥1 verified citation or be downgraded to `not_found`; never fabricate
- Budget check happens BEFORE any external call; rejected = $0 spent
- Every pipeline stage wrapped in `@stage_span` with token/cost attributes
- Embedding model id pinned per chunk; mixed-model search must raise
- Secrets only in `.env` (gitignored); fixtures must contain zero real PII
- **Every phase in tasks.md ends with its commit task — do not batch phases**

## Commands
```bash
uv sync                                   # deps
make up / make down                       # compose stack (infra/docker-compose.yml)
make test                                 # pytest
make eval                                 # eval suite → evals/results/ (regression-gated)
alembic upgrade head                      # migrations
```

## Current state
Specs complete (constitution + spec + plan + research + data-model + contracts + quickstart + tasks). **Implementation not started — next action is T001 in tasks.md.**
