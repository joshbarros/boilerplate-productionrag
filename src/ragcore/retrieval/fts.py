"""Keyword search — simple in-memory BM25-like scoring (D3).

Production uses Postgres FTS (tsvector with portuguese + english configs).
For the MVP demo, this provides keyword search that catches exact codes
and acronyms that vector search misses (Constitution IV).
"""

from __future__ import annotations

import re
from collections import Counter

from ragcore.retrieval.fusion import RetrievalResult
from ragcore.retrieval.vector_pg import IndexedChunk


class InMemoryKeywordSearch:
    """Simple keyword search with TF-based scoring.

    Catches exact identifiers, codes, and acronyms (FR-004).
    Will be replaced by Postgres FTS in production (D3).
    """

    def __init__(self) -> None:
        self._chunks: list[IndexedChunk] = []
        self._tokenized: list[list[str]] = []

    def add(self, chunk: IndexedChunk) -> None:
        self._chunks.append(chunk)
        self._tokenized.append(self._tokenize(chunk.text))

    def add_batch(self, chunks: list[IndexedChunk]) -> None:
        for chunk in chunks:
            self.add(chunk)

    def search(
        self,
        query: str,
        top_k: int = 8,
    ) -> list[RetrievalResult]:
        """Score chunks by query term frequency."""
        if not self._chunks:
            return []

        query_terms = set(self._tokenize(query))
        if not query_terms:
            return []

        results: list[tuple[float, IndexedChunk]] = []
        for tokens, chunk in zip(self._tokenized, self._chunks, strict=False):
            chunk_terms = Counter(tokens)
            score = 0.0
            for term in query_terms:
                if term in chunk_terms:
                    # TF score (simplified BM25 without IDF for MVP)
                    score += chunk_terms[term]
            if score > 0:
                results.append((score, chunk))

        results.sort(key=lambda x: x[0], reverse=True)

        return [
            RetrievalResult(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                page=chunk.page,
                document_id=chunk.document_id,
                keyword_score=score,
                metadata=chunk.metadata,
            )
            for score, chunk in results[:top_k]
        ]

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase, split on non-alphanumeric, keep tokens ≥ 2 chars."""
        text = text.lower()
        tokens = re.findall(r"[a-zà-ÿ0-9]{2,}", text)
        return tokens
