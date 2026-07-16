"""Semantic chunker — group adjacent sentences by embedding similarity (T042).

Uses a lightweight character n-gram embedding by default so unit tests and
air-gapped hosts never download models. Pass an ``Embedder`` for higher quality.
"""

from __future__ import annotations

import math
import re
import uuid

from ragcore.chunking.base import Chunker, ChunkResult
from ragcore.obs.otel import stage_span

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n{2,}")


def _char_ngram_vec(text: str, n: int = 3) -> list[float]:
    """Sparse-ish dense bag of character n-grams (fixed 256 dims via hashing)."""
    dims = 256
    vec = [0.0] * dims
    cleaned = re.sub(r"\s+", " ", text.lower()).strip()
    if len(cleaned) < n:
        if cleaned:
            vec[hash(cleaned) % dims] += 1.0
        return vec
    for i in range(len(cleaned) - n + 1):
        gram = cleaned[i : i + n]
        vec[hash(gram) % dims] += 1.0
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return sum(a[i] * b[i] for i in range(n))


class SemanticChunker(Chunker):
    """Sentence-boundary chunker that splits when topic similarity drops."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        similarity_threshold: float = 0.35,
        embedder: object | None = None,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.similarity_threshold = similarity_threshold
        self._embedder = embedder

    @stage_span("chunk.semantic")
    def chunk(
        self,
        text: str,
        pages: list[str],
        document_id: uuid.UUID,
    ) -> list[ChunkResult]:
        if not text or not text.strip():
            return []

        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
        if not sentences:
            return []

        if self._embedder is not None and hasattr(self._embedder, "embed"):
            vectors = self._embedder.embed(sentences)  # type: ignore[union-attr]
        else:
            vectors = [_char_ngram_vec(s) for s in sentences]

        groups: list[list[str]] = []
        current: list[str] = [sentences[0]]
        current_len = len(sentences[0])

        for i in range(1, len(sentences)):
            sent = sentences[i]
            sim = _cosine(vectors[i - 1], vectors[i])
            would_overflow = current_len + 1 + len(sent) > self.chunk_size
            topic_break = sim < self.similarity_threshold

            if (would_overflow or topic_break) and current:
                groups.append(current)
                # Overlap: keep tail sentences that fit in overlap budget
                overlap: list[str] = []
                budget = self.chunk_overlap
                for prev in reversed(current):
                    if budget <= 0:
                        break
                    overlap.insert(0, prev)
                    budget -= len(prev) + 1
                current = overlap + [sent]
                current_len = sum(len(s) for s in current) + max(0, len(current) - 1)
            else:
                current.append(sent)
                current_len += 1 + len(sent)

        if current:
            groups.append(current)

        chunks: list[ChunkResult] = []
        for group in groups:
            chunk_text = " ".join(group).strip()
            if not chunk_text:
                continue
            page_start, page_end = self._find_pages(chunk_text, pages)
            chunks.append(
                ChunkResult(
                    text=chunk_text,
                    page_start=page_start,
                    page_end=page_end,
                    metadata={
                        "strategy": "semantic",
                        "document_id": str(document_id),
                        "sentence_count": len(group),
                    },
                )
            )
        return chunks

    def _find_pages(self, chunk_text: str, pages: list[str]) -> tuple[int, int]:
        if not pages:
            return 0, 0
        fingerprint = re.sub(r"\s+", " ", chunk_text).strip()[:50]
        if not fingerprint:
            return 0, 0
        for i, page_text in enumerate(pages):
            page_clean = re.sub(r"\s+", " ", page_text).strip()
            if fingerprint[:30] in page_clean:
                return i, i
        return 0, max(0, len(pages) - 1)
