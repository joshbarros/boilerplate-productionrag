"""Vector search — in-memory cosine (default) + pgvector HNSW (postgres backend).

The filename is historical: production path uses Postgres + pgvector;
MVP/tests use InMemoryVectorStore so CI never needs a database.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from ragcore.obs.otel import stage_span
from ragcore.retrieval.fusion import RetrievalResult


@dataclass
class IndexedChunk:
    """In-memory / transport chunk with embedding."""

    chunk_id: str
    text: str
    page: int
    document_id: str
    embedding: list[float]
    metadata: dict = field(default_factory=dict)
    embedding_model: str = ""


class MixedModelError(ValueError):
    """Raised when query embedding model does not match indexed chunks (D6)."""


class InMemoryVectorStore:
    """Simple in-memory vector store with cosine similarity."""

    def __init__(self) -> None:
        self._chunks: list[IndexedChunk] = []
        self._model_id: str | None = None

    def add(self, chunk: IndexedChunk) -> None:
        model = chunk.embedding_model or chunk.metadata.get("embedding_model", "")
        if self._model_id is None and model:
            self._model_id = model
        elif model and self._model_id and model != self._model_id:
            raise MixedModelError(
                f"Cannot mix embedding models: store={self._model_id}, chunk={model}"
            )
        self._chunks.append(chunk)

    def add_batch(self, chunks: list[IndexedChunk]) -> None:
        for chunk in chunks:
            self.add(chunk)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        query_model: str | None = None,
    ) -> list[RetrievalResult]:
        if not self._chunks:
            return []
        if query_model and self._model_id and query_model != self._model_id:
            raise MixedModelError(
                f"Query model {query_model!r} != index model {self._model_id!r}"
            )

        results: list[tuple[float, IndexedChunk]] = []
        for chunk in self._chunks:
            score = self._cosine(query_embedding, chunk.embedding)
            results.append((score, chunk))

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
        if len(a) != len(b):
            # Pad/truncate for mismatched dims (shouldn't happen in prod)
            n = min(len(a), len(b))
            a, b = a[:n], b[:n]
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def __len__(self) -> int:
        return len(self._chunks)


class PostgresVectorStore:
    """pgvector cosine search over the chunks table."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def add_batch(
        self,
        chunks: list[IndexedChunk],
        session: Session | None = None,
    ) -> None:
        """Insert indexed chunks. Caller owns the document row and transaction."""
        own = session is None
        sess = session or self._session_factory()
        try:
            for chunk in chunks:
                emb = chunk.embedding
                # Pad/truncate to 1536 for text-embedding-3-small schema
                if len(emb) < 1536:
                    emb = emb + [0.0] * (1536 - len(emb))
                elif len(emb) > 1536:
                    emb = emb[:1536]
                emb_literal = "[" + ",".join(str(float(x)) for x in emb) + "]"
                meta = dict(chunk.metadata)
                model = chunk.embedding_model or meta.get("embedding_model", "unknown")
                sess.execute(
                    text(
                        """
                        INSERT INTO chunks (
                            id, document_id, strategy, page_start, page_end,
                            text, embedding_model, metadata, embedding
                        ) VALUES (
                            :id, :document_id, :strategy, :page_start, :page_end,
                            :text, :embedding_model, CAST(:metadata AS jsonb),
                            CAST(:embedding AS vector)
                        )
                        """
                    ),
                    {
                        "id": chunk.chunk_id,
                        "document_id": chunk.document_id,
                        "strategy": meta.get("strategy", "recursive"),
                        "page_start": chunk.page,
                        "page_end": chunk.page,
                        "text": chunk.text,
                        "embedding_model": model,
                        "metadata": __import__("json").dumps(meta),
                        "embedding": emb_literal,
                    },
                )
            if own:
                sess.commit()
        except Exception:
            if own:
                sess.rollback()
            raise
        finally:
            if own:
                sess.close()

    @stage_span("retrieve.vector_pg")
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        query_model: str | None = None,
    ) -> list[RetrievalResult]:
        emb = query_embedding
        if len(emb) < 1536:
            emb = emb + [0.0] * (1536 - len(emb))
        elif len(emb) > 1536:
            emb = emb[:1536]
        emb_literal = "[" + ",".join(str(float(x)) for x in emb) + "]"

        sess = self._session_factory()
        try:
            # Mixed-model guard (D6)
            if query_model:
                other = sess.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM chunks
                        WHERE embedding_model IS DISTINCT FROM :model
                        """
                    ),
                    {"model": query_model},
                ).scalar()
                same = sess.execute(
                    text(
                        "SELECT COUNT(*) FROM chunks WHERE embedding_model = :model"
                    ),
                    {"model": query_model},
                ).scalar()
                if other and same:
                    raise MixedModelError(
                        "Corpus has mixed embedding models; "
                        f"query model={query_model!r}"
                    )
                if other and not same:
                    raise MixedModelError(
                        f"No chunks indexed with model {query_model!r}"
                    )

            rows = sess.execute(
                text(
                    """
                    SELECT c.id, c.text, c.page_start, c.document_id, c.metadata,
                           1 - (c.embedding <=> CAST(:emb AS vector)) AS score,
                           d.title
                    FROM chunks c
                    LEFT JOIN documents d ON d.id = c.document_id
                    WHERE c.embedding IS NOT NULL
                      AND (:model IS NULL OR c.embedding_model = :model)
                    ORDER BY c.embedding <=> CAST(:emb AS vector)
                    LIMIT :top_k
                    """
                ),
                {
                    "emb": emb_literal,
                    "top_k": top_k,
                    "model": query_model,
                },
            ).fetchall()

            results: list[RetrievalResult] = []
            for row in rows:
                meta = row.metadata or {}
                if isinstance(meta, str):
                    import json

                    meta = json.loads(meta)
                meta = dict(meta)
                if row.title:
                    meta.setdefault("title", row.title)
                results.append(
                    RetrievalResult(
                        chunk_id=str(row.id),
                        text=row.text,
                        page=int(row.page_start),
                        document_id=str(row.document_id),
                        vector_score=float(row.score or 0.0),
                        metadata=meta,
                    )
                )
            return results
        finally:
            sess.close()

    def count(self) -> int:
        sess = self._session_factory()
        try:
            return int(sess.execute(text("SELECT COUNT(*) FROM chunks")).scalar() or 0)
        finally:
            sess.close()


def parse_uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)
