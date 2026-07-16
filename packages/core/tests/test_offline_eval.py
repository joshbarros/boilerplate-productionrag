"""Offline eval runner — deterministic CI path."""

from __future__ import annotations

from pathlib import Path

import pytest

from ragcore.evals.runner import EvalRunner

_FIXTURES = Path(__file__).parent / "fixtures"
_GOLDEN = str(_FIXTURES / "golden_set.json")
_PDF = str(_FIXTURES / "langchain_demo.pdf")
_REG_GOLDEN = str(_FIXTURES / "golden_regulatory.json")
_CORPUS = _FIXTURES / "corpus"


@pytest.mark.asyncio
async def test_offline_core_eval_meets_floor() -> None:
    summary = await EvalRunner(
        golden_path=_GOLDEN,
        fixture_path=_PDF,
        mode="offline",
    ).run()
    assert summary.total_cases == 22
    assert summary.pass_rate >= 0.70, summary.pass_rate
    assert summary.refusal_rate >= 0.80, summary.refusal_rate


@pytest.mark.asyncio
async def test_offline_regulatory_eval_meets_floor() -> None:
    paths = sorted(str(p) for p in _CORPUS.glob("*.md"))
    assert len(paths) >= 6
    summary = await EvalRunner(
        golden_path=_REG_GOLDEN,
        fixture_paths=paths,
        mode="offline",
    ).run()
    assert summary.total_cases == 50
    fails = [r.case_id for r in summary.results if not r.passed]
    assert summary.pass_rate >= 0.70, f"pass_rate={summary.pass_rate}; fails={fails}"
    assert summary.refusal_rate >= 0.80
