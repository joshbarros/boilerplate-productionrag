# Data Model: Regulatory Document QA

**Date**: 2026-07-07 · Storage: PostgreSQL 17 (+pgvector). All tables carry `created_at`/`updated_at`. Alembic-managed.

## documents
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| fingerprint | text UNIQUE | sha256 of normalized bytes — dedup key (FR-006) |
| title, filename | text | |
| language | text | `pt` / `en` / `mixed` (detected) |
| page_count | int | |
| status | enum | `pending / processing / succeeded / failed` |
| failure_reason | text NULL | actionable message (US2-AS3) |
| extraction_summary | jsonb | per-page method: `digital` / `ocr` |

## chunks
| Column | Type | Notes |
|---|---|---|
| id | uuid PK | |
| document_id | FK → documents | cascade delete |
| strategy | enum | `fixed / recursive / semantic` — multiple strategies may coexist per document |
| page_start, page_end | int | citation anchor |
| text | text | |
| tsv | tsvector | GENERATED, language-config from document.language — FTS arm |
| embedding | vector(1536) | pgvector; HNSW index (m=16, ef_construction=64) |
| embedding_model | text | pinned model id — mixed-model search is refused (D6) |
| metadata | jsonb | section, detected identifiers/acronyms (feeds keyword boost) |

Indexes: HNSW on embedding (partial per embedding_model), GIN on tsv, GIN on metadata jsonb_path_ops. Qdrant mirror: collection `chunks_bench` with same payload — written only by the eval/benchmark pipeline, never by the serving path.

## queries
| id uuid PK · text text · masked_text text (what may leave the host) · client_id text · budget_snapshot jsonb · created_at |

## answers
| id uuid PK · query_id FK · status enum `answered / not_found / rejected_budget / rejected_security / degraded` · text text NULL · model_used text · config jsonb (chunking strategy, retrieval mode, reranker on/off, backend) · cost jsonb (prompt_tokens, completion_tokens, embed_tokens, usd_estimate) · latency_ms int |

## citations
| id uuid PK · answer_id FK · chunk_id FK · document_id FK · page int · excerpt text · support_score float |
Constraint: an `answered` answer MUST have ≥1 citation (enforced in output validator + DB CHECK via trigger).

## golden_cases  (also versioned as evals/golden/golden.yaml — DB is the run-time copy)
| id uuid PK · question text · expected_answer text · expected_document_fingerprint text · expected_pages int[] · language text · answerable bool · status enum `active / disputed / excluded` · audit_note text |

## eval_runs
| id uuid PK · started_at · git_sha text · config_matrix jsonb · scores jsonb (per config × metric: recall_at_k, faithfulness, relevance, citation_accuracy) · baseline_run_id FK NULL · verdict enum `pass / regression` · report_path text |

## budget_ledger
| id uuid PK · period date · scope enum `query / day` · cap_usd numeric · consumed_usd numeric · rejected_count int |
Invariant: `consumed_usd` only increases via recorded answer costs; rejection happens pre-call (FR-011).

## response_cache
| key text PK (sha256 of masked_text + config) · answer_id FK · hits int · ttl expires_at |

## Relationships
```
documents 1─* chunks
queries 1─1 answers 1─* citations *─1 chunks
golden_cases ─(consumed by)→ eval_runs
answers ─(append)→ budget_ledger, response_cache
```

## State machines
- **Document**: `pending → processing → succeeded | failed` (failed is terminal; re-upload with same fingerprint returns existing record)
- **Answer**: gate rejections (`rejected_*`) short-circuit before retrieval; `degraded` marks local-fallback generations (FR-013)
- **Golden case**: `active ↔ disputed → excluded` (never deleted — audit trail, spec edge case)
