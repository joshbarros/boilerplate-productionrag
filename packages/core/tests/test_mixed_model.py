"""Mixed-model embedding guard (D6)."""

from __future__ import annotations

import pytest

from ragcore.retrieval.vector_pg import (
    IndexedChunk,
    InMemoryVectorStore,
    MixedModelError,
)


def test_inmemory_refuses_mixed_models() -> None:
    store = InMemoryVectorStore()
    store.add(
        IndexedChunk(
            chunk_id="1",
            text="a",
            page=0,
            document_id="d",
            embedding=[1.0, 0.0],
            embedding_model="model-a",
        )
    )
    with pytest.raises(MixedModelError):
        store.add(
            IndexedChunk(
                chunk_id="2",
                text="b",
                page=0,
                document_id="d",
                embedding=[0.0, 1.0],
                embedding_model="model-b",
            )
        )


def test_search_refuses_wrong_query_model() -> None:
    store = InMemoryVectorStore()
    store.add(
        IndexedChunk(
            chunk_id="1",
            text="a",
            page=0,
            document_id="d",
            embedding=[1.0, 0.0],
            embedding_model="model-a",
        )
    )
    with pytest.raises(MixedModelError):
        store.search([1.0, 0.0], top_k=1, query_model="model-b")
