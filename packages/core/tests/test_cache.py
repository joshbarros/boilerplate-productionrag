"""Response cache tests."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import ragcore.service as service_module
from ragcore.budget.cache import ResponseCache
from ragcore.generation.router import GenerationResult
from ragcore.service import RagService
from ragcore.types import AnswerResult, CostReport


class FakeEmbedder:
    model_id = "fake-embedder-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 1.0, 0.0] for t in texts]


def test_cache_roundtrip() -> None:
    cache = ResponseCache(ttl_seconds=60)
    key = ResponseCache.make_key("hello", {"top_k": 3})
    original = AnswerResult(
        status="not_found",
        answer=None,
        cost=CostReport(usd_estimate=0.0),
        config={"backend": "memory"},
    )
    cache.put(key, original)
    hit = cache.get(key)
    assert hit is not None
    assert hit.status == "not_found"
    assert hit.config.get("cache_hit") is True
    assert cache.stats()["hits"] == 1


def test_ask_uses_cache(monkeypatch) -> None:
    calls = {"n": 0}
    svc = RagService()
    monkeypatch.setattr(svc, "_get_embedder", lambda: FakeEmbedder())

    def fake_generate(question, passages, model_override=None, **_kwargs):
        calls["n"] += 1
        excerpt = passages[0]["text"][:40].strip()
        payload = {
            "status": "answered",
            "answer": "Cached answer body.",
            "citations": [
                {
                    "chunk_id": passages[0]["chunk_id"],
                    "page": passages[0]["page"],
                    "excerpt": excerpt,
                }
            ],
        }
        return GenerationResult(
            text=json.dumps(payload),
            model_used="mock/model:free",
            prompt_tokens=10,
            completion_tokens=20,
            latency_ms=1,
        )

    monkeypatch.setattr(service_module, "generate_answer", fake_generate)
    fixture = Path(__file__).parent / "fixtures" / "langchain_demo.pdf"
    svc.ingest(str(fixture))

    a1 = asyncio.run(svc.ask("What is LangChain about?", top_k=3))
    a2 = asyncio.run(svc.ask("What is LangChain about?", top_k=3))
    assert a1.status == "answered"
    assert a2.config.get("cache_hit") is True
    assert calls["n"] == 1
