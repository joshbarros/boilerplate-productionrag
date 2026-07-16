"""Qdrant vector store unit tests (mocked client — no live Qdrant)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ragcore.retrieval.vector_pg import IndexedChunk, MixedModelError
from ragcore.retrieval.vector_qdrant import QdrantVectorStore


def _chunk(cid: str, emb: list[float], model: str = "m1") -> IndexedChunk:
    return IndexedChunk(
        chunk_id=cid,
        text=f"text for {cid}",
        page=0,
        document_id="doc-1",
        embedding=emb,
        metadata={"title": "T", "embedding_model": model},
        embedding_model=model,
    )


def test_add_batch_upserts_points() -> None:
    client = MagicMock()
    client.get_collections.return_value = SimpleNamespace(collections=[])
    store = QdrantVectorStore(
        url="http://localhost:6333",
        collection="test",
        vector_size=3,
        client=client,
    )
    store.add_batch(
        [
            _chunk("00000000-0000-0000-0000-000000000001", [1.0, 0.0, 0.0]),
            _chunk("00000000-0000-0000-0000-000000000002", [0.0, 1.0, 0.0]),
        ]
    )
    client.create_collection.assert_called_once()
    client.upsert.assert_called_once()
    args = client.upsert.call_args
    assert args.kwargs["collection_name"] == "test"
    assert len(args.kwargs["points"]) == 2


def test_search_maps_payload() -> None:
    client = MagicMock()
    client.get_collections.return_value = SimpleNamespace(
        collections=[SimpleNamespace(name="test")]
    )
    hit = SimpleNamespace(
        id="1",
        score=0.91,
        payload={
            "chunk_id": "c1",
            "text": "hello world",
            "page": 2,
            "document_id": "d1",
            "title": "Doc",
            "metadata": {},
            "embedding_model": "m1",
        },
    )
    client.query_points.return_value = SimpleNamespace(points=[hit])
    store = QdrantVectorStore(
        collection="test", vector_size=3, client=client
    )
    store._ensured = True
    results = store.search([1.0, 0.0, 0.0], top_k=3, query_model="m1")
    assert len(results) == 1
    assert results[0].chunk_id == "c1"
    assert results[0].page == 2
    assert results[0].vector_score == pytest.approx(0.91)


def test_search_mixed_model_raises() -> None:
    client = MagicMock()
    client.get_collections.return_value = SimpleNamespace(
        collections=[SimpleNamespace(name="test")]
    )
    client.query_points.side_effect = Exception("force legacy")
    client.search.return_value = []
    client.count.return_value = SimpleNamespace(count=1)
    other = SimpleNamespace(
        payload={"embedding_model": "other-model"}
    )
    client.scroll.return_value = ([other], None)
    store = QdrantVectorStore(collection="test", vector_size=3, client=client)
    store._ensured = True
    with pytest.raises(MixedModelError):
        store.search([0.0, 1.0, 0.0], top_k=1, query_model="m1")
