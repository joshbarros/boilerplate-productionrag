"""FastAPI app — HTTP API surface (contracts §HTTP).

All routes call a RagService instance — never pipeline modules directly (D13).
Use ``create_app(svc)`` for niche isolation (custom prompt builder / backend).
"""

from __future__ import annotations

import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from pydantic import BaseModel, field_validator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ragcore.config import get_settings
from ragcore.security.rate_limit import RateLimiter, RateLimitExceededError
from ragcore.service import RagService
from ragcore.service import service as default_service


def _init_telemetry() -> None:
    try:
        from ragcore.obs.otel import configure_telemetry

        configure_telemetry()
    except Exception:
        pass


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    _init_telemetry()
    yield


# Module-level default app (uvicorn: ragcore.api.app:app)
app = FastAPI(
    title="Production RAG",
    description="Self-hosted, citation-grounded document QA",
    version="0.3.0",
    lifespan=_lifespan,
)


def create_app(svc: RagService | None = None) -> FastAPI:
    """Build a FastAPI app bound to a specific RagService (niches use this)."""
    bound = svc or default_service
    application = FastAPI(
        title="Production RAG",
        description="Self-hosted, citation-grounded document QA",
        version="0.3.0",
        lifespan=_lifespan,
    )
    _register_middleware(application)
    _register_routes(application, bound)
    return application


def _register_middleware(application: FastAPI) -> None:
    limiter = RateLimiter(per_minute=get_settings().rate_limit_per_minute)

    class RateLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            settings = get_settings()
            if not settings.security_enabled:
                return await call_next(request)
            if request.url.path.endswith("/health"):
                return await call_next(request)
            client = request.client.host if request.client else "unknown"
            auth = request.headers.get("authorization", "")
            key = f"{client}:{auth[-8:] if auth else 'anon'}"
            try:
                limiter.check(key)
            except RateLimitExceededError as exc:
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": str(exc),
                        "status": "rejected_security",
                        "kind": "rate_limit",
                    },
                )
            return await call_next(request)

    application.add_middleware(RateLimitMiddleware)


def _check_auth(authorization: str | None) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    settings = get_settings()
    if token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid token")


class AskRequest(BaseModel):
    question: str
    top_k: int | None = None
    config_override: dict | None = None

    @field_validator("question")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("question must be non-empty")
        return v


class SearchRequest(BaseModel):
    query: str
    top_k: int = 8
    mode: str = "hybrid"

    @field_validator("query")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must be non-empty")
        return v


class IngestRequest(BaseModel):
    file_path: str


class IngestBatchRequest(BaseModel):
    file_paths: list[str]


def _register_routes(application: FastAPI, svc: RagService) -> None:
    @application.get("/v1/health")
    async def health():
        settings = get_settings()
        return {
            "status": "ok",
            "provider": settings.default_provider.value,
            "model": settings.openrouter_default_model,
            "documents_indexed": svc.document_count(),
            "backend": settings.vector_backend.value,
            "version": "0.3.0",
        }

    @application.post("/v1/ask")
    async def ask(
        req: AskRequest,
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        result = await svc.ask(req.question, req.top_k, req.config_override)
        status_code = 200
        if result.status == "rejected_budget":
            status_code = 402
        elif result.status == "rejected_security":
            status_code = 400
        payload = {
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
        if status_code != 200:
            return JSONResponse(status_code=status_code, content=payload)
        return payload

    @application.post("/v1/search")
    async def search(
        req: SearchRequest,
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        try:
            results = await svc.search(req.query, req.top_k, req.mode)
        except Exception as exc:
            from ragcore.security.injection import InjectionBlockedError

            if isinstance(exc, InjectionBlockedError):
                raise HTTPException(
                    status_code=400,
                    detail={"status": "rejected_security", "reason": str(exc)},
                ) from exc
            raise
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

    @application.post("/v1/documents")
    async def ingest(
        req: IngestRequest,
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        return svc.ingest(req.file_path)

    @application.post("/v1/documents/batch")
    async def ingest_batch(
        req: IngestBatchRequest,
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        results = await svc.ingest_batch(req.file_paths)
        return {
            "results": [
                {
                    "id": str(r.id),
                    "filename": r.filename,
                    "status": r.status,
                    "page_count": r.page_count,
                    "failure_reason": r.failure_reason,
                }
                for r in results
            ]
        }

    @application.post("/v1/documents/upload")
    async def upload_documents(
        authorization: str | None = Header(None),
        files: list[UploadFile] = File(...),
    ):
        """Multipart PDF upload — writes temp files then runs the ingest pipeline."""
        _check_auth(authorization)
        if not files:
            raise HTTPException(status_code=400, detail="No files uploaded")

        results: list[dict] = []
        for upload in files:
            filename = upload.filename or "upload.pdf"
            suffix = Path(filename).suffix or ".pdf"
            if suffix.lower() not in {".pdf", ".md", ".txt"}:
                results.append(
                    {
                        "id": str(uuid.UUID(int=0)),
                        "filename": filename,
                        "status": "failed",
                        "page_count": 0,
                        "failure_reason": f"unsupported file type: {suffix}",
                    }
                )
                continue

            tmp_path: str | None = None
            try:
                data = await upload.read()
                if not data:
                    raise ValueError("empty file")

                if suffix.lower() == ".pdf":
                    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
                    with os.fdopen(fd, "wb") as fh:
                        fh.write(data)
                    outcome = svc.ingest(tmp_path)
                else:
                    text = data.decode("utf-8", errors="replace")
                    outcome = svc.ingest_text(text, filename=filename)

                doc_id = outcome.get("id") or str(uuid.UUID(int=0))
                results.append(
                    {
                        "id": doc_id,
                        "filename": filename,
                        "status": outcome.get("status", "succeeded"),
                        "page_count": outcome.get("page_count", 0),
                        "failure_reason": None,
                        "chunks": outcome.get("chunks"),
                        "fingerprint": outcome.get("fingerprint"),
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "id": str(uuid.UUID(int=0)),
                        "filename": filename,
                        "status": "failed",
                        "page_count": 0,
                        "failure_reason": str(exc),
                    }
                )
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        return {"results": results}

    @application.get("/v1/documents/{document_id}")
    async def document_status(
        document_id: uuid.UUID,
        authorization: str | None = Header(None),
    ):
        _check_auth(authorization)
        try:
            result = await svc.document_status(document_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "id": str(result.id),
            "filename": result.filename,
            "status": result.status,
            "page_count": result.page_count,
            "failure_reason": result.failure_reason,
        }

    @application.get("/v1/budget")
    async def budget_status(authorization: str | None = Header(None)):
        _check_auth(authorization)
        result = await svc.budget_status()
        return {
            "period": result.period,
            "scope": result.scope,
            "cap_usd": result.cap_usd,
            "consumed_usd": result.consumed_usd,
            "rejected_count": result.rejected_count,
        }


# Register default routes on the module-level app
_register_middleware(app)
_register_routes(app, default_service)
