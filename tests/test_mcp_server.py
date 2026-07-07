from __future__ import annotations

import json
import uuid

import pytest
from fastmcp.exceptions import ToolError

import ragcore.mcp_server.app as mcp_app
from ragcore.types import AnswerResult, CitationResult, CostReport, SearchResult


@pytest.mark.asyncio
async def test_ask_documents_happy_path(monkeypatch) -> None:
    token = mcp_app.get_settings().api_token

    async def fake_ask(question: str, top_k: int | None, config_override=None):
        assert question == "What is this doc about?"
        assert top_k == 3
        return AnswerResult(
            status="answered",
            answer="Mock answer",
            citations=[
                CitationResult(
                    document_id=uuid.uuid4(),
                    title="Doc",
                    page=0,
                    excerpt="Mock excerpt",
                    support_score=1.0,
                )
            ],
            cost=CostReport(prompt_tokens=10, completion_tokens=20),
            latency_ms=12,
            config={"model": "mock"},
        )

    monkeypatch.setattr(mcp_app.service, "ask", fake_ask)

    result = await mcp_app._ask_documents_impl(
        question="What is this doc about?",
        top_k=3,
        api_token=token,
    )

    assert result["status"] == "answered"
    assert result["answer"] == "Mock answer"
    assert len(result["citations"]) == 1
    assert result["cost"]["prompt_tokens"] == 10


@pytest.mark.asyncio
async def test_ask_documents_requires_auth() -> None:
    with pytest.raises(ToolError) as exc:
        await mcp_app._ask_documents_impl("Question", api_token=None)

    payload = json.loads(str(exc.value))
    assert payload["error"]["status_code"] == 401
    assert payload["error"]["reason"] == "missing_auth"


@pytest.mark.asyncio
async def test_search_documents_invalid_mode() -> None:
    token = mcp_app.get_settings().api_token

    with pytest.raises(ToolError) as exc:
        await mcp_app._search_documents_impl(
            query="abc",
            mode="invalid",
            api_token=token,
        )

    payload = json.loads(str(exc.value))
    assert payload["error"]["status_code"] == 400
    assert payload["error"]["reason"] == "validation"


@pytest.mark.asyncio
async def test_search_documents_happy_path(monkeypatch) -> None:
    token = mcp_app.get_settings().api_token

    async def fake_search(query: str, top_k: int, mode: str):
        assert query == "LangChain"
        assert top_k == 2
        assert mode == "hybrid"
        return [
            SearchResult(
                chunk_id=uuid.uuid4(),
                document_id=uuid.uuid4(),
                page=0,
                text="Chunk text",
                scores={"vector": 0.8, "keyword": 0.4, "fused": 0.02},
            )
        ]

    monkeypatch.setattr(mcp_app.service, "search", fake_search)

    result = await mcp_app._search_documents_impl(
        query="LangChain",
        top_k=2,
        mode="hybrid",
        api_token=token,
    )
    assert len(result["results"]) == 1
    assert result["results"][0]["text"] == "Chunk text"


@pytest.mark.asyncio
async def test_ingest_document_duplicate_passthrough(monkeypatch) -> None:
    token = mcp_app.get_settings().api_token

    def fake_ingest(file_path: str):
        assert file_path.endswith("demo.pdf")
        return {"status": "duplicate", "fingerprint": "abc"}

    monkeypatch.setattr(mcp_app.service, "ingest", fake_ingest)

    result = await mcp_app._ingest_document_impl(
        file_path="/tmp/demo.pdf",
        api_token=token,
    )
    assert result["status"] == "duplicate"


@pytest.mark.asyncio
async def test_health_returns_provider_and_count() -> None:
    token = mcp_app.get_settings().api_token
    result = await mcp_app._health_impl(api_token=token)
    assert result["status"] == "ok"
    assert "provider" in result
    assert "documents_indexed" in result
