"""Fixed-size character chunker — sliding windows with overlap (D5 / T042)."""

from __future__ import annotations

import re
import uuid

from ragcore.chunking.base import Chunker, ChunkResult
from ragcore.obs.otel import stage_span


class FixedChunker(Chunker):
    """Fixed-size character splitter with configurable chunk size and overlap."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be in [0, chunk_size)")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @stage_span("chunk.fixed")
    def chunk(
        self,
        text: str,
        pages: list[str],
        document_id: uuid.UUID,
    ) -> list[ChunkResult]:
        if not text or not text.strip():
            return []

        step = self.chunk_size - self.chunk_overlap
        chunks: list[ChunkResult] = []
        for start in range(0, len(text), step):
            end = min(start + self.chunk_size, len(text))
            piece = text[start:end]
            if not piece.strip():
                if end >= len(text):
                    break
                continue
            page_start, page_end = self._find_pages(piece, pages)
            chunks.append(
                ChunkResult(
                    text=piece.strip(),
                    page_start=page_start,
                    page_end=page_end,
                    metadata={
                        "strategy": "fixed",
                        "document_id": str(document_id),
                        "char_start": start,
                        "char_end": end,
                    },
                )
            )
            if end >= len(text):
                break
        return chunks

    def _find_pages(self, chunk_text: str, pages: list[str]) -> tuple[int, int]:
        if not pages:
            return 0, 0
        fingerprint = re.sub(r"\s+", " ", chunk_text).strip()[:50]
        if not fingerprint:
            return 0, 0
        for i, page_text in enumerate(pages):
            page_clean = re.sub(r"\s+", " ", page_text).strip()
            if fingerprint[:30] in page_clean:
                return i, i
        return 0, max(0, len(pages) - 1)
