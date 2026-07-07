from __future__ import annotations

import asyncio
import json
from pathlib import Path

import ragcore.service as service_module
from ragcore.generation.router import GenerationResult
from ragcore.service import RagService


class FakeEmbedder:
    model_id = "fake-embedder-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            length = float(len(text))
            alpha = float(sum(ch.isalpha() for ch in text))
            digits = float(sum(ch.isdigit() for ch in text))
            vectors.append([length, alpha, digits])
        return vectors


def test_ingest_search_and_ask_pipeline(monkeypatch) -> None:
    svc = RagService()

    monkeypatch.setattr(svc, "_get_embedder", lambda: FakeEmbedder())

    def fake_generate_answer(question: str, passages: list[dict], model_override=None):
        excerpt = passages[0]["text"][:80].strip()
        payload = {
            "status": "answered",
            "answer": "Mocked grounded answer.",
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
            prompt_tokens=12,
            completion_tokens=34,
            latency_ms=5,
        )

    monkeypatch.setattr(service_module, "generate_answer", fake_generate_answer)

    fixture = Path(__file__).parent / "fixtures" / "langchain_demo.pdf"
    ingest = svc.ingest(str(fixture))

    assert ingest["status"] == "succeeded"
    assert ingest["chunks"] > 0

    search_results = asyncio.run(svc.search("LangChain", top_k=3, mode="hybrid"))
    assert search_results
    assert all(r.text for r in search_results)

    answer = asyncio.run(svc.ask("What is this document about?", top_k=3))
    assert answer.status == "answered"
    assert answer.answer == "Mocked grounded answer."
    assert len(answer.citations) >= 1
    assert answer.cost.prompt_tokens == 12
    assert answer.cost.completion_tokens == 34
