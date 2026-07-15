"""Legal niche FastAPI app — CourtListener case law on port 8820."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Header, HTTPException

from ragcore.api.app import create_app
from ragcore.generation.prompts import niche_prompt_builder
from ragcore.service import RagService

from legal.golden import write_golden

API_TOKEN = os.getenv("API_TOKEN", "changeme")
NICHE = os.getenv("NICHE_NAME", "legal")
CORPUS_DIR = Path(os.getenv("LEGAL_CORPUS_DIR", "./corpus"))

_SYSTEM = (
    "You are a legal research assistant. Answer the question using "
    "ONLY the provided case law passages. Always cite the case name "
    "and reporter citation inline. If the passages don't support the "
    "answer, say so. Do not fabricate holdings or quote text that is "
    "not in the passages. Distinguish binding vs persuasive authority "
    "when the passage indicates it. This is general legal information, "
    "not legal advice."
)

svc = RagService(
    prompt_builder=niche_prompt_builder(_SYSTEM, source_label="case"),
)
app = create_app(svc)


def _check_auth(authorization: str | None) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/v1/niche")
async def niche_info(authorization: str | None = Header(None)):
    _check_auth(authorization)
    return {
        "niche": NICHE,
        "description": "Citation-grounded Q&A over US case law (CourtListener)",
        "corpus_dir": str(CORPUS_DIR.absolute()),
        "corpus_files": len(list(CORPUS_DIR.glob("*.md"))) if CORPUS_DIR.exists() else 0,
        "endpoints": [
            "/v1/ask",
            "/v1/search",
            "/v1/documents",
            "/v1/documents/batch",
            "/v1/documents/upload",
            "/v1/budget",
            "/v1/health",
            "/v1/niche",
        ],
    }


@app.post("/v1/golden")
async def generate_golden(authorization: str | None = Header(None)):
    _check_auth(authorization)
    target = CORPUS_DIR.parent / "golden_set.json"
    write_golden(str(target))
    return {"written": str(target)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("LEGAL_PORT", "8820")))
