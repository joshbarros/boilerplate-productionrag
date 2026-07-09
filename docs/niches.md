# Niche architecture

## Decision: one repo, niches as apps/

Each niche is a self-contained FastAPI app that composes the shared
`packages/core` engine with domain-specific data, prompts, and evals.

```
production-rag/
├── packages/
│   └── core/          # ragcore — shared RAG engine (was apps/backend)
│       ├── src/ragcore/
│       │   ├── api/             # FastAPI app + routes
│       │   ├── mcp_server/      # FastMCP tool surface
│       │   ├── ingestion/       # PyMuPDF + Docling OCR
│       │   ├── chunking/         # recursive + fixed + semantic
│       │   ├── embedding/        # provider abstraction
│       │   ├── retrieval/       # vector + keyword + RRF
│       │   ├── generation/      # router + prompts + grounding
│       │   ├── budget/          # daily/query caps
│       │   └── evals/           # golden set + scorer + runner
│       ├── tests/               # 68 tests
│       ├── alembic/             # DB migrations
│       └── pyproject.toml       # name: production-rag-core
│
├── apps/
│   ├── web/                     # Next.js 15 chat UI (shared, niche switcher)
│   ├── medical/                 # niche 1: PubMed Central literature
│   │   ├── src/medical/
│   │   │   ├── pubmed.py        # E-utilities fetcher (free, no auth)
│   │   │   ├── golden.py        # 8-case medical eval set
│   │   │   ├── ingest.py        # CLI: query → PubMed → corpus/*.md
│   │   │   └── app.py           # FastAPI on :8810 with medical prompt
│   │   ├── corpus/              # 48 seed PMC articles (reproducible)
│   │   ├── pyproject.toml       # depends on production-rag-core
│   │   └── package.json
│   └── legal/                   # niche 2: US case law (CourtListener)
│       ├── src/legal/
│       │   ├── courtlistener.py # Search API fetcher (free, token optional)
│       │   ├── golden.py        # 8-case legal eval set
│       │   ├── ingest.py        # CLI: query → cases → corpus/*.md
│       │   └── app.py           # FastAPI on :8820 with legal prompt
│       ├── corpus/              # reproducible seed corpus
│       ├── pyproject.toml       # depends on production-rag-core
│       └── package.json
│
├── docs/                        # design_system, eval_results, limits
├── turbo.json                   # orchestrator
└── .github/workflows/ci.yml    # CI for all paths
```

## Why one repo

- One VPS, one CI, one set of CVE patches
- Each niche reuses the same retrieval/generation/grounding/budget code
- Adding a niche is a small, focused PR (one app dir, one golden set)
- Eval numbers are comparable across niches (same engine, same model)

## Why NOT separate repos

- Security/dependency updates would need to be replicated per repo
- Bug fixes in retrieval/grounding would land in N places
- Eval baseline drift would be hard to detect

## VPS deployment

Each niche runs its own FastAPI on a different port behind one Caddy:

```
:80  → Caddy → /
:8800 → core (generic, default landing)
:8810 → medical
:8820 → legal
:8830 → accounting (future)
```

The web app points at the chosen niche via `NEXT_PUBLIC_NICHES` env var:

```json
[
  {"key": "core",     "label": "Generic",  "backend": "http://localhost:8800", "enabled": true},
  {"key": "medical",  "label": "Medical",  "backend": "http://localhost:8810", "enabled": true},
  {"key": "legal",    "label": "Legal",    "backend": "http://localhost:8820", "enabled": true},
  {"key": "accounting","label":"Accounting","backend": "http://localhost:8830", "enabled": false}
]
```

`enabled: false` hides a niche from the switcher in the UI without
removing its backend. The frontend stores the active niche in
`localStorage` so the choice persists per-browser.

## Adding a new niche

1. `cp -r apps/legal apps/<newniche>` and edit the files
2. Write your niche's `golden.py` (8+ Q&A pairs)
3. Add your data fetcher in `courtlistener.py` → `<source>.py` (EDGAR, …)
4. Wire the URL into `NICHES` env var
5. Run `make eval` to verify the niche works end-to-end

No core changes needed. The engine is stable.

## Shipped niches (so far)

| Niche | Backend port | Data source | Auth | Status |
|---|---|---|---|---|
| core | :8800 | any user-uploaded docs | API_TOKEN | shipped (v0.1.0) |
| medical | :8810 | PubMed Central (E-utilities) | none | shipped |
| legal | :8820 | CourtListener (Free Law Project) | optional token | shipped |
| accounting | :8830 | SEC EDGAR | TBD | planned |
