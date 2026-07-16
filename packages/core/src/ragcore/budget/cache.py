"""In-process response cache — content-hash keyed with TTL (FR-012).

Key = sha256(masked_question + config_fingerprint). Stores serialized AnswerResult
payloads so repeated identical asks skip retrieval + LLM (and cost $0).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import asdict
from typing import Any

from ragcore.types import AnswerResult, CitationResult, CostReport


class ResponseCache:
    """Thread-safe TTL cache for AnswerResult objects."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, dict[str, Any]]] = {}
        self._hits = 0
        self._misses = 0

    @staticmethod
    def make_key(question: str, config: dict[str, Any] | None = None) -> str:
        payload = json.dumps(
            {"q": question.strip().lower(), "c": config or {}},
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get(self, key: str) -> AnswerResult | None:
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                self._misses += 1
                return None
            expires_at, payload = entry
            if now > expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return _deserialize(payload)

    def put(self, key: str, result: AnswerResult) -> None:
        # Never cache rejections (budget/security) — caller decides; still allow
        # answered / not_found / degraded.
        if result.status in ("rejected_budget", "rejected_security"):
            return
        with self._lock:
            self._store[key] = (time.time() + self._ttl, _serialize(result))

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "size": len(self._store),
                "hits": self._hits,
                "misses": self._misses,
            }

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0


def _serialize(result: AnswerResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "answer": result.answer,
        "citations": [asdict(c) for c in result.citations],
        "cost": asdict(result.cost),
        "latency_ms": result.latency_ms,
        "config": result.config,
    }


def _deserialize(payload: dict[str, Any]) -> AnswerResult:
    citations = [
        CitationResult(
            document_id=c["document_id"]
            if not isinstance(c["document_id"], str)
            else __import__("uuid").UUID(str(c["document_id"])),
            title=c.get("title", ""),
            page=c.get("page", 0),
            excerpt=c.get("excerpt", ""),
            support_score=c.get("support_score"),
        )
        for c in payload.get("citations", [])
    ]
    cost_raw = payload.get("cost") or {}
    cost = CostReport(
        prompt_tokens=cost_raw.get("prompt_tokens", 0),
        completion_tokens=cost_raw.get("completion_tokens", 0),
        embed_tokens=cost_raw.get("embed_tokens", 0),
        usd_estimate=cost_raw.get("usd_estimate", 0.0),
    )
    config = dict(payload.get("config") or {})
    config["cache_hit"] = True
    return AnswerResult(
        status=payload["status"],
        answer=payload.get("answer"),
        citations=citations,
        cost=cost,
        latency_ms=payload.get("latency_ms", 0),
        config=config,
    )
