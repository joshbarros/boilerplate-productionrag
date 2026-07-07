"""OTel observability — span-per-stage decorators with token/cost/latency attrs.

Constitution III: every pipeline stage (ingest, chunk, embed, retrieve, rerank,
generate) emits OTel spans with token counts, cost attribution, and latency.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from typing import Any, TypeVar

from opentelemetry import trace

from ragcore.config import get_settings

F = TypeVar("F", bound=Callable[..., Any])

# Tracer is created lazily so tests don't require an OTel collector
_tracer: trace.Tracer | None = None


def _get_tracer() -> trace.Tracer:
    global _tracer
    if _tracer is None:
        settings = get_settings()
        _tracer = trace.get_tracer(settings.otel_service_name)
    return _tracer


def stage_span(name: str) -> Callable[[F], F]:
    """Decorator that wraps a pipeline stage in an OTel span.

    Records timing automatically. The wrapped function can attach token/cost
    attributes by returning a dict with a ``_otel_attrs`` key, or by calling
    ``set_span_attrs()`` within the function body.

    Usage::

        @stage_span("retrieve.vector")
        def vector_search(query: str, top_k: int) -> list[Chunk]:
            ...
    """

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
                    # If the function returned attrs, attach them
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
