"""EvalRunner — loads a golden set, ingests fixtures, runs all cases.

Modes:
  * live     — real embedder + LLM (EVAL_TEST / OpenRouter)
  * offline  — HashEmbedder + deterministic cite-or-refuse (CI gate)

Usage::

    import asyncio
    from ragcore.evals.runner import EvalRunner

    summary = asyncio.run(
        EvalRunner(
            golden_path="tests/fixtures/golden_set.json",
            fixture_path="tests/fixtures/langchain_demo.pdf",
            mode="offline",
        ).run()
    )
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Literal

from ragcore.evals.scorer import score_case
from ragcore.evals.types import EvalCase, EvalResult, EvalSummary
from ragcore.service import RagService

EvalMode = Literal["live", "offline"]


def _load_golden(path: str) -> tuple[str, str, list[EvalCase]]:
    """Parse golden_set.json → (fixture_name, version, cases)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
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
    return data["fixture"], str(data["version"]), cases


class EvalRunner:
    """Orchestrates the golden-set eval against one or more fixtures."""

    def __init__(
        self,
        golden_path: str,
        fixture_path: str | None = None,
        *,
        fixture_paths: list[str] | None = None,
        mode: EvalMode = "live",
        service: RagService | None = None,
    ) -> None:
        self._golden_path = golden_path
        paths: list[str] = []
        if fixture_paths:
            paths.extend(fixture_paths)
        if fixture_path:
            paths.append(fixture_path)
        if not paths:
            raise ValueError("fixture_path or fixture_paths required")
        self._fixture_paths = paths
        self._mode = mode
        self._service = service

    async def run(self) -> EvalSummary:
        fixture_name, version, cases = _load_golden(self._golden_path)

        svc = self._service or RagService()
        restore = None
        if self._mode == "offline":
            restore = self._wire_offline(svc)

        try:
            for path in self._fixture_paths:
                p = Path(path)
                if p.suffix.lower() == ".pdf":
                    svc.ingest(str(p))
                else:
                    text = p.read_text(encoding="utf-8", errors="replace")
                    svc.ingest_text(text, filename=p.name, title=p.stem)

            results: list[EvalResult] = []
            for case in cases:
                t0 = time.monotonic()
                answer_result = await svc.ask(
                    case.question,
                    top_k=12,
                    config_override={"skip_cache": True},
                )
                latency_ms = int((time.monotonic() - t0) * 1000)
                results.append(score_case(case, answer_result, latency_ms))

            return _summarise(fixture_name, version, results)
        finally:
            if restore is not None:
                restore()

    @staticmethod
    def _wire_offline(svc: RagService):
        import ragcore.service as service_module
        from ragcore.evals.offline import HashEmbedder, offline_generate_answer

        emb = HashEmbedder()
        svc._embedder = emb  # type: ignore[assignment]
        svc._get_embedder = lambda: emb  # type: ignore[method-assign]
        original = service_module.generate_answer
        service_module.generate_answer = offline_generate_answer  # type: ignore[assignment]

        # Offline gate: lexical rerank only (no model download)
        settings = __import__(
            "ragcore.config", fromlist=["get_settings"]
        ).get_settings()
        prev_ce = settings.rerank_cross_encoder
        prev_re = settings.rerank_enabled
        settings.rerank_cross_encoder = False
        # Keep rerank stage on for hybrid quality, but lexical only
        settings.rerank_enabled = True

        def _restore() -> None:
            service_module.generate_answer = original
            settings.rerank_cross_encoder = prev_ce
            settings.rerank_enabled = prev_re

        return _restore


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

    answered_results = [r for r in in_scope if r.actual_status == "answered"]
    kw_hit = sum(1 for r in answered_results if r.keyword_hit)

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


def render_markdown_table(summary: EvalSummary) -> str:
    """Human-readable markdown report."""
    lines = [
        f"# Eval — {summary.fixture} (v{summary.golden_version})",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| total_cases | {summary.total_cases} |",
        f"| pass_rate | **{summary.pass_rate:.1%}** |",
        f"| answered_rate | {summary.answered_rate:.1%} |",
        f"| refusal_rate | {summary.refusal_rate:.1%} |",
        f"| keyword_hit_rate | {summary.keyword_hit_rate:.1%} |",
        f"| citation_hit_rate | {summary.citation_hit_rate:.1%} |",
        f"| avg_latency_ms | {summary.avg_latency_ms:.0f} |",
        f"| total_cost_usd | ${summary.total_cost_usd:.6f} |",
        "",
        "| Case | Expected | Actual | Pass |",
        "| --- | --- | --- | --- |",
    ]
    for r in summary.results:
        flag = "✓" if r.passed else "✗"
        lines.append(
            f"| {r.case_id} | {r.expected_status} | {r.actual_status} | {flag} |"
        )
    return "\n".join(lines) + "\n"
