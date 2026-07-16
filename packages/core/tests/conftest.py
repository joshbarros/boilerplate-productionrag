"""Pytest defaults — keep CI offline and free of model downloads."""

from __future__ import annotations

import os

# Always-on rerank is production default; tests use lexical path only.
os.environ.setdefault("RERANK_ENABLED", "true")
os.environ.setdefault("RERANK_CROSS_ENCODER", "false")
os.environ.setdefault("OTEL_ENABLED", "false")
os.environ.setdefault("VECTOR_BACKEND", "memory")
os.environ.setdefault("SECURITY_ENABLED", "true")

# Clear cached settings if already imported
try:
    from ragcore.config import get_settings

    get_settings.cache_clear()
except Exception:
    pass
