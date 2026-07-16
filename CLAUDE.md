# production-rag — agent context

Self-hosted, citation-grounded document QA for messy regulatory/fiscal PDFs (PT-BR + EN).

## Layout
```
packages/core/          # ragcore engine (FastAPI + MCP + pipeline)
apps/web/               # Next.js UI
apps/medical|legal|accounting/
infra/                  # docker-compose: postgres, qdrant, otel, prom, tempo, grafana
```

## Stack
Python 3.12 + uv · FastAPI + FastMCP · Postgres/pgvector · Qdrant · hybrid RRF ·
rerank (cross-encoder + lexical fallback) · Docling/PyMuPDF · OpenRouter/… ·
OTel → collector → Tempo/Prometheus/Grafana · pytest · Next.js 15

## Hard rules
- NO LangChain in `src/`
- `api/` and `mcp_server/` call ONLY `ragcore.service`
- answered ⇒ ≥1 verified citation else `not_found`
- Budget pre-check before LLM
- Embedding model pinned; mixed-model search raises

## Backends
| `VECTOR_BACKEND` | Behavior |
| --- | --- |
| `memory` | default, CI |
| `postgres` | pgvector + FTS |
| `qdrant` | Qdrant vectors + in-memory keyword |

`QDRANT_BENCH_ENABLED=true` dual-writes to collection `chunks_bench`.

## Rerank
`RERANK_ENABLED=true` (default). `RERANK_CROSS_ENCODER=true` (default) with
lexical fallback. CI uses `RERANK_CROSS_ENCODER=false`.

## Commands
```bash
make test
make eval-gate
make eval-matrix
make up / make obs
```

## Current state (v0.3)
Cite-or-refuse MVP, Postgres path, niches, multipart upload, offline golden
gate (22+50), Qdrant arm, always-on rerank, OTel compose stack, config matrix.
