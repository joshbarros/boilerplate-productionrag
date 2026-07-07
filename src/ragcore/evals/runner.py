"""EvalRunner — loads a golden set, ingests a fixture PDF, runs all cases,
and returns an EvalSummary.

Usage (standalone)::

    import asyncio, json
    from ragcore.evals.runner import EvalRunner

    runner = EvalRunner(
        golden_path="tests/fixtures/golden_set.json",
        fixture_path="tests/fixtures/langchain_demo.pdf",
    )
    summary = asyncio.run(runner.run())
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ragcore.evals.scorer import score_case
from ragcore.evals.types import EvalCase, EvalResult, EvalSummary
from ragcore.service import RagService


def _load_golden(path: str) -> tuple[str, str, list[EvalCase]]:
    """Parse golden_set.json → (fixture_name, version, cases)."""
    data = json.loads(Path(path).read_text())
    cases = [
        EvalCase(
            id=c["id"],
            question=c["question"],
            expected_status=c["expected_status"],
            keyword_hints=c.get("keyword_hints", []),
            expected_pages=c.get("expected_pages", []),
        )
        for c in data["cases"]
    ]
    return data["fixture"], data["version"], cases


class EvalRunner:
    """Orchestrates the golden-set eval against a fixture PDF."""

    def __init__(self, golden_path: str, fixture_path: str) -> None:
        self._golden_path = golden_path
        self._fixture_path = fixture_path

    async def run(self) -> EvalSummary:
        fixture_name, version, cases = _load_golden(self._golden_path)

        # Fresh isolated service instance — no shared state with the singleton
        svc = RagService()
        svc.ingest(self._fixture_path)

        results: list[EvalResult] = []
        for case in cases:
            t0 = time.monotonic()
            answer_result = await svc.ask(case.question)
            latency_ms = int((time.monotonic() - t0) * 1000)
            results.append(score_case(case, answer_result, latency_ms))

        return _summarise(fixture_name, version, results)


# ─── Summary aggregation ──────────────────────────────────────────────────────


def _safe_rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _summarise(fixture: str, version: str, results: list[EvalResult]) -> EvalSummary:
    n = len(results)
    passed = sum(1 for r in results if r.passed)

    in_scope = [r for r in results if r.expected_status == "answered"]
    out_scope = [r for r in results if r.expected_status == "not_found"]

    answered = sum(1 for r in in_scope if r.actual_status == "answered")
    refused = sum(1 for r in out_scope if r.actual_status == "not_found")

    # keyword hit rate only over in-scope cases that were actually answered
    answered_results = [r for r in in_scope if r.actual_status == "answered"]
    kw_hit = sum(1 for r in answered_results if r.keyword_hit)

    # citation hit rate over all cases that had expected_pages
    citation_cases = [r for r in results if r.expected_status == "answered"]
    cit_hit = sum(1 for r in citation_cases if r.citation_hit)

    avg_lat = round(sum(r.latency_ms for r in results) / n, 1) if n else 0.0
    total_cost = round(sum(r.cost_usd for r in results), 6)

    return EvalSummary(
        fixture=fixture,
        golden_version=version,
        total_cases=n,
        pass_rate=_safe_rate(passed, n),
        answered_rate=_safe_rate(answered, len(in_scope)),
        refusal_rate=_safe_rate(refused, len(out_scope)),
        keyword_hit_rate=_safe_rate(kw_hit, len(answered_results)),
        citation_hit_rate=_safe_rate(cit_hit, len(citation_cases)),
        avg_latency_ms=avg_lat,
        total_cost_usd=total_cost,
        results=results,
    )
