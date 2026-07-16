"""Chunking package — strategies behind one interface (D5)."""

from ragcore.chunking.base import Chunker, ChunkResult
from ragcore.chunking.fixed import FixedChunker
from ragcore.chunking.recursive import RecursiveChunker
from ragcore.chunking.semantic import SemanticChunker

__all__ = [
    "Chunker",
    "ChunkResult",
    "RecursiveChunker",
    "FixedChunker",
    "SemanticChunker",
]
