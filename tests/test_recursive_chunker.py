from __future__ import annotations

import uuid

from ragcore.chunking.recursive import RecursiveChunker


def test_split_text_last_resort_uses_fixed_char_windows() -> None:
    chunker = RecursiveChunker(chunk_size=1000, chunk_overlap=200)
    text = "a" * 2500

    splits = chunker._split_text(text, [""])

    assert len(splits) == 3
    assert [len(s) for s in splits] == [1000, 1000, 500]


def test_chunk_outputs_metadata_and_valid_page_range() -> None:
    chunker = RecursiveChunker(chunk_size=60, chunk_overlap=10)
    page1 = "LangChain intro. " * 8
    page2 = "Vector retrieval details. " * 8
    full = page1 + "\n\n" + page2

    chunks = chunker.chunk(full, [page1, page2], uuid.uuid4())

    assert len(chunks) > 1
    for c in chunks:
        assert c.text
        assert c.metadata["strategy"] == "recursive"
        assert isinstance(c.metadata["document_id"], str)
        assert 0 <= c.page_start <= c.page_end <= 1
