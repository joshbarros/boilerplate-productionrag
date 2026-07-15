"""Qdrant vector backend — benchmark / alternate serving arm (T044).

Collection ``chunks`` (or ``chunks_bench`` when used as dual-write) stores
payload: text, page, document_id, embedding_model, metadata, title.
"""

from __future__ import annotations

import uuid
from typing import Any

from ragcore.obs.otel import stage_span
from ragcore.retrieval.fusion import RetrievalResult
from ragcore.retrieval.vector_pg import IndexedChunk, MixedModelError


class QdrantVectorStore:
    """Thin wrapper around the Qdrant client (cosine / named vector)."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        *,
        collection: str = "chunks",
        vector_size: int = 1536,
        client: Any | None = None,
    ) -> None:
        self._url = url
        self._collection = collection
        self._vector_size = vector_size
        self._client = client
        self._ensured = False

    def _get_client(self) -> Any:
        if self._client is None:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(url=self._url, prefer_grpc=False)
        return self._client

    def ensure_collection(self) -> None:
        if self._ensured:
            return
        from qdrant_client.http import models as qm

        client = self._get_client()
        names = {c.name for c in client.get_collections().collections}
        if self._collection not in names:
            client.create_collection(
                collection_name=self._collection,
                vectors_config=qm.VectorParams(
                    size=self._vector_size,
                    distance=qm.Distance.COSINE,
                ),
            )
        self._ensured = True

    def add_batch(self, chunks: list[IndexedChunk]) -> None:
        if not chunks:
            return
        from qdrant_client.http import models as qm

        self.ensure_collection()
        client = self._get_client()
        points = []
        for chunk in chunks:
            emb = list(chunk.embedding)
            if len(emb) < self._vector_size:
                emb = emb + [0.0] * (self._vector_size - len(emb))
            elif len(emb) > self._vector_size:
                emb = emb[: self._vector_size]
            model = chunk.embedding_model or chunk.metadata.get(
                "embedding_model", "unknown"
            )
            points.append(
                qm.PointStruct(
                    id=str(uuid.UUID(chunk.chunk_id))
                    if _is_uuid(chunk.chunk_id)
                    else str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                    vector=emb,
                    payload={
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text,
                        "page": chunk.page,
                        "document_id": chunk.document_id,
                        "embedding_model": model,
                        "title": chunk.metadata.get("title", ""),
                        "metadata": chunk.metadata,
                    },
                )
            )
        client.upsert(collection_name=self._collection, points=points)

    @stage_span("retrieve.vector_qdrant")
    def search(
        self,
        query_embedding: list[float],
        top_k: int = 8,
        *,
        query_model: str | None = None,
    ) -> list[RetrievalResult]:
        from qdrant_client.http import models as qm

        self.ensure_collection()
        client = self._get_client()
        emb = list(query_embedding)
        if len(emb) < self._vector_size:
            emb = emb + [0.0] * (self._vector_size - len(emb))
        elif len(emb) > self._vector_size:
            emb = emb[: self._vector_size]

        query_filter = None
        if query_model:
            query_filter = qm.Filter(
                must=[
                    qm.FieldCondition(
                        key="embedding_model",
                        match=qm.MatchValue(value=query_model),
                    )
                ]
            )

        # qdrant-client ≥1.12 prefers query_points; fall back to search.
        try:
            resp = client.query_points(
                collection_name=self._collection,
                query=emb,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )
            hits = resp.points
        except Exception:
            hits = client.search(
                collection_name=self._collection,
                query_vector=emb,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )

        # Mixed-model guard: if filter returns empty but collection has points
        # under another model, raise.
        if query_model and not hits:
            count = client.count(collection_name=self._collection, exact=True).count
            if count > 0:
                # Check whether other models exist
                sample = client.scroll(
                    collection_name=self._collection, limit=1, with_payload=True
                )[0]
                if sample:
                    other = (sample[0].payload or {}).get("embedding_model")
                    if other and other != query_model:
                        raise MixedModelError(
                            f"No chunks for model {query_model!r} "
                            f"(found {other!r})"
                        )

        results: list[RetrievalResult] = []
        for h in hits:
            payload = h.payload or {}
            meta = dict(payload.get("metadata") or {})
            if payload.get("title"):
                meta.setdefault("title", payload["title"])
            results.append(
                RetrievalResult(
                    chunk_id=str(payload.get("chunk_id") or h.id),
                    text=str(payload.get("text") or ""),
                    page=int(payload.get("page") or 0),
                    document_id=str(payload.get("document_id") or ""),
                    vector_score=float(h.score or 0.0),
                    metadata=meta,
                )
            )
        return results

    def count(self) -> int:
        self.ensure_collection()
        return int(
            self._get_client()
            .count(collection_name=self._collection, exact=True)
            .count
        )

    def recreate(self) -> None:
        """Drop and recreate collection (eval matrix isolation)."""
        from qdrant_client.http import models as qm

        client = self._get_client()
        names = {c.name for c in client.get_collections().collections}
        if self._collection in names:
            client.delete_collection(self._collection)
        client.create_collection(
            collection_name=self._collection,
            vectors_config=qm.VectorParams(
                size=self._vector_size,
                distance=qm.Distance.COSINE,
            ),
        )
        self._ensured = True


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
