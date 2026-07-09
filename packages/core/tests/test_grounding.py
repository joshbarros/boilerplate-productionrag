from __future__ import annotations

import uuid
from types import SimpleNamespace

from ragcore.generation.grounding import (
    ParsedLLMResponse,
    compose_answer,
    parse_llm_response,
    verify_citations,
)
from ragcore.types import CitationResult


def test_parse_llm_response_strips_markdown_fence() -> None:
    raw = (
        "```json\n"
        '{"status":"answered","answer":"A","citations":[]}'
        "\n```"
    )

    parsed = parse_llm_response(raw)

    assert parsed.status == "answered"
    assert parsed.answer == "A"
    assert parsed.citations == []


def test_parse_llm_response_malformed_json_falls_back_not_found() -> None:
    parsed = parse_llm_response('{"status":"answered"')
    assert parsed.status == "not_found"
    assert parsed.answer is None
    assert parsed.citations == []


def test_verify_citations_accepts_only_verbatim_excerpt() -> None:
    doc_id = uuid.uuid4()
    passages = [
        {
            "chunk_id": "c1",
            "page": 0,
            "text": "LangChain can load PDF files with PyPDFLoader.",
            "document_id": doc_id,
            "title": "Doc",
        }
    ]
    parsed = ParsedLLMResponse(
        status="answered",
        answer="It supports PyPDFLoader.",
        citations=[
            {"chunk_id": "c1", "page": 0, "excerpt": "load PDF files with PyPDFLoader"},
            {"chunk_id": "c1", "page": 0, "excerpt": "this excerpt does not exist"},
        ],
    )

    verified = verify_citations(parsed, passages)

    assert len(verified) == 1
    assert verified[0].excerpt == "load PDF files with PyPDFLoader"


def test_compose_answer_downgrades_answered_without_verified_citations() -> None:
    parsed = ParsedLLMResponse(status="answered", answer="A", citations=[])
    generation = SimpleNamespace(prompt_tokens=10, completion_tokens=20, latency_ms=3)

    result = compose_answer(parsed, [], generation, {"model": "mock"})

    assert result.status == "not_found"
    assert result.answer is None
    assert result.citations == []
    assert result.cost.prompt_tokens == 10
    assert result.cost.completion_tokens == 20


def test_compose_answer_keeps_answer_when_citations_verified() -> None:
    parsed = ParsedLLMResponse(status="answered", answer="A", citations=[])
    generation = SimpleNamespace(prompt_tokens=1, completion_tokens=2, latency_ms=1)
    verified = [
        CitationResult(
            document_id=uuid.uuid4(),
            title="Doc",
            page=0,
            excerpt="excerpt",
            support_score=1.0,
        )
    ]

    result = compose_answer(parsed, verified, generation, {"model": "mock"})

    assert result.status == "answered"
    assert result.answer == "A"
    assert len(result.citations) == 1
