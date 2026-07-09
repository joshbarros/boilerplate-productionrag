# Eval Results — v0.1.0

Run on: `langchain_demo.pdf` (2-page fixture), 8 golden cases (6 in-scope + 2 out-of-scope).
Model: `openai/gpt-4o-mini` via OpenRouter.
Reproduce: `EVAL_TEST=1 uv run pytest tests/test_phase7_evals.py::test_phase7_live_eval_suite -v -s`

## Aggregate

| Metric | Value | Threshold |
| --- | --- | --- |
| pass_rate | 75.0% (6/8) | ≥ 50% |
| answered_rate | 66.7% (4/6 in-scope) | ≥ 50% |
| refusal_rate | 100.0% (2/2 out-of-scope) | ≥ 50% |
| keyword_hit_rate | 100% (when answered) | — |
| citation_hit_rate | 66.7% (4/6 with page expectation) | — |
| avg_latency | 2.9s | < 10s p95 target |
| total_cost | $0.00 (free OpenRouter credits) | — |

## Per-case

| ID | Question | Status | Result |
| --- | --- | --- | --- |
| lc-001 | What does a Document Loader do? | answered | ✓ |
| lc-002 | What fields does a Document object contain? | answered | ✓ |
| lc-003 | What are Text Splitters used for? | not_found | ✗ |
| lc-004 | What does a vector store do with chunks? | not_found | ✗ |
| lc-005 | What was the demo document generated to demonstrate? | answered | ✓ |
| lc-006 | Which Python class is used to load PDFs? | answered | ✓ |
| lc-oos-001 | What is the capital of France? | not_found | ✓ (correct refusal) |
| lc-oos-002 | How do I configure a PostgreSQL connection pool? | not_found | ✓ (correct refusal) |

## Notes

- **In-scope failures (lc-003, lc-004)**: the source material is a bullet list, and the
  model paraphrases the bullets rather than quoting them verbatim. Our cite-or-refuse
  guard downgrades these to `not_found` because the excerpts don't verify at ≥70%
  word overlap with the passage text. This is *correct behavior* — we don't want to
  cite-ground fabricated paraphrases — but a richer fixture with prose-format
  answers would raise the in-scope rate.
- **Out-of-scope refusal is 100%**: the grounding guard reliably prevents
  hallucination on ungrounded questions.
- **Cost is zero**: we route through OpenRouter's free-credit tier for `gpt-4o-mini`.
  At scale, budget is enforced by `BudgetLedger` (Phase 6) with a default $5/day cap.
