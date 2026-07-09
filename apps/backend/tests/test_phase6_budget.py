"""Phase 6 budget tests: BudgetLedger unit tests + service integration."""

from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from ragcore.budget.ledger import (
    BudgetExceededError,
    BudgetLedger,
    QueryCost,
    estimate_usd,
)
from ragcore.generation.router import GenerationResult
from ragcore.service import RagService

# ─── estimate_usd ─────────────────────────────────────────────────────────────


def test_estimate_usd_free_model_is_zero() -> None:
    usd = estimate_usd("nvidia/nemotron-3-ultra-550b-a55b:free", 1000, 1000)
    assert usd == 0.0


def test_estimate_usd_paid_model_nonzero() -> None:
    usd = estimate_usd("gpt-4o-mini", 1000, 1000)
    assert usd > 0.0


def test_estimate_usd_fallback_for_unknown_model() -> None:
    usd = estimate_usd("some-totally-unknown-model", 1000, 1000)
    assert usd > 0.0  # conservative fallback applied


def test_estimate_usd_scales_with_tokens() -> None:
    usd_small = estimate_usd("gpt-4o-mini", 100, 100)
    usd_large = estimate_usd("gpt-4o-mini", 10000, 10000)
    assert usd_large > usd_small


# ─── BudgetLedger.check ───────────────────────────────────────────────────────


def test_check_passes_when_under_all_caps() -> None:
    ledger = BudgetLedger(daily_cap_usd=10.0, query_cap_usd=1.0)
    ledger.check(0.50)  # should not raise


def test_check_raises_on_query_cap_breach() -> None:
    ledger = BudgetLedger(daily_cap_usd=10.0, query_cap_usd=0.05)
    with pytest.raises(BudgetExceededError) as exc_info:
        ledger.check(0.10)
    assert exc_info.value.kind == "query"
    assert exc_info.value.cap_usd == 0.05


def test_check_raises_on_daily_cap_breach() -> None:
    ledger = BudgetLedger(daily_cap_usd=0.10, query_cap_usd=1.0)
    # gpt-4o at 10k tokens each: 10k*$0.005/1k + 10k*$0.015/1k = $0.05+$0.15 = $0.20
    # After recording $0.20, the daily cap of $0.10 is already consumed + exceeded
    ledger.record("gpt-4o", 10000, 10000)
    with pytest.raises(BudgetExceededError) as exc_info:
        ledger.check(0.01)
    assert exc_info.value.kind == "daily"
    assert exc_info.value.cap_usd == 0.10


def test_check_rejected_count_increments() -> None:
    ledger = BudgetLedger(daily_cap_usd=0.01, query_cap_usd=100.0)
    for _ in range(3):
        try:
            ledger.check(0.05)
        except BudgetExceededError:
            pass
    snap = ledger.snapshot()
    assert snap["rejected_count"] == 3


# ─── BudgetLedger.record ──────────────────────────────────────────────────────


def test_record_returns_query_cost() -> None:
    ledger = BudgetLedger(daily_cap_usd=10.0, query_cap_usd=1.0)
    cost = ledger.record("gpt-4o-mini", 500, 200)
    assert isinstance(cost, QueryCost)
    assert cost.prompt_tokens == 500
    assert cost.completion_tokens == 200
    assert cost.usd > 0.0


def test_record_accumulates_consumed_usd() -> None:
    ledger = BudgetLedger(daily_cap_usd=10.0, query_cap_usd=1.0)
    ledger.record("gpt-4o-mini", 500, 200)
    ledger.record("gpt-4o-mini", 500, 200)
    snap = ledger.snapshot()
    assert snap["consumed_usd"] > 0.0
    assert snap["query_count"] == 2


def test_record_free_model_zero_consumed() -> None:
    ledger = BudgetLedger(daily_cap_usd=10.0, query_cap_usd=1.0)
    ledger.record("nvidia/nemotron-3-ultra-550b-a55b:free", 1000, 500)
    snap = ledger.snapshot()
    assert snap["consumed_usd"] == 0.0
    assert snap["query_count"] == 1


# ─── BudgetLedger.snapshot ────────────────────────────────────────────────────


def test_snapshot_structure() -> None:
    ledger = BudgetLedger(daily_cap_usd=5.0, query_cap_usd=0.10)
    snap = ledger.snapshot()
    assert set(snap.keys()) == {
        "period",
        "scope",
        "daily_cap_usd",
        "query_cap_usd",
        "consumed_usd",
        "rejected_count",
        "query_count",
    }
    assert snap["scope"] == "daily"
    assert snap["daily_cap_usd"] == 5.0
    assert snap["query_cap_usd"] == 0.10


# ─── service.ask + budget integration ────────────────────────────────────────


class FakeEmbedder:
    model_id = "fake/embedding-model"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]


def _make_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "Budget enforcement test document. "
        "LangChain uses embeddings to retrieve relevant passages for RAG.",
    )
    doc.save(str(path))
    doc.close()


@pytest.mark.asyncio
async def test_ask_records_cost_in_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful ask → ledger.query_count increments by 1."""
    import ragcore.service as svc_mod  # noqa: PLC0415

    pdf = tmp_path / "budget_test.pdf"
    _make_pdf(pdf)

    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]

    def fake_generate(question, passages, model_override=None):
        payload = {
            "status": "answered",
            "answer": "Budget answer.",
            "citations": [
                {"chunk_id": passages[0]["chunk_id"], "page": 0, "excerpt": "test"}
            ],
        }
        return GenerationResult(
            text=json.dumps(payload),
            model_used="nvidia/nemotron-3-ultra-550b-a55b:free",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=1,
        )

    monkeypatch.setattr(svc_mod, "generate_answer", fake_generate)
    svc.ingest(str(pdf))

    await svc.ask("What is this document about?")

    snap = svc._ledger.snapshot()
    assert snap["query_count"] == 1


@pytest.mark.asyncio
async def test_ask_returns_rejected_budget_when_daily_cap_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ask() returns rejected_budget when the daily cap is already exhausted."""
    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]

    # Force the ledger to look exhausted by patching its check method
    def _always_reject(usd: float) -> None:
        from ragcore.budget.ledger import BudgetExceededError  # noqa: PLC0415

        raise BudgetExceededError("daily", 0.01, usd)

    svc._ledger.check = _always_reject  # type: ignore[method-assign]

    result = await svc.ask("Any question at all")
    assert result.status == "rejected_budget"
    assert result.config["kind"] == "daily"


@pytest.mark.asyncio
async def test_budget_status_reflects_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """budget_status() returns a BudgetStatusResult matching the ledger state."""
    import ragcore.service as svc_mod  # noqa: PLC0415

    pdf = tmp_path / "budget_status.pdf"
    _make_pdf(pdf)

    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]

    def fake_generate(question, passages, model_override=None):
        payload = {
            "status": "answered",
            "answer": "OK.",
            "citations": [
                {"chunk_id": passages[0]["chunk_id"], "page": 0, "excerpt": "ok"}
            ],
        }
        return GenerationResult(
            text=json.dumps(payload),
            model_used="nvidia/nemotron-3-ultra-550b-a55b:free",
            prompt_tokens=50,
            completion_tokens=20,
            latency_ms=1,
        )

    monkeypatch.setattr(svc_mod, "generate_answer", fake_generate)
    svc.ingest(str(pdf))
    await svc.ask("What is RAG?")

    status = await svc.budget_status()
    assert status.scope == "daily"
    assert status.consumed_usd >= 0.0
    assert status.rejected_count == 0
    assert status.cap_usd == svc._ledger._daily_cap
