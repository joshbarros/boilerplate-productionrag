"""Fixed chunker unit tests."""

from __future__ import annotations

import uuid

from ragcore.chunking.fixed import FixedChunker


def test_fixed_chunker_respects_size_and_overlap() -> None:
    text = "abcdefghij" * 50  # 500 chars
    pages = [text]
    chunker = FixedChunker(chunk_size=100, chunk_overlap=20)
    chunks = chunker.chunk(text, pages, uuid.uuid4())
    assert len(chunks) >= 5
    assert all(len(c.text) <= 100 for c in chunks)
    assert all(c.metadata["strategy"] == "fixed" for c in chunks)


def test_fixed_chunker_empty_text() -> None:
    chunker = FixedChunker(chunk_size=100, chunk_overlap=10)
    assert chunker.chunk("   ", [], uuid.uuid4()) == []
