# Production RAG Constitution

Grounded in market research (N=1,894 US-remote job postings, 2026-07; `~/CAREER-RESEARCH/`), the freeCodeCamp production-RAG failure taxonomy, and the owner's production experience. Every spec, plan, and task is checked against these principles. Violations require an explicit, written justification in the plan's Complexity Tracking section.

## Core Principles

### I. Evals Gate Everything (NON-NEGOTIABLE)
No retrieval or generation change merges without the eval suite running and scores published. A golden dataset (≥50 query/answer pairs with source attributions) exists before the first RAG chain is built. Metrics: retrieval recall@k, answer faithfulness, answer relevance, citation accuracy. Regressions block merge — delta over baseline, not absolute pass-rate. Rationale: 90% of RAG failures are retrieval failures; evaluation is the #1 scarce skill in the hiring market; an eval table is this project's primary published artifact.

### II. Self-Hosted, Compose-First
Every service runs from a single `docker-compose.yml` on commodity hardware (target: one VPS). Vector store: **pgvector (primary)** and **Qdrant (benchmark arm)** — both stay in the compose file, and the pgvector-vs-Qdrant comparison (recall@k, p95 latency, RAM) is a published deliverable. No managed-cloud dependencies for core function (LLM APIs are the sole allowed external calls, and a local-model fallback via Ollama must exist). Rationale: owner self-hosts on VPS; enterprise demand concentrates in regulated/air-gapped doc workloads where "can't send chunks to OpenAI" is the buying trigger.

### III. Observability via OpenTelemetry, Not Vendor Lock
Every pipeline stage (ingest, chunk, embed, retrieve, rerank, generate) emits OTel spans with token counts, cost attribution, and latency as attributes. Dashboards in Grafana; alerting on eval-score regression and cost-per-query drift. LangSmith may be consulted during development but is not a runtime dependency. Rationale: the three pillars (logging, metrics, instrumented LLM calls) answer "is it working / fast / expensive / breaking"; OTel-for-agents is the owner's differentiation vs. 126k course-clone repos.

### IV. Retrieval Is Hybrid by Default
BM25 + vector hybrid search from day one; pure vector search is the fallback, not the default. Reranking is a measured stage, not an assumption — its uplift must appear in the eval table. Chunking strategy is chosen by experiment (fixed vs recursive vs semantic benchmarked on the project corpus), never by tutorial default. Rationale: vector search demonstrably fails on codes, acronyms, and exact identifiers — and the target corpus is full of them; "reranking + metadata beat model swapping" per practitioner consensus.

### V. Cost Is a Feature
Token budgeting before every LLM call: estimate → reject-if-over-budget ($0 spent) → record actuals. Per-query and per-day cost caps enforced in code, response caching with content-hash keys, and a cost dashboard beside the latency one. Model routing (cheap-first, escalate on need) is designed in, not bolted on. Rationale: RAG's economic argument vs long-context is ~25× per query; a system that can't report its own cost per answer is a demo, not a product.

### VI. Security at the Boundary
A gate stands between client and LLM: rate limiting, prompt-injection screening, PII detection and masking on input, output validation before return. Secrets live in `.env` (gitignored, with `.env.example` committed) — enforced by pre-commit scan. No PII or third-party corpus content in the repo. Rationale: the security layer is what separates "$15K production" engagements from "$3K demo" work.

### VII. Framework-Light, Outcomes-First
LangChain/LangGraph may be used where they earn their keep, but every core mechanism (chunking, retrieval, budgeting, evals) must be explainable and replaceable — no chain so magic it can't be traced in an OTel span. Public interfaces are FastAPI + an MCP server exposing retrieval/QA as tools. Rationale: employers name outcomes, not frameworks (LangChain 1.7% of postings and falling; MCP fastest-rising term with near-zero practitioner supply).

## Delivery Constraints

- **Ship-ugly-first:** repo is public from v0.1; README with architecture diagram (Mermaid) before feature-complete; every phase ends in a commit.
- **WIP=1:** one spec in implementation at a time.
- **Definition of done for the project:** README + eval table + compose-up demo + OTel/Grafana screenshots + LinkedIn post live.
- **Corpus:** real, messy, owner-controlled documents (regulatory/fiscal PDFs preferred — acronym-dense, tests Principle IV honestly). Never the tutorial's sample docs.

## Development Workflow

Spec-Kit flow: `/speckit-specify` (what/why) → `/speckit-clarify` → `/speckit-plan` (against this constitution) → `/speckit-tasks` → `/speckit-implement`. Plans must show a Constitution Check section mapping each principle to how the design satisfies it. Tests and eval cases are written with the spec, not after implementation.

## Governance

This constitution supersedes ad-hoc practices for this repo. Amendments: edit this file with a dated changelog line and re-run `/speckit-analyze` on open specs. Version: 1.0.0 | Ratified: 2026-07-07 | Last amended: 2026-07-07
