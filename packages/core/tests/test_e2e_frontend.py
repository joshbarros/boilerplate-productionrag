"""End-to-end frontend test — runs the full ingest → ask → budget flow.

Hits the live FastAPI backend (must be running on :8800) and verifies that
the API contract that the Next.js frontend depends on is intact.

Run with:  cd apps/backend && uv run python tests/test_e2e_frontend.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "http://127.0.0.1:8800"
TOKEN = "changeme"
PDF = Path(__file__).parent / "fixtures" / "langchain_demo.pdf"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[2m"
RESET = "\033[0m"


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        data=json.dumps(body).encode() if body else None,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def banner(label: str) -> None:
    print(f"\n{CYAN}━━━ {label} ━━━{RESET}")


def step(label: str) -> None:
    print(f"  {DIM}→{RESET} {label}…", end="", flush=True)


def ok(detail: str = "") -> None:
    print(f"  {GREEN}✓{RESET}{(' ' + detail) if detail else ''}")


def fail(detail: str) -> None:
    print(f"  {RED}✗ {detail}{RESET}")
    sys.exit(1)


# ─── The flow ────────────────────────────────────────────────────────────────


def main() -> int:
    print(f"{CYAN}Production RAG — Frontend E2E Smoke{RESET}")
    print(f"  API: {API}")
    print(f"  PDF: {PDF.name} ({PDF.stat().st_size} bytes)")

    # 1. Health
    banner("1. /v1/health")
    step("Checking")
    code, body = call("GET", "/v1/health")
    if code != 200:
        fail(f"HTTP {code}: {body}")
    ok(
        f"provider={body.get('provider')} "
        f"model={body.get('model')} "
        f"docs={body.get('documents_indexed')}"
    )

    # 2. Ingest the fixture PDF
    banner("2. /v1/documents — ingest fixture")
    step("Submitting path")
    t0 = time.monotonic()
    code, body = call("POST", "/v1/documents", {"file_path": str(PDF)})
    elapsed = (time.monotonic() - t0) * 1000
    if code != 200:
        fail(f"HTTP {code}: {body}")
    status = body.get("status")
    if status not in ("succeeded", "duplicate"):
        fail(f"unexpected status: {status}")
    ok(f"status={status} chunks={body.get('chunks', '?')} {elapsed:.0f}ms")

    # 3. Ask an in-scope question
    banner("3. /v1/ask — in-scope question")
    for q, expect_cited in [
        ("What does a Document Loader do in LangChain?", True),
        ("Which Python class is used to load PDF files in LangChain?", True),
    ]:
        step(f"Q: {q[:60]}")
        t0 = time.monotonic()
        code, body = call("POST", "/v1/ask", {"question": q})
        elapsed = (time.monotonic() - t0) * 1000
        if code != 200:
            fail(f"HTTP {code}: {body}")
        status = body.get("status")
        citations = body.get("citations", [])
        cost = body.get("cost", {}).get("usd_estimate", 0)
        if expect_cited and status == "not_found":
            print(f"  {YELLOW}! cite-or-refuse downgraded to not_found{RESET}")
        if expect_cited and not citations:
            print(f"  {YELLOW}! no citations returned{RESET}")
        ok(
            f"status={status} citations={len(citations)} "
            f"${cost:.6f} {elapsed:.0f}ms"
        )

    # 4. Ask an out-of-scope question — should refuse
    banner("4. /v1/ask — out-of-scope (refusal)")
    step("Q: What is the capital of France?")
    code, body = call("POST", "/v1/ask", {"question": "What is the capital of France?"})
    if code != 200:
        fail(f"HTTP {code}: {body}")
    status = body.get("status")
    if status != "not_found":
        fail(f"expected not_found, got {status}")
    ok(f"correctly refused: {status}")

    # 5. Budget check
    banner("5. /v1/budget")
    step("Reading ledger")
    code, body = call("GET", "/v1/budget")
    if code != 200:
        fail(f"HTTP {code}: {body}")
    consumed = body.get("consumed_usd", 0)
    cap = body.get("cap_usd", 0)
    pct = (consumed / cap * 100) if cap else 0
    ok(
        f"${consumed:.6f} / ${cap:.2f} ({pct:.4f}%) "
        f"rejected={body.get('rejected_count')}"
    )

    # 6. Search-only
    banner("6. /v1/search — retrieval-only")
    step("Q: LangChain")
    code, body = call(
        "POST",
        "/v1/search",
        {"query": "LangChain Document Loader", "top_k": 3},
    )
    if code != 200:
        fail(f"HTTP {code}: {body}")
    results = body.get("results", [])
    ok(f"returned {len(results)} chunks")

    # Summary
    banner("Summary")
    print(f"  {GREEN}All E2E steps passed{RESET}")
    print(f"  Run: open {YELLOW}http://127.0.0.1:3000{RESET} to see the UI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
