"""FastAPI app — HTTP API surface (contracts §HTTP).

All routes call ragcore.service — never pipeline modules directly (D13, VII).
Auth: Bearer token (single shared key v1).
"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from ragcore.config import get_settings
from ragcore.service import service

app = FastAPI(
    title="Production RAG",
    description="Self-hosted, citation-grounded document QA",
    version="0.1.0",
)


# ─── Auth ───

def _check_auth(authorization: str | None) -> None:
    """Bearer token auth (single shared key, v1)."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    settings = get_settings()
    if token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid token")


# ─── Request/Response models ───


class AskRequest(BaseModel):
    question: str
    top_k: int | None = None
    config_override: dict | None = None


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    mode: str = "hybrid"


class IngestRequest(BaseModel):
    file_path: str


# ─── Routes ───


@app.get("/v1/health")
async def health():
    """Liveness/readiness check."""
    settings = get_settings()
    return {
        "status": "ok",
        "provider": settings.default_provider.value,
        "model": settings.openrouter_default_model,
        "documents_indexed": len(service._documents),
    }


@app.post("/v1/ask")
async def ask(
    req: AskRequest,
    authorization: str | None = Header(None),
):
    """Answer a question with grounded citations (FR-001/002/003)."""
    _check_auth(authorization)
    result = await service.ask(req.question, req.top_k, req.config_override)
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


@app.post("/v1/search")
async def search(
    req: SearchRequest,
    authorization: str | None = Header(None),
):
    """Raw ranked chunks — retrieval-only surface."""
    _check_auth(authorization)
    results = await service.search(req.query, req.top_k, req.mode)
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


@app.post("/v1/documents")
async def ingest(
    req: IngestRequest,
    authorization: str | None = Header(None),
):
    """Ingest a PDF file (MVP: single file path, not multipart)."""
    _check_auth(authorization)
    result = service.ingest(req.file_path)
    return result
