"""FastMCP server — MCP tool surface with parity to HTTP contracts.

All tools call ragcore.service only (shared guarantees with API).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ragcore.config import get_settings
from ragcore.service import service
from ragcore.types import AnswerResult

mcp = FastMCP(
    name="Production RAG MCP",
    instructions=(
        "Grounded document QA tools with citation-first behavior. "
        "Use ask/search/ingest/health/budget/document_status depending on task."
    ),
)


def _structured_error(status_code: int, reason: str, detail: str, **extra: Any) -> None:
    payload: dict[str, Any] = {
        "error": {
            "status_code": status_code,
            "reason": reason,
            "detail": detail,
        }
    }
    payload["error"].update(extra)
    raise ToolError(json.dumps(payload, ensure_ascii=True))


def _check_auth(api_token: str | None) -> None:
    if not api_token:
        _structured_error(401, "missing_auth", "Missing api_token")
    settings = get_settings()
    if api_token.strip() != settings.api_token:
        _structured_error(401, "invalid_auth", "Invalid api_token")


def _serialize_answer(result: AnswerResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "answer": result.answer,
        "citations": [
            {
                "document_id": str(c.document_id),
                "title": c.title,
                "page": c.page,
                "excerpt": c.excerpt,
                "support_score": c.support_score,
            }
            for c in result.citations
        ],
        "cost": {
            "prompt_tokens": result.cost.prompt_tokens,
            "completion_tokens": result.cost.completion_tokens,
            "embed_tokens": result.cost.embed_tokens,
            "usd_estimate": result.cost.usd_estimate,
        },
        "latency_ms": result.latency_ms,
        "config": result.config,
    }


async def _ask_documents_impl(
    question: str,
    top_k: int | None = None,
    api_token: str | None = None,
) -> dict[str, Any]:
    _check_auth(api_token)

    if not question or not question.strip():
        _structured_error(400, "validation", "question must be a non-empty string")

    result = await service.ask(question.strip(), top_k, None)
    return _serialize_answer(result)


async def _search_documents_impl(
    query: str,
    top_k: int = 8,
    mode: str = "hybrid",
    api_token: str | None = None,
) -> dict[str, Any]:
    _check_auth(api_token)

    if not query or not query.strip():
        _structured_error(400, "validation", "query must be a non-empty string")

    valid_modes = {"hybrid", "vector", "keyword"}
    if mode not in valid_modes:
        _structured_error(
            400,
            "validation",
            f"mode must be one of {sorted(valid_modes)}",
        )

    results = await service.search(query=query.strip(), top_k=top_k, mode=mode)
    return {
        "results": [
            {
                "chunk_id": str(r.chunk_id),
                "document_id": str(r.document_id),
                "page": r.page,
                "text": r.text,
                "scores": r.scores,
            }
            for r in results
        ]
    }


async def _ingest_document_impl(
    file_path: str,
    api_token: str | None = None,
) -> dict[str, Any]:
    _check_auth(api_token)

    if not file_path or not file_path.strip():
        _structured_error(400, "validation", "file_path must be a non-empty string")

    return service.ingest(file_path.strip())


async def _health_impl(api_token: str | None = None) -> dict[str, Any]:
    _check_auth(api_token)
    settings = get_settings()
    return {
        "status": "ok",
        "provider": settings.default_provider.value,
        "model": settings.openrouter_default_model,
        "documents_indexed": service.document_count(),
        "backend": settings.vector_backend.value,
    }


async def _budget_impl(api_token: str | None = None) -> dict[str, Any]:
    _check_auth(api_token)
    result = await service.budget_status()
    return {
        "period": result.period,
        "scope": result.scope,
        "cap_usd": result.cap_usd,
        "consumed_usd": result.consumed_usd,
        "rejected_count": result.rejected_count,
    }


async def _document_status_impl(
    document_id: str,
    api_token: str | None = None,
) -> dict[str, Any]:
    _check_auth(api_token)
    if not document_id or not document_id.strip():
        _structured_error(
            400, "validation", "document_id must be a non-empty UUID string"
        )
    try:
        doc_uuid = uuid.UUID(document_id.strip())
    except ValueError:
        _structured_error(400, "validation", "document_id must be a valid UUID")
    try:
        result = await service.document_status(doc_uuid)
    except KeyError:
        _structured_error(404, "not_found", f"Document {document_id} not found")
    return {
        "id": str(result.id),
        "filename": result.filename,
        "status": result.status,
        "page_count": result.page_count,
        "failure_reason": result.failure_reason,
    }


@mcp.tool(
    name="ask_documents",
    description=(
        "Ask a question over indexed documents and get a grounded answer. "
        "Answered responses include citations and cost metadata."
    ),
)
async def ask_documents(
    question: str,
    top_k: int | None = None,
    api_token: str | None = None,
) -> dict[str, Any]:
    return await _ask_documents_impl(
        question=question,
        top_k=top_k,
        api_token=api_token,
    )


@mcp.tool(
    name="search_documents",
    description=(
        "Run retrieval-only search over indexed chunks. "
        "Returns ranked chunks with vector/keyword/fused scores."
    ),
)
async def search_documents(
    query: str,
    top_k: int = 8,
    mode: str = "hybrid",
    api_token: str | None = None,
) -> dict[str, Any]:
    return await _search_documents_impl(
        query=query,
        top_k=top_k,
        mode=mode,
        api_token=api_token,
    )


@mcp.tool(
    name="ingest_document",
    description=(
        "Ingest a PDF from a local path. "
        "Returns succeeded, duplicate, or failure details."
    ),
)
async def ingest_document(
    file_path: str,
    api_token: str | None = None,
) -> dict[str, Any]:
    return await _ingest_document_impl(file_path=file_path, api_token=api_token)


@mcp.tool(
    name="health",
    description=(
        "Return MCP and retrieval health metadata. "
        "Includes provider, model, and indexed-doc count."
    ),
)
async def health(api_token: str | None = None) -> dict[str, Any]:
    return await _health_impl(api_token=api_token)


@mcp.tool(
    name="budget",
    description=(
        "Return current budget ledger snapshot. "
        "Includes daily cap, consumed USD, and rejection count."
    ),
)
async def budget(api_token: str | None = None) -> dict[str, Any]:
    return await _budget_impl(api_token=api_token)


@mcp.tool(
    name="get_document_status",
    description=(
        "Return ingestion status for a document UUID. "
        "Includes filename, status, page_count, and failure_reason."
    ),
)
async def get_document_status(
    document_id: str,
    api_token: str | None = None,
) -> dict[str, Any]:
    return await _document_status_impl(document_id=document_id, api_token=api_token)


def create_http_app(path: str = "/mcp"):
    """ASGI app for streamable-http transport."""
    return mcp.http_app(path=path, transport="streamable-http")


def run() -> None:
    """Run MCP server on configured host/port."""
    settings = get_settings()
    mcp.run(
        transport="streamable-http",
        host=settings.api_host,
        port=settings.mcp_port,
        path="/mcp",
    )


if __name__ == "__main__":
    run()
