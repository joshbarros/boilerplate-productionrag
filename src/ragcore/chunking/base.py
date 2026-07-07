"""Chunker interface — all strategies implement this (D5).

Choice of strategy is an eval outcome, not a default. The interface is
deliberately simple: take a document's text + page map, return chunks.
"""

from __future__ import annotations

import abc
import uuid
from dataclasses import dataclass, field


@dataclass
class ChunkResult:
    """A single chunk produced by a chunker."""

    text: str
    page_start: int
    page_end: int
    metadata: dict = field(default_factory=dict)


class Chunker(abc.ABC):
    """Base interface for all chunking strategies."""

    @abc.abstractmethod
    def chunk(
        self,
        text: str,
        pages: list[str],
        document_id: uuid.UUID,
    ) -> list[ChunkResult]:
        """Split document text into chunks.

        Args:
            text: Full document text (all pages concatenated).
            pages: List of per-page text (index = page number, 0-based).
            document_id: Parent document UUID (for metadata).

        Returns:
            List of ChunkResult objects.
        """
        ...
