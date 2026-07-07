# Production RAG

Self-hosted, citation-grounded document QA for regulatory and fiscal PDFs.

## Current Status

Implemented and validated:

- Phase 2 foundation:
  - SQLAlchemy models
  - Alembic wiring
  - OpenTelemetry stage decorator
  - Shared service-layer skeleton
- Phase 3 MVP (US1):
  - PDF ingest (PyMuPDF fast path)
  - Recursive chunking
  - Embedding provider abstraction
  - Hybrid retrieval (vector + keyword + RRF)
  - Grounded generation with cite-or-refuse behavior
  - FastAPI surface: health, ask, search, ingest
- OpenRouter free-model routing:
  - Default provider set to OpenRouter
  - Reasoning-effort knob for reasoning models
- Phase 4 MCP surface:
  - Tools: ask_documents, search_documents, ingest_document, health
  - Streamable HTTP transport
  - Auth + structured tool errors

## Project Layout

- src/ragcore/service.py: shared use-case layer used by API and MCP
- src/ragcore/api/app.py: FastAPI app
- src/ragcore/mcp_server/app.py: FastMCP app
- src/ragcore/ingestion: PDF loading
- src/ragcore/chunking: chunk strategies
- src/ragcore/embedding: embedder providers
- src/ragcore/retrieval: vector, keyword, and fusion
- src/ragcore/generation: router, prompts, grounding
- tests: unit, integration, and e2e coverage

## API Endpoints

Base: /v1

- GET /health
- POST /ask
- POST /search
- POST /documents

Auth: Bearer token via API_TOKEN from environment.

## MCP Tools

- ask_documents
- search_documents
- ingest_document
- health

Default transport: streamable-http on port 8801.

## Configuration

Main settings live in src/ragcore/config.py and are loaded from .env.

Key variables:

- OPENROUTER_API_KEY
- OPENROUTER_BASE_URL
- OPENROUTER_DEFAULT_MODEL
- OPENROUTER_REASONING_EFFORT
- API_TOKEN

## Run Locally

Install deps:

- uv sync

Run API:

- make api

Run MCP server:

- make mcp

Lint:

- make lint

Tests:

- make test

## Validation Snapshot

Most recent local checks before this README update:

- Ruff: pass
- Pytest: 17 passed
- MCP stress (deterministic local path):
  - 470 concurrent mixed requests, 0 failures
  - p50 0.08 ms, p95 0.36 ms, p99 7.13 ms
  - expected error semantics validated under concurrent invalid input/auth load

## Notes

- Current ingestion path targets born-digital PDFs.
- OCR-heavy ingestion hardening is planned in next phases.
- In-memory retrieval stores are used in MVP paths; production pgvector backend is wired in project design.
