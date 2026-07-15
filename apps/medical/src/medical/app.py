"""Medical niche FastAPI app — PubMed-grounded Q&A on port 8810.

Uses ``create_app(RagService(prompt_builder=...))`` — no monkey-patching.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import Header, HTTPException

from ragcore.api.app import create_app
from ragcore.generation.prompts import niche_prompt_builder
from ragcore.service import RagService

from medical.golden import write_golden

API_TOKEN = os.getenv("API_TOKEN", "changeme")
NICHE = os.getenv("NICHE_NAME", "medical")
CORPUS_DIR = Path(os.getenv("MEDICAL_CORPUS_DIR", "./corpus"))

_SYSTEM = (
    "You are a clinical reference assistant. Answer the question "
    "using ONLY the provided PubMed article passages. Always cite "
    "the source (PMID) inline. If the passages don't support the "
    "answer, say so. Do not fabricate."
)

svc = RagService(
    prompt_builder=niche_prompt_builder(_SYSTEM, source_label="PMID"),
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
        "description": "Citation-grounded Q&A over PubMed Central open-access literature",
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

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("MEDICAL_PORT", "8810")))
