"""Niche prompt builders are bound to RagService — no global monkey-patch."""

from __future__ import annotations

import asyncio
import json

import ragcore.service as service_module
from ragcore.generation.prompts import niche_prompt_builder
from ragcore.generation.router import GenerationResult
from ragcore.service import RagService


class FakeEmbedder:
    model_id = "fake-embedder-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]


def test_two_services_keep_distinct_prompts(monkeypatch) -> None:
    seen: list[str] = []

    def capture_generate(question, passages, model_override=None, prompt_builder=None):
        msgs = (prompt_builder or (lambda q, p: []))(question, passages)
        system = msgs[0]["content"] if msgs else ""
        seen.append(system[:40])
        excerpt = passages[0]["text"][:40] if passages else "x"
        payload = {
            "status": "answered",
            "answer": "ok",
            "citations": [
                {
                    "chunk_id": passages[0]["chunk_id"],
                    "page": 0,
                    "excerpt": excerpt,
                }
            ],
        }
        return GenerationResult(
            text=json.dumps(payload),
            model_used="mock",
            prompt_tokens=1,
            completion_tokens=1,
            latency_ms=1,
        )

    monkeypatch.setattr(service_module, "generate_answer", capture_generate)

    medical = RagService(
        prompt_builder=niche_prompt_builder("You are a clinical assistant.")
    )
    legal = RagService(
        prompt_builder=niche_prompt_builder("You are a legal research assistant.")
    )
    medical._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]
    legal._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]

    medical.ingest_text(
        "Patient fever is a clinical sign of infection.", filename="m.md"
    )
    legal.ingest_text(
        "The court held that fair use applies to parody.", filename="l.md"
    )

    asyncio.run(medical.ask("What is fever?"))
    asyncio.run(legal.ask("What is fair use?"))

    assert any("clinical" in s.lower() for s in seen)
    assert any("legal" in s.lower() for s in seen)
