# Eval results

Committed baselines power the **offline regression gate** (`make eval-gate` / CI).

| File | Suite | Mode |
| --- | --- | --- |
| `baseline_core_offline.json` | `tests/fixtures/golden_set.json` (22 cases) | HashEmbedder + deterministic cite-or-refuse |
| `baseline_regulatory_offline.json` | `tests/fixtures/golden_regulatory.json` (50 cases) | Same, multi-doc PT-BR/EN regulatory corpus |
| `baseline_core_live.json` | golden_set v2 (22 cases) | **Live** OpenRouter free model + OpenAI embeddings — **86.4%** (2026-07-19) |

## Rules

- Gate fails if `pass_rate` drops **> 2 percentage points** vs baseline, or falls below **70%** absolute.
- Re-generate baselines only intentionally after golden/corpus changes:

```bash
cd packages/core
uv run python -m ragcore.evals \
  --golden tests/fixtures/golden_set.json \
  --fixture tests/fixtures/langchain_demo.pdf \
  --mode offline \
  --write-baseline evals/results/baseline_core_offline.json
```

Live OpenRouter runs remain optional: `make eval` / `EVAL_TEST=1`.
