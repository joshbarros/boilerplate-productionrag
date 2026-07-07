"""Live-provider gated stress test.

Only runs when ``LIVE_PROVIDER_TEST=1`` is set in environment (never in CI
unless explicitly enabled). Calls the real OpenRouter endpoint with the
configured free model; budget-safe by design (free tier, max 20 requests).

Run locally:
    LIVE_PROVIDER_TEST=1 uv run pytest tests/test_live_provider.py -v -s
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import pytest

LIVE = os.getenv("LIVE_PROVIDER_TEST", "0") == "1"
skip_unless_live = pytest.mark.skipif(
    not LIVE,
    reason="set LIVE_PROVIDER_TEST=1 to run live-provider tests",
)


def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    sv = sorted(vals)
    idx = min(len(sv) - 1, max(0, int(round((p / 100.0) * (len(sv) - 1)))))
    return sv[idx]


@skip_unless_live
def test_openrouter_key_configured() -> None:
    """Fail fast if key is missing — better than a cryptic network error."""
    from ragcore.config import get_settings

    s = get_settings()
    assert s.openrouter_api_key, "OPENROUTER_API_KEY must be set for live tests"
    assert s.default_provider.value == "openrouter"


@skip_unless_live
def test_live_ingest_and_ask_fixture(tmp_path: Path) -> None:
    """Single live ask against the fixture PDF — asserts answered + citation."""
    import fitz  # noqa: PLC0415

    from ragcore.service import RagService  # noqa: PLC0415

    svc = RagService()

    pdf = tmp_path / "live_smoke.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        (
            "LangChain Demo Document. "
            "A sample PDF for testing LangChain document loaders. "
            "Document Loaders read files such as PDF, TXT, CSV, HTML into "
            "LangChain Document objects with page_content and metadata. "
            "Use PyPDFLoader to load a PDF and iterate over pages."
        ),
    )
    doc.save(str(pdf))
    doc.close()

    ingest = svc.ingest(str(pdf))
    assert ingest["status"] == "succeeded", f"ingest failed: {ingest}"
    assert ingest["chunks"] >= 1

    answer = asyncio.run(svc.ask("What does this document describe?", top_k=3))
    assert answer.status == "answered", (
        f"expected answered, got {answer.status}. "
        f"cost={answer.cost.prompt_tokens}+{answer.cost.completion_tokens}"
    )
    assert len(answer.citations) >= 1, "at least one verified citation required"
    assert answer.answer, "answer text must not be empty"


@skip_unless_live
def test_live_unanswerable_returns_not_found(tmp_path: Path) -> None:
    """Unanswerable question must return not_found without fabrication."""
    import fitz  # noqa: PLC0415

    from ragcore.service import RagService  # noqa: PLC0415

    svc = RagService()

    pdf = tmp_path / "live_unanswerable.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72), "This document only discusses PDF loading with LangChain."
    )
    doc.save(str(pdf))
    doc.close()

    svc.ingest(str(pdf))
    answer = asyncio.run(svc.ask("What is the population of Mars?", top_k=3))
    assert answer.status == "not_found", f"expected not_found, got {answer.status}"
    assert answer.answer is None, "answer must be null for not_found"
    assert answer.citations == [], "no citations expected"


@skip_unless_live
def test_live_concurrent_ask_latency(tmp_path: Path) -> None:
    """20 concurrent ask calls — all succeed, p95 < 30 s (free model)."""
    import fitz  # noqa: PLC0415

    from ragcore.service import RagService  # noqa: PLC0415

    svc = RagService()

    pdf = tmp_path / "live_concurrent.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        (
            "Concurrent load test document. "
            "LangChain document loaders support PDF, TXT, CSV, HTML files. "
            "Text Splitters break large documents into smaller chunks. "
            "Vector stores persist embeddings for similarity search."
        ),
    )
    doc.save(str(pdf))
    doc.close()

    svc.ingest(str(pdf))

    async def single_ask():
        t0 = time.perf_counter()
        result = await svc.ask("What file types are supported?", top_k=3)
        latency = (time.perf_counter() - t0) * 1000.0
        return result.status, latency

    async def run_concurrent():
        return await asyncio.gather(*[single_ask() for _ in range(20)])

    results = asyncio.run(run_concurrent())

    statuses = [r[0] for r in results]
    latencies = [r[1] for r in results]

    answered = statuses.count("answered")
    p50 = _pct(latencies, 50)
    p95 = _pct(latencies, 95)

    print(
        f"\nlive concurrent: answered={answered}/20  "
        f"p50={p50:.0f}ms  p95={p95:.0f}ms  max={max(latencies):.0f}ms"
    )

    assert answered >= 18, f"too many failures: {statuses}"
    assert p95 < 30_000, f"p95 latency too high: {p95:.0f}ms"
