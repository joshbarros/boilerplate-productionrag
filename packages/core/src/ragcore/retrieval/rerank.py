"""Cross-encoder rerank stage (T043) — always-on when enabled, lexical fallback.

Default production config has ``RERANK_ENABLED=true`` and
``RERANK_CROSS_ENCODER=true``. When the CrossEncoder model cannot load
(offline CI, missing weights), falls back to term-overlap scoring so the
pipeline stays available.
"""

from __future__ import annotations

import re
from collections import Counter

from ragcore.obs.otel import stage_span
from ragcore.retrieval.fusion import RetrievalResult

_cross_encoder = None
_cross_encoder_name: str | None = None


def _get_cross_encoder(model_name: str):
    global _cross_encoder, _cross_encoder_name
    if _cross_encoder is not None and _cross_encoder_name == model_name:
        return _cross_encoder
    from sentence_transformers import CrossEncoder

    _cross_encoder = CrossEncoder(model_name)
    _cross_encoder_name = model_name
    return _cross_encoder


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zà-ÿ0-9]{2,}", text.lower())


def lexical_rerank(
    query: str,
    results: list[RetrievalResult],
    top_k: int,
) -> list[RetrievalResult]:
    """Score by query-term overlap (no model download)."""
    q_terms = set(_tokenize(query))
    if not q_terms:
        return results[:top_k]

    scored: list[tuple[float, RetrievalResult]] = []
    for r in results:
        counts = Counter(_tokenize(r.text))
        score = sum(counts[t] for t in q_terms if t in counts)
        # blend with existing fused score if present
        blended = score + (r.fused_score or 0.0)
        scored.append((blended, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    out: list[RetrievalResult] = []
    for score, r in scored[:top_k]:
        r.fused_score = score
        out.append(r)
    return out


@stage_span("retrieve.rerank")
def rerank(
    query: str,
    results: list[RetrievalResult],
    top_k: int = 8,
    *,
    model_name: str = "BAAI/bge-reranker-v2-m3",
    use_cross_encoder: bool = True,
) -> list[RetrievalResult]:
    """Rerank retrieval results; always returns ≤ top_k items."""
    if not results:
        return []
    candidates = results[: max(top_k * 3, top_k)]

    if use_cross_encoder:
        try:
            model = _get_cross_encoder(model_name)
            pairs = [[query, r.text[:1500]] for r in candidates]
            scores = model.predict(pairs)
            ranked = sorted(
                zip(scores, candidates, strict=False),
                key=lambda x: float(x[0]),
                reverse=True,
            )
            out: list[RetrievalResult] = []
            for score, r in ranked[:top_k]:
                r.fused_score = float(score)
                out.append(r)
            return out
        except Exception:
            # Soft-fail: never break ask() because weights are missing.
            pass

    return lexical_rerank(query, candidates, top_k)
