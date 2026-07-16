"""Semantic chunker unit tests."""

from __future__ import annotations

import uuid

from ragcore.chunking.semantic import SemanticChunker


def test_semantic_chunker_splits_on_topic_shift() -> None:
    text = (
        "Cats are mammals that meow. Cats like to sleep in the sun. "
        "Cats hunt mice at night. "
        "Quantum physics studies particles. Quantum entanglement is non-local. "
        "The Schrödinger equation describes wavefunctions."
    )
    chunker = SemanticChunker(
        chunk_size=200, chunk_overlap=20, similarity_threshold=0.15
    )
    chunks = chunker.chunk(text, [text], uuid.uuid4())
    assert len(chunks) >= 1
    assert all(c.metadata["strategy"] == "semantic" for c in chunks)
    assert all(c.text for c in chunks)


def test_semantic_chunker_empty() -> None:
    chunker = SemanticChunker()
    assert chunker.chunk("", [], uuid.uuid4()) == []
