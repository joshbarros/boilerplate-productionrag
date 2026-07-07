# Quickstart: clean host → first cited answer (< 30 min, SC-004)

## Prerequisites
Docker + Docker Compose v2. 8 GB RAM recommended (Ollama fallback model included; set `LOCAL_LLM_ENABLED=false` on 4 GB hosts).

## 1. Configure (2 min)
```bash
git clone <repo> && cd production-rag
cp .env.example .env
# set: ANTHROPIC_API_KEY or OPENAI_API_KEY (either works; both = router chooses)
# optional: DAILY_BUDGET_USD=1.00  QUERY_BUDGET_USD=0.05  API_TOKEN=<choose one>
```

## 2. Bring it up (5–10 min first pull)
```bash
docker compose -f infra/docker-compose.yml up -d
docker compose -f infra/docker-compose.yml ps   # all services healthy
curl -s localhost:8800/v1/health | jq            # readiness incl. provider checks
```
Services: `app` (API :8800 + MCP :8801), `postgres` (pgvector), `qdrant` (benchmark only), `ollama`, `otel-collector`, `prometheus`, `tempo`, `grafana` (:3000, admin/admin on first run).

## 3. Ingest the fixture corpus (3 min)
```bash
./scripts/ingest.sh tests/fixtures/pdfs/          # or: curl -F "files=@doc.pdf" -H "Authorization: Bearer $API_TOKEN" localhost:8800/v1/documents
curl -s -H "Authorization: Bearer $API_TOKEN" localhost:8800/v1/batches/<batch_id> | jq '.documents[].status'
```

## 4. Ask (the demo)
```bash
curl -s -X POST localhost:8800/v1/ask -H "Authorization: Bearer $API_TOKEN" -H "Content-Type: application/json" \
  -d '{"question": "Qual a tolerância de peso para a NF-e do exemplo?"}' | jq '{status, answer, citations: [.citations[] | {title, page}], cost}'
```
Expected: `status: "answered"`, ≥1 citation with document+page, and a real `cost.usd_estimate`. Ask something the corpus can't answer → `status: "not_found"`, no fabricated text.

## 5. See inside (2 min)
- Grafana → dashboard **RAG Overview**: latency, tokens, cost/query, eval trend
- Grafana → Explore → Tempo: pick your `X-Request-Id` → the full span waterfall (gate → retrieve → fuse → generate → validate)

## 6. Prove the guarantees (optional, 5 min)
```bash
# budget: set DAILY_BUDGET_USD=0 in .env, restart app → next /v1/ask returns 402 pre-call
# degraded mode: unset both API keys → /v1/ask answers via Ollama with status "degraded"
# evals: make eval   → writes evals/results/<ts>.md and fails on regression vs baseline
```

## Troubleshooting
| Symptom | Fix |
|---|---|
| `provider_unreachable` in /health | check API key; system still answers degraded if `LOCAL_LLM_ENABLED=true` |
| OCR slow on scanned PDFs | expected (CPU Tesseract); watch `ingest.*` spans in Tempo |
| HNSW build memory spike on bulk ingest | ingest in batches ≤ 200 docs (documented limit, spec edge case) |
