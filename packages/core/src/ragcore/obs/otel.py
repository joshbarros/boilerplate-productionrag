"""OTel observability — span-per-stage + optional OTLP export.

Constitution III: every pipeline stage emits spans with latency (and optional
token/cost attrs). Call ``configure_telemetry()`` once at process start to
wire the OTLP exporter (collector → Tempo/Prometheus/Grafana).
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from ragcore.config import get_settings

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

_tracer: trace.Tracer | None = None
_configured = False


def configure_telemetry(*, force: bool = False) -> None:
    """Install TracerProvider + OTLP exporter when enabled.

    Safe to call multiple times. No-ops when ``otel_enabled=False`` unless
    ``force=True``. Failures are logged and swallowed so missing collectors
    never crash the app.
    """
    global _tracer, _configured
    if _configured and not force:
        return

    settings = get_settings()
    if not settings.otel_enabled:
        _configured = True
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": "0.3.0",
        }
    )
    provider = TracerProvider(resource=resource)

    if settings.otel_console_export:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    endpoint = settings.otel_exporter_otlp_endpoint
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(
                endpoint=endpoint,
                insecure=settings.otel_insecure,
            )
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTel OTLP exporter → %s", endpoint)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OTel OTLP exporter unavailable: %s", exc)

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(settings.otel_service_name)

    # Metrics (OTLP) — best-effort; spans still work if metrics SDK missing
    try:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        metric_readers = []
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )

            reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=endpoint,
                    insecure=settings.otel_insecure,
                ),
                export_interval_millis=15000,
            )
            metric_readers.append(reader)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OTel metrics exporter unavailable: %s", exc)

        if metric_readers:
            metrics.set_meter_provider(
                MeterProvider(resource=resource, metric_readers=metric_readers)
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("OTel metrics SDK unavailable: %s", exc)

    _configured = True


def _get_tracer() -> trace.Tracer:
    global _tracer
    if _tracer is None:
        # Lazy: use global provider (noop if never configured)
        settings = get_settings()
        _tracer = trace.get_tracer(settings.otel_service_name)
    return _tracer


def stage_span(name: str) -> Callable[[F], F]:
    """Decorator that wraps a pipeline stage in an OTel span."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = _get_tracer()
            with tracer.start_as_current_span(name) as span:
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    span.set_attribute(f"{name}.latency_ms", elapsed_ms)
                    if isinstance(result, dict) and "_otel_attrs" in result:
                        for key, value in result["_otel_attrs"].items():
                            span.set_attribute(key, value)
                    return result
                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    span.set_attribute(f"{name}.latency_ms", elapsed_ms)
                    span.set_attribute(f"{name}.error", str(exc))
                    span.record_exception(exc)
                    raise

        return wrapper  # type: ignore[return-value]

    return decorator


def set_span_attrs(**kwargs: Any) -> None:
    """Set attributes on the current active span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        for key, value in kwargs.items():
            span.set_attribute(key, value)
