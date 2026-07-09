"""Accounting niche FastAPI app.

A thin FastAPI over the shared `production-rag-core` engine. Same shape
as apps/medical and apps/legal: reuses core's FastAPI routes, overrides
the prompt builder with an accounting-citation-grounded prompt, exposes
on port 8830.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel  # noqa: F401  (parity with medical/legal)

# Reuse the shared core
from ragcore.api.app import (
    AskRequest,  # noqa: F401
    IngestRequest,  # noqa: F401
    IngestBatchRequest,  # noqa: F401
    app as core_app,
)

from accounting.golden import write_golden

app = FastAPI(
    title="production-rag — accounting",
    description="Citation-grounded Q&A over US public-company filings (SEC EDGAR)",
    version="0.1.0",
)

API_TOKEN = os.getenv("API_TOKEN", "changeme")
NICHE = os.getenv("NICHE_NAME", "accounting")
CORPUS_DIR = Path(os.getenv("ACCOUNTING_CORPUS_DIR", "./corpus"))


def _check_auth(authorization: str | None) -> None:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


# Accounting-citation-grounded prompt: cite filer + form + section,
# never fabricate dollar amounts, surface restated figures when present.
def _build_accounting_prompt(question: str, passages: list[dict]) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are an accounting research assistant. Answer the question "
                "using ONLY the provided SEC filing passages. Always cite the "
                "filer (company name) and the form type (e.g. 10-K) inline. "
                "When the passage includes specific dollar amounts, reproduce "
                "them verbatim. If the passages don't support the answer, say "
                "so. Do not fabricate figures or holdings. This is general "
                "accounting information based on filed disclosures, not "
                "professional accounting advice."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Passages:\n\n"
                + "\n\n---\n\n".join(
                    f"[chunk_id={p.get('chunk_id', '?')}] [source={p.get('document_id', '?')}]\n"
                    f"{p['text']}"
                    for p in passages
                )
                + f"\n\nQuestion: {question}\n\nRespond in JSON with this exact schema:\n"
                '{"status": "answered" or "not_found",\n'
                ' "answer": "string",\n'
                ' "citations": [{"chunk_id": "<the chunk_id from the passage you used>", '
                '"excerpt": "<a short verbatim quote from that passage>", "page": 0}]}\n'
                "\nRules:\n"
                '- Citations MUST include the exact chunk_id you saw in the passages block\n'
                "- excerpt MUST be a verbatim substring of that passage\n"
                '- If passages don\'t support an answer, status="not_found" and answer=null'
            ),
        },
    ]


# Monkey-patch the core's prompt builder to use the accounting system prompt
import ragcore.generation.prompts as _prompts  # noqa: E402


def _accounting_build(question, passages):
    return _build_accounting_prompt(question, passages)


_prompts.build_prompt = _accounting_build


# Reuse all core routes
for route in core_app.routes:
    if hasattr(route, "path"):
        app.router.routes.append(route)


# Niche info
@app.get("/v1/niche")
async def niche_info(authorization: str | None = Header(None)):
    _check_auth(authorization)
    return {
        "niche": NICHE,
        "description": "Citation-grounded Q&A over US public-company filings (SEC EDGAR)",
        "corpus_dir": str(CORPUS_DIR.absolute()),
        "corpus_files": len(list(CORPUS_DIR.glob("*.md"))) if CORPUS_DIR.exists() else 0,
        "endpoints": ["/v1/ask", "/v1/search", "/v1/documents", "/v1/documents/batch", "/v1/budget", "/v1/health", "/v1/niche"],
    }


@app.post("/v1/golden")
async def generate_golden(authorization: str | None = Header(None)):
    """Write the accounting golden set to disk for the eval runner."""
    _check_auth(authorization)
    target = CORPUS_DIR.parent / "golden_set.json"
    write_golden(str(target))
    return {"written": str(target)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("ACCOUNTING_PORT", "8830")))
