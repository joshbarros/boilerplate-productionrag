"""Shared service layer — the ONLY thing api/ and mcp_server/ call (D13, VII).

This module defines the use-case signatures. Implementation is filled in
Phase 3 (US1 MVP) and beyond. Both FastAPI and FastMCP import from here,
so guarantees (citations, budgets, security) cannot drift.
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


class RagService:
    """Use-case layer — called by both HTTP API and MCP server."""

    async def ask(
        self,
        question: str,
        top_k: int = 8,
        config_override: dict[str, Any] | None = None,
    ) -> AnswerResult:
        """Answer a question with grounded citations or refuse."""
        raise NotImplementedError("Implemented in Phase 3 (US1 MVP)")

    async def search(
        self,
        query: str,
        top_k: int = 8,
        mode: str = "hybrid",
    ) -> list[SearchResult]:
        """Return raw ranked chunks — retrieval-only surface."""
        raise NotImplementedError("Implemented in Phase 3 (US1 MVP)")

    async def ingest_batch(self, file_paths: list[str]) -> list[DocumentStatusResult]:
        """Ingest a batch of PDFs, reporting per-document status."""
        raise NotImplementedError("Implemented in Phase 5 (US2)")

    async def document_status(self, document_id: uuid.UUID) -> DocumentStatusResult:
        """Return ingestion status for a single document."""
        raise NotImplementedError("Implemented in Phase 5 (US2)")

    async def budget_status(self) -> BudgetStatusResult:
        """Return current budget ledger snapshot."""
        raise NotImplementedError("Implemented in Phase 6 (US4)")


# Singleton — both api/ and mcp_server/ import this
service = RagService()
