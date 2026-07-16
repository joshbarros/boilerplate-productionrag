"""In-process metrics tests."""

from __future__ import annotations

import asyncio

from ragcore.obs.metrics import record_ask, reset_for_tests, snapshot
from ragcore.service import RagService


def test_record_ask_snapshot() -> None:
    reset_for_tests()
    record_ask(status="answered", latency_ms=12.5, cost_usd=0.001)
    record_ask(status="not_found", latency_ms=5.0, cost_usd=0.0)
    snap = snapshot()
    assert snap["asks_total"] == 2
    assert snap["asks_by_status"]["answered"] == 1
    assert snap["asks_by_status"]["not_found"] == 1
    assert snap["ask_latency_ms_avg"] > 0


def test_ask_records_metrics(monkeypatch) -> None:
    reset_for_tests()
    svc = RagService()

    async def fake_inner(*_a, **_k):
        from ragcore.types import AnswerResult, CostReport

        return AnswerResult(
            status="not_found",
            cost=CostReport(usd_estimate=0.0),
            config={},
        )

    monkeypatch.setattr(svc, "_ask_inner", fake_inner)
    asyncio.run(svc.ask("hello?"))
    snap = snapshot()
    assert snap["asks_total"] >= 1
