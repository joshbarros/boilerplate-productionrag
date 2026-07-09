"""Vector search via pgvector HNSW cosine similarity.

In Phase 3 (MVP), we use an in-memory store for the demo. The pgvector
backend is wired in Phase 2's models and will be activated once
Postgres is running via docker-compose. For now, this provides a
working vector search that can be swapped for pgvector later.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ragcore.retrieval.fusion import RetrievalResult


@dataclass
class IndexedChunk:
    """In-memory indexed chunk with embedding."""

    chunk_id: str
    text: str
    page: int
    document_id: str
    embedding: list[float]
    metadata: dict


class InMemoryVectorStore:
    """Simple in-memory vector store with cosine similarity.

    Will be replaced by pgvector HNSW in production (D2).
    """

    def __init__(self) -> None:
        self._chunks: list[IndexedChunk] = []

    def add(self, chunk: IndexedChunk) -> None:
        self._chunks.append(chunk)

    def add_batch(self, chunks: list[IndexedChunk]) -> None:
        self._chunks.extend(chunks)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
    ) -> list[RetrievalResult]:
        """Cosine similarity search."""
        if not self._chunks:
            return []

        results: list[tuple[float, IndexedChunk]] = []
        for chunk in self._chunks:
            score = self._cosine(query_embedding, chunk.embedding)
            results.append((score, chunk))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)

        return [
            RetrievalResult(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                page=chunk.page,
                document_id=chunk.document_id,
                vector_score=score,
                metadata=chunk.metadata,
            )
            for score, chunk in results[:top_k]
        ]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def __len__(self) -> int:
        return len(self._chunks)
