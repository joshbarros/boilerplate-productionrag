"""Recursive character chunker — v1 default strategy (D5).

Splits text hierarchically by separators (\\n\\n → \\n → . → space),
trying to keep semantically coherent blocks together. This is the
LangChain RecursiveCharacterTextSplitter approach, reimplemented
framework-light (Constitution VII).
"""

from __future__ import annotations

import re
import uuid

from ragcore.chunking.base import Chunker, ChunkResult
from ragcore.obs.otel import stage_span

# Separator hierarchy: try larger blocks first, fall back to smaller
_SEPARATORS: list[str] = ["\n\n\n", "\n\n", "\n", ". ", " ", ""]


class RecursiveChunker(Chunker):
    """Recursive character splitter with configurable chunk size and overlap."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @stage_span("chunk.recursive")
    def chunk(
        self,
        text: str,
        pages: list[str],
        document_id: uuid.UUID,
    ) -> list[ChunkResult]:
        # Split text using the separator hierarchy
        splits = self._split_text(text, _SEPARATORS)

        # Merge splits into chunks respecting chunk_size + overlap
        chunks: list[ChunkResult] = []
        current: list[str] = []
        current_len = 0

        for split in splits:
            split_len = len(split)
            if current_len + split_len > self.chunk_size and current:
                # Flush current chunk
                chunk_text = "".join(current)
                page_range = self._find_pages(chunk_text, pages)
                chunks.append(
                    ChunkResult(
                        text=chunk_text.strip(),
                        page_start=page_range[0],
                        page_end=page_range[1],
                        metadata={
                            "strategy": "recursive",
                            "document_id": str(document_id),
                        },
                    )
                )
                # Keep overlap: carry last N chars
                overlap_text = (
                    chunk_text[-self.chunk_overlap :]
                    if self.chunk_overlap > 0
                    else ""
                )
                current = [overlap_text] if overlap_text else []
                current_len = len(overlap_text)

            current.append(split)
            current_len += split_len

        # Flush remaining
        if current:
            chunk_text = "".join(current)
            page_range = self._find_pages(chunk_text, pages)
            chunks.append(
                ChunkResult(
                    text=chunk_text.strip(),
                    page_start=page_range[0],
                    page_end=page_range[1],
                    metadata={"strategy": "recursive", "document_id": str(document_id)},
                )
            )

        return chunks

    def _split_text(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text using the separator hierarchy."""
        if not text:
            return []

        # If text is small enough, return it as-is
        if len(text) <= self.chunk_size:
            return [text]

        if not separators:
            return [text]

        separator = separators[0]
        if separator == "":
            # Last resort: split by character chunks
            return [
                text[i : i + self.chunk_size]
                for i in range(0, len(text), self.chunk_size)
            ]

        # Split by current separator
        parts = text.split(separator)
        parts = [p for p in parts if p.strip()]

        if len(parts) <= 1:
            # This separator didn't help — try next
            return self._split_text(text, separators[1:])

        # Recursively split each part with remaining separators
        result: list[str] = []
        for part in parts:
            if len(part) > self.chunk_size:
                sub_splits = self._split_text(part, separators[1:])
                result.extend(sub_splits)
            else:
                result.append(part)

        return result

    def _find_pages(self, chunk_text: str, pages: list[str]) -> tuple[int, int]:
        """Find which pages this chunk spans by matching text against page content."""
        if not pages:
            return 0, 0

        # Use first 50 non-whitespace chars as a fingerprint
        fingerprint = re.sub(r"\s+", " ", chunk_text).strip()[:50]
        if not fingerprint:
            return 0, 0

        start_page = 0
        end_page = 0
        found_start = False

        for i, page_text in enumerate(pages):
            page_clean = re.sub(r"\s+", " ", page_text).strip()
            if fingerprint[:30] in page_clean:
                start_page = i
                end_page = i
                found_start = True
                break

        if not found_start:
            return 0, max(0, len(pages) - 1)

        # Find end page by checking last chars
        end_fingerprint = re.sub(r"\s+", " ", chunk_text).strip()[-30:]
        for i in range(start_page, len(pages)):
            page_clean = re.sub(r"\s+", " ", pages[i]).strip()
            if end_fingerprint in page_clean:
                end_page = i

        return start_page, end_page
