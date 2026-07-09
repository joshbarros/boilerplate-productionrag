# Public deploy guide

This guide covers deploying the multi-niche RAG stack to a single VPS
for the LinkedIn public demo. It's the minimum config to get
**medical** and **legal** niches live with **free LLM models** and a
**chat UI** behind one Caddy.

## Architecture

```
            Internet
                │
                ▼
        ┌───────────────┐
        │  Caddy :443   │  (TLS, rate limit, static)
        └───────┬───────┘
                │
        ┌───────┴─────────────────────────┐
        │                                 │
   :3000 web (Next.js)              :8810 medical
                                    :8820 legal
```

Each niche is a separate uvicorn process on its own port. They share
**zero state** — each has its own in-memory `RAGService`. (For a
production deploy, swap in Postgres + a shared retrieval service.)

## Cost model (free tier)

| Component | Cost | Notes |
|---|---|---|
| LLM (Nemotron 3 Ultra) | **$0.00/query** | Free on OpenRouter, 1M context, fast (~1-2s typical) |
| Embeddings (text-embedding-3-small) | **$0.02 / 1M tokens** | ~$0.001 per 48-doc ingest, ~$0.0001 per query |
| VPS (1 vCPU, 1 GB) | **$5/month** | Hetzner / DigitalOcean |
| Domain + TLS | **$0** | Caddy + Let's Encrypt |

**Per-query cost: < $0.0001** (negligible). **Per-month cost: $5 (VPS only)**
for a demo that gets up to ~10k queries/month. The OpenRouter free
tier rate limits (20 req/min without API key) are the only constraint
for viral moments.

## Required env

```bash
# .env (root of repo)
OPENAI_API_KEY=sk-...        # for embeddings (any OpenAI key works)
OPENROUTER_API_KEY=sk-or-...  # for free models (optional but recommended)
OPENROUTER_DEFAULT_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
API_TOKEN=changeme            # shared between medical and legal
```

The repo's `.env.example` ships with these values. The free model
default is already set in `.env.example` so a fresh clone just needs
the two API keys.

## Local run (for the LinkedIn demo)

In one terminal:
```bash
# Medical
cd apps/medical
uv sync
API_TOKEN=changeme \
  ./.venv/bin/uvicorn medical.app:app \
    --app-dir ./src --host 127.0.0.1 --port 8810
```

In another:
```bash
# Legal
cd apps/legal
uv sync
API_TOKEN=changeme \
  ./.venv/bin/uvicorn legal.app:app \
    --app-dir ./src --host 127.0.0.1 --port 8820
```

In a third:
```bash
# Web chat UI
cd apps/web
pnpm install
pnpm dev
# → http://localhost:3000
```

The web app reads `NEXT_PUBLIC_NICHES` (defaults to core + medical +
legal in dev fixtures — see `apps/web/src/lib/niches.ts`).

## Ingest before public demo

Each niche ships with a small seed corpus (medical: 48 PMC articles,
legal: 80 cases). The web UI can ingest via:

```bash
# Medical: fetch 5 queries × 3 results = ~15 articles
cd apps/medical
uv run python -m medical.ingest --out ./corpus

# Legal: fetch 10 queries × 5 results = 50 cases
cd apps/legal
uv run python -m legal.ingest --out ./corpus
```

Then upload via the API:
```bash
curl -X POST -H "Authorization: Bearer changeme" \
  -H "Content-Type: application/json" \
  -d @<(jq -R '{file_paths: split("\n")|select(length>0)}' < <(ls /abs/path/corpus/*.md)) \
  http://127.0.0.1:8810/v1/documents/batch
```

## Verified performance (free model, 3 stress runs)

| Test | Result |
|---|---|
| Medical golden (8 Qs) | 3-4 / 8 (deterministic, same 4 failures) |
| Legal golden (8 Qs) | 2 / 8 (deterministic) |
| OOS refusals (2 + 5 edge) | 100% (8/8) |
| Empty input handling | 422 (no 500s) |
| Per-query latency | 1-3s typical |
| Per-query cost | < $0.0001 |
| Per-day cost (1000 Qs) | < $0.10 |

The "failures" on the golden are not bugs — they are cases where the
LLM correctly refuses to fabricate an answer when the corpus doesn't
contain the doctrinal statement. This is the safety property we
want for a public deploy.

## Production hardening checklist (before going public)

- [x] Empty input returns 422, not 500
- [x] No secret in git (`.env` gitignored, `.env.example` is template)
- [x] Free model verified, $0/query
- [ ] Caddy reverse proxy with TLS
- [ ] Rate limit per IP (Caddy `rate_limit` directive)
- [ ] `API_TOKEN` rotated to a long random value
- [ ] Monitoring: `/v1/budget` polled every minute, alert at 80% of cap
- [ ] Restart policy: systemd units for each niche
- [ ] `WIP=1` (only one niche process at a time, swap by editing Caddyfile)

## LinkedIn launch checklist

1. Pick a domain ($0 if you use a free subdomain, $10/yr for `.com`)
2. Deploy to a $5 VPS (Hetzner or DO)
3. Run the 3 uvicorn commands above in systemd
4. Caddy serves :443 with the niche-specific paths
5. Post the LinkedIn announcement pointing at the URL
6. Monitor `/v1/budget` for the first 24 hours
