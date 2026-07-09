"""Eval types — EvalCase, EvalResult, EvalSummary."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalCase:
    """A single golden question with expected outputs."""

    id: str
    question: str
    # "answered" for in-scope, "not_found" for out-of-scope questions
    expected_status: str
    # Keywords that must appear (case-insensitive) in the answer for a hit
    keyword_hints: list[str] = field(default_factory=list)
    # 0-based page numbers where a supporting citation is expected
    expected_pages: list[int] = field(default_factory=list)


@dataclass
class EvalResult:
    """Scored outcome for a single EvalCase."""

    case_id: str
    question: str
    expected_status: str
    actual_status: str
    answer: str | None
    citation_pages: list[int]
    latency_ms: int
    cost_usd: float
    # Derived scores
    status_match: bool = False
    keyword_hit: bool = False      # ≥1 keyword_hint found in answer (only for answered)
    citation_hit: bool = False     # ≥1 citation page in expected_pages (when non-empty)
    passed: bool = False           # overall pass for this case


@dataclass
class EvalSummary:
    """Aggregate scores across all cases in a run."""

    fixture: str
    golden_version: str
    total_cases: int
    pass_rate: float             # fraction of cases that passed
    answered_rate: float         # fraction of in-scope cases answered
    refusal_rate: float          # fraction of out-of-scope cases correctly refused
    keyword_hit_rate: float      # fraction of answered cases with keyword hit
    citation_hit_rate: float     # fraction of cases with expected_pages that had a hit
    avg_latency_ms: float
    total_cost_usd: float
    results: list[EvalResult] = field(default_factory=list)
