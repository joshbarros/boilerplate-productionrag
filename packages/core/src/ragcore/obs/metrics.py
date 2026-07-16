"""Application metrics — ask latency, cost, answer status counters.

Exported via OTLP when telemetry is enabled; otherwise in-process only so
tests can assert without a collector.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

_lock = threading.Lock()


@dataclass
class _Counters:
    asks_total: int = 0
    asks_by_status: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    ask_latency_ms_sum: float = 0.0
    ask_latency_ms_count: int = 0
    cost_usd_sum: float = 0.0
    ingest_total: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


_state = _Counters()

# Optional OTel instruments (created lazily)
_ask_counter: Any = None
_latency_hist: Any = None
_cost_counter: Any = None
_instruments_ready = False


def _ensure_instruments() -> None:
    global _ask_counter, _latency_hist, _cost_counter, _instruments_ready
    if _instruments_ready:
        return
    _instruments_ready = True
    try:
        from opentelemetry import metrics

        from ragcore.config import get_settings

        settings = get_settings()
        if not settings.otel_enabled:
            return
        meter = metrics.get_meter(settings.otel_service_name)
        _ask_counter = meter.create_counter(
            "ragcore.asks",
            description="Total /v1/ask calls by status",
            unit="1",
        )
        _latency_hist = meter.create_histogram(
            "ragcore.ask.latency",
            description="Ask end-to-end latency",
            unit="ms",
        )
        _cost_counter = meter.create_counter(
            "ragcore.ask.cost_usd",
            description="Estimated USD spent on asks",
            unit="USD",
        )
    except Exception:
        _ask_counter = None
        _latency_hist = None
        _cost_counter = None


def record_ask(
    *,
    status: str,
    latency_ms: float,
    cost_usd: float = 0.0,
    cache_hit: bool = False,
) -> None:
    """Record one ask outcome."""
    with _lock:
        _state.asks_total += 1
        _state.asks_by_status[status] += 1
        _state.ask_latency_ms_sum += latency_ms
        _state.ask_latency_ms_count += 1
        _state.cost_usd_sum += cost_usd
        if cache_hit:
            _state.cache_hits += 1
        else:
            _state.cache_misses += 1

    _ensure_instruments()
    attrs = {"status": status}
    if _ask_counter is not None:
        _ask_counter.add(1, attrs)
    if _latency_hist is not None:
        _latency_hist.record(latency_ms, attrs)
    if _cost_counter is not None and cost_usd:
        _cost_counter.add(cost_usd, attrs)


def record_ingest() -> None:
    with _lock:
        _state.ingest_total += 1


@contextmanager
def timed_ask() -> Iterator[dict[str, float]]:
    """Context manager that fills elapsed_ms on the bag."""
    bag: dict[str, float] = {}
    t0 = time.perf_counter()
    try:
        yield bag
    finally:
        bag["elapsed_ms"] = (time.perf_counter() - t0) * 1000


def snapshot() -> dict[str, Any]:
    """In-process metrics snapshot (for /v1/metrics and tests)."""
    with _lock:
        count = max(_state.ask_latency_ms_count, 1)
        return {
            "asks_total": _state.asks_total,
            "asks_by_status": dict(_state.asks_by_status),
            "ask_latency_ms_avg": round(
                _state.ask_latency_ms_sum / count, 2
            )
            if _state.ask_latency_ms_count
            else 0.0,
            "cost_usd_sum": round(_state.cost_usd_sum, 6),
            "ingest_total": _state.ingest_total,
            "cache_hits": _state.cache_hits,
            "cache_misses": _state.cache_misses,
        }


def reset_for_tests() -> None:
    global _state
    with _lock:
        _state = _Counters()
