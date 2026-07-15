"""Rerank unit tests — lexical path (no model download)."""

from __future__ import annotations

from ragcore.retrieval.fusion import RetrievalResult
from ragcore.retrieval.rerank import lexical_rerank, rerank


def _r(cid: str, text: str) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=cid,
        text=text,
        page=0,
        document_id="d",
        fused_score=0.1,
    )


def test_lexical_rerank_prefers_term_overlap() -> None:
    results = [
        _r("1", "unrelated gardening tips"),
        _r("2", "LangChain PDF loader documentation"),
        _r("3", "weather forecast tomorrow"),
    ]
    ranked = lexical_rerank("LangChain PDF", results, top_k=2)
    assert ranked[0].chunk_id == "2"
    assert len(ranked) == 2


def test_rerank_falls_back_without_cross_encoder() -> None:
    results = [_r("a", "alpha beta"), _r("b", "gamma")]
    out = rerank("alpha", results, top_k=1, use_cross_encoder=False)
    assert len(out) == 1
    assert out[0].chunk_id == "a"
