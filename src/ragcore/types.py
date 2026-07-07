"""Shared result types — used by service, grounding, and API.

Separated from service.py to avoid circular imports.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CitationResult:
    document_id: uuid.UUID
    title: str
    page: int
    excerpt: str
    support_score: float | None = None


@dataclass
class CostReport:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    embed_tokens: int = 0
    usd_estimate: float = 0.0


@dataclass
class AnswerResult:
    status: str  # answered | not_found | degraded | rejected_budget | rejected_security
    answer: str | None = None
    citations: list[CitationResult] = field(default_factory=list)
    cost: CostReport = field(default_factory=CostReport)
    latency_ms: int = 0
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    page: int
    text: str
    scores: dict[str, float] = field(default_factory=dict)


@dataclass
class DocumentStatusResult:
    id: uuid.UUID
    filename: str
    status: str
    page_count: int
    failure_reason: str | None = None


@dataclass
class BudgetStatusResult:
    period: str
    scope: str
    cap_usd: float
    consumed_usd: float
    rejected_count: int
