"""Configuration matrix eval — chunking × retrieval × rerank × backend (FR-008).

Runs offline (HashEmbedder + deterministic answers) so CI can publish a table
without API keys. Optional Qdrant arm is included when reachable.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ragcore.config import (
    ChunkingStrategy,
    RetrievalMode,
    VectorBackend,
    get_settings,
)
from ragcore.evals.offline import HashEmbedder, offline_generate_answer
from ragcore.evals.scorer import score_case
from ragcore.evals.types import EvalCase, EvalResult
from ragcore.service import RagService


@dataclass
class MatrixCell:
    chunking: str
    retrieval: str
    rerank: bool
    backend: str
    pass_rate: float
    answered_rate: float
    refusal_rate: float
    keyword_hit_rate: float
    citation_hit_rate: float
    avg_latency_ms: float
    total_cases: int
    error: str | None = None


@dataclass
class MatrixReport:
    fixture: str
    golden_version: str
    cells: list[MatrixCell] = field(default_factory=list)
    elapsed_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture": self.fixture,
            "golden_version": self.golden_version,
            "elapsed_ms": self.elapsed_ms,
            "cells": [asdict(c) for c in self.cells],
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Config matrix — {self.fixture} (v{self.golden_version})",
            "",
            f"Elapsed: {self.elapsed_ms} ms",
            "",
            "| chunk | ret | rr | be | pass | ans | ref | kw | cite | ms |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for c in self.cells:
            if c.error:
                lines.append(
                    f"| {c.chunking} | {c.retrieval} | {c.rerank} "
                    f"| {c.backend} | ERR | — | — | — | — | — |"
                )
            else:
                lines.append(
                    f"| {c.chunking} | {c.retrieval} | {c.rerank} "
                    f"| {c.backend} | {c.pass_rate:.1%} "
                    f"| {c.answered_rate:.1%} | {c.refusal_rate:.1%} "
                    f"| {c.keyword_hit_rate:.1%} "
                    f"| {c.citation_hit_rate:.1%} "
                    f"| {c.avg_latency_ms:.0f} |"
                )
        return "\n".join(lines) + "\n"


def _load_cases(path: str) -> tuple[str, str, list[EvalCase]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = [
        EvalCase(
            id=c["id"],
            question=c["question"],
            expected_status=c["expected_status"],
            keyword_hints=c.get("keyword_hints", []),
            expected_pages=c.get("expected_pages", []),
        )
        for c in data["cases"]
    ]
    return data["fixture"], str(data["version"]), cases


def _summarise_rates(results: list[EvalResult]) -> dict[str, float]:
    n = len(results) or 1
    passed = sum(1 for r in results if r.passed)
    in_scope = [r for r in results if r.expected_status == "answered"]
    out_scope = [r for r in results if r.expected_status == "not_found"]
    answered = sum(1 for r in in_scope if r.actual_status == "answered")
    refused = sum(1 for r in out_scope if r.actual_status == "not_found")
    ans_res = [r for r in in_scope if r.actual_status == "answered"]
    kw = sum(1 for r in ans_res if r.keyword_hit)
    cit = sum(1 for r in in_scope if r.citation_hit)
    return {
        "pass_rate": round(passed / n, 4),
        "answered_rate": round(answered / len(in_scope), 4) if in_scope else 0.0,
        "refusal_rate": round(refused / len(out_scope), 4) if out_scope else 0.0,
        "keyword_hit_rate": round(kw / len(ans_res), 4) if ans_res else 0.0,
        "citation_hit_rate": round(cit / len(in_scope), 4) if in_scope else 0.0,
        "avg_latency_ms": round(sum(r.latency_ms for r in results) / n, 1),
    }


async def _run_cell(
    *,
    cases: list[EvalCase],
    fixture_paths: list[str],
    chunking: str,
    retrieval: str,
    rerank: bool,
    backend: str,
) -> MatrixCell:
    import ragcore.service as service_module
    from ragcore.config import get_settings as _gs

    # Mutate cached settings for this cell (restore after)
    settings = _gs()
    prev = {
        "chunking_strategy": settings.chunking_strategy,
        "retrieval_mode": settings.retrieval_mode,
        "rerank_enabled": settings.rerank_enabled,
        "rerank_cross_encoder": settings.rerank_cross_encoder,
        "vector_backend": settings.vector_backend,
    }
    try:
        settings.chunking_strategy = ChunkingStrategy(chunking)
        settings.retrieval_mode = RetrievalMode(retrieval)
        settings.rerank_enabled = rerank
        # Matrix stays offline-friendly: lexical rerank only
        settings.rerank_cross_encoder = False
        settings.vector_backend = VectorBackend(backend)

        svc = RagService(backend=backend)
        emb = HashEmbedder()
        # Match vector size expectations for qdrant (pad in store)
        svc._embedder = emb  # type: ignore[assignment]
        svc._get_embedder = lambda: emb  # type: ignore[method-assign]
        original_gen = service_module.generate_answer
        service_module.generate_answer = offline_generate_answer  # type: ignore[assignment]
        try:
            for path in fixture_paths:
                p = Path(path)
                if p.suffix.lower() == ".pdf":
                    svc.ingest(str(p))
                else:
                    svc.ingest_text(
                        p.read_text(encoding="utf-8", errors="replace"),
                        filename=p.name,
                    )

            results: list[EvalResult] = []
            for case in cases:
                t0 = time.monotonic()
                ans = await svc.ask(
                    case.question,
                    top_k=8,
                    config_override={
                        "skip_cache": True,
                        "retrieval": retrieval,
                        "use_cross_encoder": False,
                    },
                )
                latency = int((time.monotonic() - t0) * 1000)
                results.append(score_case(case, ans, latency))
        finally:
            service_module.generate_answer = original_gen

        rates = _summarise_rates(results)
        return MatrixCell(
            chunking=chunking,
            retrieval=retrieval,
            rerank=rerank,
            backend=backend,
            total_cases=len(results),
            **rates,  # type: ignore[arg-type]
        )
    except Exception as exc:  # noqa: BLE001
        return MatrixCell(
            chunking=chunking,
            retrieval=retrieval,
            rerank=rerank,
            backend=backend,
            pass_rate=0.0,
            answered_rate=0.0,
            refusal_rate=0.0,
            keyword_hit_rate=0.0,
            citation_hit_rate=0.0,
            avg_latency_ms=0.0,
            total_cases=0,
            error=str(exc),
        )
    finally:
        for k, v in prev.items():
            setattr(settings, k, v)


def _qdrant_available() -> bool:
    try:
        from qdrant_client import QdrantClient

        url = get_settings().qdrant_url
        client = QdrantClient(url=url, prefer_grpc=False, timeout=2)
        client.get_collections()
        return True
    except Exception:
        return False


async def run_matrix(
    golden_path: str,
    fixture_paths: list[str],
    *,
    include_qdrant: bool | None = None,
    chunking: list[str] | None = None,
    retrieval: list[str] | None = None,
    rerank_opts: list[bool] | None = None,
) -> MatrixReport:
    """Execute the offline configuration matrix."""
    fixture_name, version, cases = _load_cases(golden_path)
    t0 = time.monotonic()

    chunking = chunking or ["recursive", "fixed", "semantic"]
    retrieval = retrieval or ["hybrid", "vector", "keyword"]
    rerank_opts = rerank_opts if rerank_opts is not None else [False, True]

    backends = ["memory"]
    if include_qdrant is None:
        include_qdrant = _qdrant_available()
    if include_qdrant:
        backends.append("qdrant")

    cells: list[MatrixCell] = []
    for ch in chunking:
        for ret in retrieval:
            for rr in rerank_opts:
                for be in backends:
                    cell = await _run_cell(
                        cases=cases,
                        fixture_paths=fixture_paths,
                        chunking=ch,
                        retrieval=ret,
                        rerank=rr,
                        backend=be,
                    )
                    cells.append(cell)

    return MatrixReport(
        fixture=fixture_name,
        golden_version=version,
        cells=cells,
        elapsed_ms=int((time.monotonic() - t0) * 1000),
    )


def run_matrix_sync(*args: Any, **kwargs: Any) -> MatrixReport:
    return asyncio.run(run_matrix(*args, **kwargs))
