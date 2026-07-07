"""Reciprocal Rank Fusion (RRF) — combine vector + keyword rankings (D3).

RRF is simple, tunable, explainable: score = sum(1 / (k + rank_i))
for each retrieval arm. No training needed, traceable in a span.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ragcore.obs.otel import stage_span


@dataclass
class RetrievalResult:
    """A single retrieved chunk with fused score."""

    chunk_id: str
    text: str
    page: int
    document_id: str
    vector_score: float = 0.0
    keyword_score: float = 0.0
    fused_score: float = 0.0
    metadata: dict = field(default_factory=dict)


@stage_span("retrieve.fuse")
def reciprocal_rank_fusion(
    vector_results: list[RetrievalResult],
    keyword_results: list[RetrievalResult],
    k: int = 60,
    top_k: int = 8,
) -> list[RetrievalResult]:
    """Fuse vector and keyword results using RRF.

    Args:
        vector_results: Ranked results from vector search (best first).
        keyword_results: Ranked results from keyword/FTS search (best first).
        k: RRF constant (default 60, standard value).
        top_k: Number of fused results to return.

    Returns:
        Fused results sorted by RRF score, limited to top_k.
    """
    scores: dict[str, float] = {}
    result_map: dict[str, RetrievalResult] = {}

    # Vector arm: rank 1-based
    for rank, result in enumerate(vector_results, start=1):
        rrf_score = 1.0 / (k + rank)
        scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + rrf_score
        result_map[result.chunk_id] = result
        result_map[result.chunk_id].vector_score = rrf_score

    # Keyword arm
    for rank, result in enumerate(keyword_results, start=1):
        rrf_score = 1.0 / (k + rank)
        scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + rrf_score
        if result.chunk_id not in result_map:
            result_map[result.chunk_id] = result
        result_map[result.chunk_id].keyword_score = rrf_score

    # Sort by fused score
    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)

    results: list[RetrievalResult] = []
    for chunk_id in sorted_ids[:top_k]:
        result = result_map[chunk_id]
        result.fused_score = scores[chunk_id]
        results.append(result)

    return results
