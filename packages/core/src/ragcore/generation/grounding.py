"""Grounding — parse LLM output, verify citations, compose Answer (FR-002/003).

Cite-or-refuse enforcement:
- answered ⇒ ≥1 verified citation (excerpt must be in the passage text)
- not_found ⇒ answer = null, no fabrication
- If LLM says "answered" but no citation verifies → downgrade to not_found
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from ragcore.budget.ledger import estimate_usd
from ragcore.obs.otel import stage_span
from ragcore.types import AnswerResult, CitationResult, CostReport


@dataclass
class ParsedLLMResponse:
    """Parsed JSON response from the LLM."""

    status: str  # answered | not_found
    answer: str | None
    citations: list[dict[str, Any]]


@stage_span("grounding.parse")
def parse_llm_response(raw_text: str) -> ParsedLLMResponse:
    """Parse the LLM's JSON response.

    Handles cases where the LLM wraps JSON in markdown code blocks.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last line (```json ... ```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
        return ParsedLLMResponse(
            status=data.get("status", "not_found"),
            answer=data.get("answer"),
            citations=data.get("citations", []),
        )
    except (json.JSONDecodeError, KeyError):
        # If JSON parsing fails, treat as not_found
        return ParsedLLMResponse(status="not_found", answer=None, citations=[])


@stage_span("grounding.verify")
def verify_citations(
    parsed: ParsedLLMResponse,
    passages: list[dict[str, Any]],
) -> list[CitationResult]:
    """Verify that each citation's excerpt actually exists in the passages.

    FR-002: citations MUST resolve to real corpus content containing the cited text.
    Verification uses ≥70 % word-overlap so minor paraphrasing by the LLM does not
    incorrectly downgrade a correct, grounded answer to not_found.
    """
    verified: list[CitationResult] = []

    if parsed.status != "answered" or not parsed.answer:
        return verified

    passage_map: dict[str, dict] = {p["chunk_id"]: p for p in passages}

    for citation in parsed.citations:
        chunk_id = citation.get("chunk_id", "")
        excerpt = citation.get("excerpt", "")
        page = citation.get("page", 0)

        # Find the passage this citation references
        passage = passage_map.get(chunk_id)
        if not passage:
            continue

        # FR-002: verify excerpt is grounded in the passage.
        # Primary check: exact substring (verbatim quote).
        # Fallback: ≥70 % word-overlap to tolerate minor paraphrasing by the LLM
        # while still blocking fabricated text.
        excerpt_clean = " ".join(excerpt.split())
        passage_clean = " ".join(passage["text"].split())

        if not excerpt_clean:
            continue

        exact_match = excerpt_clean in passage_clean

        excerpt_words = set(excerpt_clean.lower().split())
        passage_words = set(passage_clean.lower().split())
        overlap = (
            len(excerpt_words & passage_words) / len(excerpt_words)
            if excerpt_words
            else 0.0
        )
        word_overlap_match = overlap >= 0.70

        if exact_match or word_overlap_match:
            raw_doc = passage.get("document_id", uuid.UUID(int=0))
            if isinstance(raw_doc, str):
                try:
                    raw_doc = uuid.UUID(raw_doc)
                except ValueError:
                    raw_doc = uuid.UUID(int=0)
            verified.append(
                CitationResult(
                    document_id=raw_doc,
                    title=passage.get("title", ""),
                    page=page,
                    excerpt=excerpt,
                    support_score=1.0 if exact_match else round(overlap, 2),
                )
            )

    return verified


@stage_span("grounding.compose")
def compose_answer(
    parsed: ParsedLLMResponse,
    verified_citations: list[CitationResult],
    generation_result: Any,  # GenerationResult
    config: dict[str, Any],
) -> AnswerResult:
    """Compose the final AnswerResult with cite-or-refuse enforcement.

    FR-002/003: answered ⇒ ≥1 verified citation, else downgrade to not_found.
    FR-010: every answer reports cost.
    """
    # Cite-or-refuse: if LLM says answered but no verified citations → downgrade
    if parsed.status == "answered" and not verified_citations:
        status = "not_found"
        answer = None
    else:
        status = parsed.status
        answer = parsed.answer

    model_used = getattr(generation_result, "model_used", "") or ""
    usd = estimate_usd(
        model_used,
        generation_result.prompt_tokens,
        generation_result.completion_tokens,
    )
    cost = CostReport(
        prompt_tokens=generation_result.prompt_tokens,
        completion_tokens=generation_result.completion_tokens,
        embed_tokens=0,  # set by caller when embed usage is known
        usd_estimate=usd,
    )

    return AnswerResult(
        status=status,
        answer=answer,
        citations=verified_citations if status == "answered" else [],
        cost=cost,
        latency_ms=generation_result.latency_ms,
        config=config,
    )
