"""Regression gate unit tests."""

from __future__ import annotations

from ragcore.evals.regression import check_regression
from ragcore.evals.types import EvalResult, EvalSummary


def _summary(pass_rate: float, n: int = 10) -> EvalSummary:
    passed = int(round(pass_rate * n))
    results = [
        EvalResult(
            case_id=f"c{i}",
            question="q",
            expected_status="answered",
            actual_status="answered" if i < passed else "not_found",
            answer="a" if i < passed else None,
            citation_pages=[0] if i < passed else [],
            latency_ms=10,
            cost_usd=0.0,
            status_match=i < passed,
            keyword_hit=True,
            citation_hit=True,
            passed=i < passed,
        )
        for i in range(n)
    ]
    return EvalSummary(
        fixture="t",
        golden_version="1",
        total_cases=n,
        pass_rate=pass_rate,
        answered_rate=pass_rate,
        refusal_rate=1.0,
        keyword_hit_rate=1.0,
        citation_hit_rate=1.0,
        avg_latency_ms=10.0,
        total_cost_usd=0.0,
        results=results,
    )


def test_regression_when_drop_exceeds_threshold() -> None:
    current = _summary(0.80)
    baseline = {"pass_rate": 0.90}
    v = check_regression(current, baseline, max_drop_pts=2.0)
    assert v.verdict == "regression"
    assert v.drop_pts == 10.0
    assert not v.ok


def test_pass_when_within_drop() -> None:
    current = _summary(0.89)
    baseline = {"pass_rate": 0.90}
    v = check_regression(current, baseline, max_drop_pts=2.0)
    assert v.verdict == "pass"
    assert v.ok


def test_no_baseline() -> None:
    v = check_regression(_summary(0.95), None)
    assert v.verdict == "no_baseline"
    assert v.ok


def test_min_pass_rate_floor() -> None:
    v = check_regression(
        _summary(0.50),
        {"pass_rate": 0.50},
        max_drop_pts=5.0,
        min_pass_rate=0.70,
    )
    assert v.verdict == "regression"
    assert "min_pass_rate" in v.details["reason"]
