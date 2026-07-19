# Eval Results — v0.3.0 (live)

Run: 2026-07-19 · fixture `langchain_demo.pdf` · golden set v2 (**22 cases**: 16 in-scope + 6 out-of-scope).

| Field | Value |
| --- | --- |
| Mode | **live** (real embeddings + LLM) |
| Provider | OpenRouter |
| Model | `nvidia/nemotron-3-super-120b-a12b:free` |
| Embeddings | OpenAI `text-embedding-3-small` |
| Backend | in-memory hybrid + lexical rerank |
| Reproduce | `make eval-live` |

Baseline artifact: `packages/core/evals/results/baseline_core_live.json`

## Aggregate

| Metric | Value | Threshold |
| --- | --- | --- |
| pass_rate | **86.4%** (19/22) | ≥ 50% |
| answered_rate | 81.2% (13/16 in-scope) | ≥ 50% |
| refusal_rate | **100.0%** (6/6 out-of-scope) | ≥ 50% |
| keyword_hit_rate | 100% (when answered) | — |
| citation_hit_rate | 81.2% | — |
| avg_latency | 4.2s | < 10s target |
| total_cost | $0.00 (free OpenRouter model) | — |

Compare to v0.1.0 (8 cases, gpt-4o-mini): pass_rate **75.0%**, refusal **100%**.

## Per-case

| ID | Expected | Actual | Pass |
| --- | --- | --- | --- |
| lc-001 | answered | answered | ✓ |
| lc-002 | answered | not_found | ✗ |
| lc-003 | answered | answered | ✓ |
| lc-004 | answered | answered | ✓ |
| lc-005 | answered | answered | ✓ |
| lc-006 | answered | answered | ✓ |
| lc-007 | answered | answered | ✓ |
| lc-008 | answered | answered | ✓ |
| lc-009 | answered | not_found | ✗ |
| lc-010 | answered | answered | ✓ |
| lc-011 | answered | answered | ✓ |
| lc-012 | answered | answered | ✓ |
| lc-013 | answered | answered | ✓ |
| lc-014 | answered | not_found | ✗ |
| lc-015 | answered | answered | ✓ |
| lc-016 | answered | answered | ✓ |
| lc-oos-001…006 | not_found | not_found | ✓ (all 6) |

## Notes

- **In-scope misses (lc-002, lc-009, lc-014)**: model refused or failed citation verification — cite-or-refuse preferred over paraphrased fabrications.
- **Out-of-scope refusal is perfect**: grounding guard holds under a free production model.
- **Local smoke (same model)**: upload PDF → ask loader question → `answered` with verbatim citation; OOS capital question → `not_found`; `/v1/metrics` recorded 2 asks.
