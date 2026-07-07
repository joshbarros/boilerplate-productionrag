"""Chunk model — retrievable passage derived from a document."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ragcore.models.base import Base, TimestampMixin


class ChunkingStrategy(enum.StrEnum):
    FIXED = "fixed"
    RECURSIVE = "recursive"
    SEMANTIC = "semantic"


class Chunk(Base, TimestampMixin):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    strategy: Mapped[ChunkingStrategy] = mapped_column(
        Enum(ChunkingStrategy), nullable=False
    )
    page_start: Mapped[int] = mapped_column(Integer, nullable=False)
    page_end: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # tsv is a GENERATED column — created via Alembic migration, not ORM
    # embedding is vector(1536) — created via Alembic migration (pgvector)
    embedding_model: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    document: Mapped[Document] = relationship(  # noqa: F821
        back_populates="chunks"
    )
    citations: Mapped[list[Citation]] = relationship(  # noqa: F821
        back_populates="chunk"
    )

    def __repr__(self) -> str:
        return f"<Chunk {self.id} pp.{self.page_start}-{self.page_end}>"
