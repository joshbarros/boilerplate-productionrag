from __future__ import annotations

from ragcore.retrieval.fusion import RetrievalResult, reciprocal_rank_fusion


def _rr(chunk_id: str, text: str = "t") -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        text=text,
        page=0,
        document_id="d1",
    )


def test_rrf_prioritizes_cross_arm_overlap() -> None:
    vector = [_rr("a"), _rr("b"), _rr("c")]
    keyword = [_rr("x"), _rr("b"), _rr("y")]

    fused = reciprocal_rank_fusion(vector, keyword, k=60, top_k=5)

    assert fused
    assert fused[0].chunk_id == "b"
    assert fused[0].fused_score > fused[1].fused_score
    assert fused[0].vector_score > 0
    assert fused[0].keyword_score > 0


def test_rrf_empty_inputs_return_empty() -> None:
    assert reciprocal_rank_fusion([], [], k=60, top_k=8) == []
