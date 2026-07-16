"""Keyword search — in-memory TF (default) + Postgres FTS (postgres backend)."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any

from sqlalchemy import text

from ragcore.obs.otel import stage_span
from ragcore.retrieval.fusion import RetrievalResult
from ragcore.retrieval.vector_pg import IndexedChunk


class InMemoryKeywordSearch:
    """Simple keyword search with TF-based scoring."""

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
        if not self._chunks:
            return []

        query_terms = set(self._tokenize(query))
        if not query_terms:
            return []

        # Crude IDF so rare codes/acronyms outrank common tokens.
        import math

        n_docs = max(len(self._chunks), 1)
        df: Counter[str] = Counter()
        for tokens in self._tokenized:
            df.update(set(tokens))

        results: list[tuple[float, IndexedChunk]] = []
        for tokens, chunk in zip(self._tokenized, self._chunks, strict=False):
            chunk_terms = Counter(tokens)
            score = 0.0
            for term in query_terms:
                if term in chunk_terms:
                    idf = math.log(1.0 + n_docs / (1.0 + df[term]))
                    score += chunk_terms[term] * idf
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
        text = text.lower()
        tokens = re.findall(r"[a-zà-ÿ0-9]{2,}", text)
        return tokens


class PostgresKeywordSearch:
    """Postgres full-text search over the generated ``tsv`` column."""

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def add_batch(self, chunks: list[IndexedChunk]) -> None:
        """No-op: FTS index is maintained by the GENERATED tsv column on insert."""
        return None

    @stage_span("retrieve.fts")
    def search(self, query: str, top_k: int = 8) -> list[RetrievalResult]:
        # plainto_tsquery is safer than raw user input; 'simple' matches the
        # generated column config in migration 0001.
        sess = self._session_factory()
        try:
            rows = sess.execute(
                text(
                    """
                    SELECT c.id, c.text, c.page_start, c.document_id, c.metadata,
                           ts_rank_cd(c.tsv, plainto_tsquery('simple', :q)) AS score,
                           d.title
                    FROM chunks c
                    LEFT JOIN documents d ON d.id = c.document_id
                    WHERE c.tsv @@ plainto_tsquery('simple', :q)
                    ORDER BY score DESC
                    LIMIT :top_k
                    """
                ),
                {"q": query, "top_k": top_k},
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
                        keyword_score=float(row.score or 0.0),
                        metadata=meta,
                    )
                )
            return results
        finally:
            sess.close()
