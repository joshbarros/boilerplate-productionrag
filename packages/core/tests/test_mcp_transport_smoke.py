"""MCP transport smoke tests — exercises the full FastMCP tool dispatch loop.

Uses Client(mcp_instance) for in-process transport (zero network I/O),
so every test covers serialisation, argument coercion, and ToolError
propagation through the real FastMCP middleware stack.
"""

from __future__ import annotations

import json

import pytest
from fastmcp import Client

import ragcore.mcp_server.app as mcp_app
from ragcore.generation.router import GenerationResult
from ragcore.service import RagService

# ─── Fixtures ─────────────────────────────────────────────────────────────────


class FakeEmbedder:
    model_id = "fake-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [
            [float(len(t)), float(sum(c.isalpha() for c in t))]
            for t in texts
        ]


def _build_isolated_mcp(monkeypatch, fixture_path: str | None = None):
    """Return a fresh RagService + patched mcp for in-process smoke tests."""
    import ragcore.service as service_module

    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]

    def fake_generate(question, passages, model_override=None):
        excerpt = (passages[0]["text"][:60].strip()) if passages else ""
        payload = {
            "status": "answered" if passages else "not_found",
            "answer": "Smoke answer." if passages else None,
            "citations": (
                [{"chunk_id": passages[0]["chunk_id"], "page": 0, "excerpt": excerpt}]
                if passages
                else []
            ),
        }
        return GenerationResult(
            text=json.dumps(payload),
            model_used="mock/model",
            prompt_tokens=5,
            completion_tokens=10,
            latency_ms=1,
        )

    # Patch generation at the service module level (where service.ask imports it)
    monkeypatch.setattr(service_module, "generate_answer", fake_generate)
    # Point the MCP adapter to our isolated service instance
    monkeypatch.setattr(mcp_app, "service", svc)

    if fixture_path:
        svc.ingest(fixture_path)

    return svc


# ─── Tool discovery ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tools_returns_all_four(monkeypatch) -> None:
    _build_isolated_mcp(monkeypatch)

    async with Client(mcp_app.mcp) as client:
        tools = await client.list_tools()

    names = {t.name for t in tools}
    assert names == {
        "ask_documents",
        "search_documents",
        "ingest_document",
        "health",
        "budget",
    }


# ─── health ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health_tool_via_transport(monkeypatch) -> None:
    _build_isolated_mcp(monkeypatch)
    token = mcp_app.get_settings().api_token

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool("health", {"api_token": token})

    data = result.data
    assert data["status"] == "ok"
    assert "provider" in data
    assert data["documents_indexed"] == 0


@pytest.mark.asyncio
async def test_health_tool_rejects_bad_token(monkeypatch) -> None:
    _build_isolated_mcp(monkeypatch)

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool(
            "health",
            {"api_token": "wrong"},
            raise_on_error=False,
        )

    assert result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["error"]["status_code"] == 401


# ─── ingest_document ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_document_tool_via_transport(monkeypatch, tmp_path) -> None:
    import fitz  # PyMuPDF

    pdf_path = tmp_path / "smoke.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Transport smoke test content. LangChain loaders demo.")
    doc.save(str(pdf_path))
    doc.close()

    _build_isolated_mcp(monkeypatch)
    token = mcp_app.get_settings().api_token

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool(
            "ingest_document",
            {"file_path": str(pdf_path), "api_token": token},
        )

    data = result.data
    assert data["status"] == "succeeded"
    assert data["chunks"] >= 1


# ─── search_documents ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_documents_tool_via_transport(monkeypatch, tmp_path) -> None:
    import fitz

    pdf_path = tmp_path / "search_smoke.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Retrieval augmented generation uses embeddings.")
    doc.save(str(pdf_path))
    doc.close()

    _build_isolated_mcp(monkeypatch, str(pdf_path))
    token = mcp_app.get_settings().api_token

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool(
            "search_documents",
            {"query": "embeddings", "top_k": 3, "mode": "hybrid", "api_token": token},
        )

    data = result.data
    assert "results" in data
    assert len(data["results"]) >= 1
    assert all("chunk_id" in r for r in data["results"])


@pytest.mark.asyncio
async def test_search_documents_invalid_mode_via_transport(monkeypatch) -> None:
    _build_isolated_mcp(monkeypatch)
    token = mcp_app.get_settings().api_token

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool(
            "search_documents",
            {"query": "test", "mode": "oops", "api_token": token},
            raise_on_error=False,
        )

    assert result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["error"]["status_code"] == 400
    assert payload["error"]["reason"] == "validation"


# ─── ask_documents ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ask_documents_tool_via_transport(monkeypatch, tmp_path) -> None:
    import fitz

    pdf_path = tmp_path / "ask_smoke.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Transport smoke test document. LangChain can load PDF files with PyPDFLoader.",
    )
    doc.save(str(pdf_path))
    doc.close()

    _build_isolated_mcp(monkeypatch, str(pdf_path))
    token = mcp_app.get_settings().api_token

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool(
            "ask_documents",
            {"question": "What is this about?", "top_k": 3, "api_token": token},
        )

    data = result.data
    assert data["status"] == "answered"
    assert data["answer"] == "Smoke answer."
    assert len(data["citations"]) >= 1


@pytest.mark.asyncio
async def test_ask_documents_empty_question_via_transport(monkeypatch) -> None:
    _build_isolated_mcp(monkeypatch)
    token = mcp_app.get_settings().api_token

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool(
            "ask_documents",
            {"question": "   ", "api_token": token},
            raise_on_error=False,
        )

    assert result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["error"]["status_code"] == 400


@pytest.mark.asyncio
async def test_ask_documents_missing_token_via_transport(monkeypatch) -> None:
    _build_isolated_mcp(monkeypatch)

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool(
            "ask_documents",
            {"question": "test"},
            raise_on_error=False,
        )

    assert result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["error"]["status_code"] == 401
    assert payload["error"]["reason"] == "missing_auth"


# ─── budget ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_budget_tool_via_transport(monkeypatch) -> None:
    _build_isolated_mcp(monkeypatch)
    token = mcp_app.get_settings().api_token

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool("budget", {"api_token": token})

    data = result.data
    assert data["scope"] == "daily"
    assert "cap_usd" in data
    assert "consumed_usd" in data
    assert "rejected_count" in data
    assert "period" in data


@pytest.mark.asyncio
async def test_budget_tool_rejects_bad_token(monkeypatch) -> None:
    _build_isolated_mcp(monkeypatch)

    async with Client(mcp_app.mcp) as client:
        result = await client.call_tool(
            "budget", {"api_token": "bad"}, raise_on_error=False
        )

    assert result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["error"]["status_code"] == 401
