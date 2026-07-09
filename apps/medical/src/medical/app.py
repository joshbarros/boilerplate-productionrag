"""Medical niche FastAPI app.

A thin FastAPI over the shared `production-rag-core` engine. All the
RAG work happens in the core; this app only:

1. Configures a niche-specific LLM prompt
2. Exposes /v1/* endpoints on a different port (8810)
3. Wires the medical golden set into the eval runner

The web frontend (apps/web) can target this backend via the
NEXT_PUBLIC_BACKEND_URL env var to enable the medical niche switcher.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# Reuse the shared core
from ragcore.api.app import (
    AskRequest,
    IngestRequest,
    IngestBatchRequest,
    app as core_app,
    service as core_service,
)
from ragcore.generation.prompts import build_prompt

from medical.golden import write_golden

# Mount core routes under a prefix so the medical app is self-contained
# on its own port. This means /v1/* on :8810 calls into the same
# ragcore service as /v1/* on :8800 — they're the same engine, just
# different config (different prompt, different corpus).
app = FastAPI(
    title="production-rag — medical",
    description="Citation-grounded Q&A over PubMed Central open-access literature",
    version="0.1.0",
)

API_TOKEN = os.getenv("API_TOKEN", "changeme")
NICHE = os.getenv("NICHE_NAME", "medical")
CORPUS_DIR = Path(os.getenv("MEDICAL_CORPUS_DIR", "./corpus"))


def _check_auth(authorization: str | None) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


# Override the prompt for medical context — physician's clinical
# reference tone, source-faithful.
def _build_medical_prompt(question: str, passages: list[dict]) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are a clinical reference assistant. Answer the question "
                "using ONLY the provided PubMed article passages. Always cite "
                "the source (PMID) inline. If the passages don't support the "
                "answer, say so. Do not fabricate."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Passages:\n\n"
                + "\n\n---\n\n".join(
                    f"[PMID:{p.get('document_id', '?')}] {p['text']}" for p in passages
                )
                + f"\n\nQuestion: {question}\n\nRespond in JSON with "
                '"status", "answer", "citations": [{"pmid": ..., "excerpt": ...}]'
            ),
        },
    ]


# Monkey-patch the core's prompt builder to use the medical system prompt
import ragcore.generation.router as _router
import ragcore.generation.prompts as _prompts

_original_build = _prompts.build_prompt
def _medical_build(question, passages):
    return _build_medical_prompt(question, passages)
_prompts.build_prompt = _medical_build


# Reuse all core routes
for route in core_app.routes:
    if hasattr(route, "path"):
        app.router.routes.append(route)


# Add a niche info endpoint
@app.get("/v1/niche")
async def niche_info(authorization: str | None = Header(None)):
    _check_auth(authorization)
    return {
        "niche": NICHE,
        "description": "Citation-grounded Q&A over PubMed Central open-access literature",
        "corpus_dir": str(CORPUS_DIR.absolute()),
        "corpus_files": len(list(CORPUS_DIR.glob("*.md"))) if CORPUS_DIR.exists() else 0,
        "endpoints": ["/v1/ask", "/v1/search", "/v1/documents", "/v1/documents/batch", "/v1/budget", "/v1/health", "/v1/niche"],
    }


@app.post("/v1/golden")
async def generate_golden(authorization: str | None = Header(None)):
    """Write the medical golden set to disk for the eval runner."""
    _check_auth(authorization)
    target = CORPUS_DIR.parent / "golden_set.json"
    write_golden(str(target))
    return {"written": str(target)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("MEDICAL_PORT", "8810")))
