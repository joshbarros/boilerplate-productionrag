"""Accounting niche FastAPI app — SEC EDGAR filings on port 8830."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Header, HTTPException

from ragcore.api.app import create_app
from ragcore.generation.prompts import niche_prompt_builder
from ragcore.service import RagService

from accounting.golden import write_golden

API_TOKEN = os.getenv("API_TOKEN", "changeme")
NICHE = os.getenv("NICHE_NAME", "accounting")
CORPUS_DIR = Path(os.getenv("ACCOUNTING_CORPUS_DIR", "./corpus"))

_SYSTEM = (
    "You are an accounting research assistant. Answer the question "
    "using ONLY the provided SEC filing passages. Always cite the "
    "filer (company name) and the form type (e.g. 10-K) inline. "
    "When the passage includes specific dollar amounts, reproduce "
    "them verbatim. If the passages don't support the answer, say "
    "so. Do not fabricate figures or holdings. This is general "
    "accounting information based on filed disclosures, not "
    "professional accounting advice."
)

svc = RagService(
    prompt_builder=niche_prompt_builder(_SYSTEM, source_label="filing"),
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
        "description": "Citation-grounded Q&A over US public-company filings (SEC EDGAR)",
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

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("ACCOUNTING_PORT", "8830")))
