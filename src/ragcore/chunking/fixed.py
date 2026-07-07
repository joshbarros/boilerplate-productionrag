"""Fixed-size chunker — stub (implemented in Phase 7 / T042)."""

from __future__ import annotations

import uuid

from ragcore.chunking.base import Chunker, ChunkResult


class FixedChunker(Chunker):
    """Fixed-size character chunker — not yet implemented (Phase 7, T042)."""

    def chunk(
        self,
        text: str,
        pages: list[str],
        document_id: uuid.UUID,
    ) -> list[ChunkResult]:
        raise NotImplementedError("FixedChunker is implemented in Phase 7 (T042)")
