"""Query model — a user question."""

from __future__ import annotations

import uuid

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ragcore.models.base import Base, TimestampMixin


class Query(Base, TimestampMixin):
    __tablename__ = "queries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    masked_text: Mapped[str] = mapped_column(Text, nullable=False)
    client_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    budget_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    answer: Mapped[Answer | None] = relationship(  # noqa: F821
        back_populates="query", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Query {self.id}>"
