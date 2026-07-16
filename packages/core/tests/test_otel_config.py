"""OTel configure_telemetry smoke tests."""

from __future__ import annotations

from ragcore.config import get_settings
from ragcore.obs.otel import configure_telemetry, stage_span


def test_configure_telemetry_disabled_is_noop() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    settings.otel_enabled = False
    configure_telemetry(force=True)

    @stage_span("test.stage")
    def work() -> int:
        return 42

    assert work() == 42


def test_stage_span_records_without_exporter() -> None:
    @stage_span("unit.demo")
    def add(a: int, b: int) -> int:
        return a + b

    assert add(2, 3) == 5
