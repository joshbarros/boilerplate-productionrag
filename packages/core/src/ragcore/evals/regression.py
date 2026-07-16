"""Eval regression gate — compare a run against a committed baseline (FR-009).

Rule (constitution / tasks T024): fail when pass_rate drops by more than
``max_drop_pts`` percentage points relative to the baseline (default 2.0).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ragcore.evals.types import EvalSummary


@dataclass
class RegressionVerdict:
    verdict: str  # pass | regression | no_baseline
    baseline_pass_rate: float | None
    current_pass_rate: float
    drop_pts: float | None
    max_drop_pts: float
    details: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.verdict in ("pass", "no_baseline")


def summary_to_dict(summary: EvalSummary) -> dict[str, Any]:
    """Serialize EvalSummary for baseline / result files."""
    return {
        "fixture": summary.fixture,
        "golden_version": summary.golden_version,
        "total_cases": summary.total_cases,
        "pass_rate": summary.pass_rate,
        "answered_rate": summary.answered_rate,
        "refusal_rate": summary.refusal_rate,
        "keyword_hit_rate": summary.keyword_hit_rate,
        "citation_hit_rate": summary.citation_hit_rate,
        "avg_latency_ms": summary.avg_latency_ms,
        "total_cost_usd": summary.total_cost_usd,
        "results": [
            {
                "case_id": r.case_id,
                "expected_status": r.expected_status,
                "actual_status": r.actual_status,
                "passed": r.passed,
                "keyword_hit": r.keyword_hit,
                "citation_hit": r.citation_hit,
                "latency_ms": r.latency_ms,
            }
            for r in summary.results
        ],
    }


def load_baseline(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_baseline(path: str | Path, summary: EvalSummary) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(summary_to_dict(summary), indent=2) + "\n",
        encoding="utf-8",
    )


def check_regression(
    current: EvalSummary,
    baseline: dict[str, Any] | None,
    *,
    max_drop_pts: float = 2.0,
    min_pass_rate: float | None = None,
) -> RegressionVerdict:
    """Compare current summary to baseline.

    Args:
        current: Fresh eval summary.
        baseline: Loaded baseline dict (or None if first run).
        max_drop_pts: Max allowed drop in pass_rate * 100 (percentage points).
        min_pass_rate: Absolute floor (0–1). If set, fail when below even if
            not a regression vs baseline.
    """
    details: dict[str, Any] = {
        "answered_rate": current.answered_rate,
        "refusal_rate": current.refusal_rate,
        "total_cases": current.total_cases,
    }

    if min_pass_rate is not None and current.pass_rate < min_pass_rate:
        return RegressionVerdict(
            verdict="regression",
            baseline_pass_rate=baseline.get("pass_rate") if baseline else None,
            current_pass_rate=current.pass_rate,
            drop_pts=None,
            max_drop_pts=max_drop_pts,
            details={
                **details,
                "reason": (
                    f"pass_rate {current.pass_rate:.1%} < "
                    f"min_pass_rate {min_pass_rate:.1%}"
                ),
            },
        )

    if baseline is None:
        return RegressionVerdict(
            verdict="no_baseline",
            baseline_pass_rate=None,
            current_pass_rate=current.pass_rate,
            drop_pts=None,
            max_drop_pts=max_drop_pts,
            details={**details, "reason": "no baseline file"},
        )

    base_rate = float(baseline.get("pass_rate", 0.0))
    # drop in percentage points (e.g. 0.90 → 0.87 = 3.0 pts)
    drop_pts = round((base_rate - current.pass_rate) * 100, 2)

    if drop_pts > max_drop_pts:
        return RegressionVerdict(
            verdict="regression",
            baseline_pass_rate=base_rate,
            current_pass_rate=current.pass_rate,
            drop_pts=drop_pts,
            max_drop_pts=max_drop_pts,
            details={
                **details,
                "reason": (
                    f"pass_rate dropped {drop_pts:.1f} pts "
                    f"(max allowed {max_drop_pts})"
                ),
                "baseline_fixture": baseline.get("fixture"),
            },
        )

    return RegressionVerdict(
        verdict="pass",
        baseline_pass_rate=base_rate,
        current_pass_rate=current.pass_rate,
        drop_pts=drop_pts,
        max_drop_pts=max_drop_pts,
        details=details,
    )


def verdict_to_dict(v: RegressionVerdict) -> dict[str, Any]:
    return asdict(v)
