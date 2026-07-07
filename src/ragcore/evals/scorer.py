"""Scoring functions for eval cases.

Each function is a pure predicate — no I/O, easy to unit-test.
"""

from __future__ import annotations

from ragcore.evals.types import EvalCase, EvalResult
from ragcore.types import AnswerResult


def score_case(case: EvalCase, result: AnswerResult, latency_ms: int) -> EvalResult:
    """Derive an EvalResult from a raw AnswerResult."""
    answer_text = result.answer or ""
    citation_pages = [c.page for c in result.citations]
    cost_usd = result.cost.usd_estimate if result.cost else 0.0

    status_match = result.status == case.expected_status

    # keyword_hit: at least one hint appears in the answer (case-insensitive).
    # Only meaningful for in-scope (expected answered) cases.
    keyword_hit: bool
    if case.expected_status == "answered" and case.keyword_hints:
        lower = answer_text.lower()
        keyword_hit = any(kw.lower() in lower for kw in case.keyword_hints)
    else:
        keyword_hit = True  # vacuously true when no hints or out-of-scope

    # citation_hit: at least one returned citation page is in expected_pages.
    citation_hit: bool
    if case.expected_pages:
        citation_hit = bool(set(citation_pages) & set(case.expected_pages))
    else:
        citation_hit = True  # vacuously true when no expectation set

    passed = status_match and keyword_hit and citation_hit

    return EvalResult(
        case_id=case.id,
        question=case.question,
        expected_status=case.expected_status,
        actual_status=result.status,
        answer=result.answer,
        citation_pages=citation_pages,
        latency_ms=latency_ms,
        cost_usd=cost_usd,
        status_match=status_match,
        keyword_hit=keyword_hit,
        citation_hit=citation_hit,
        passed=passed,
    )
