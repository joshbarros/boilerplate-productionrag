"""Answer model — the system's response to a query."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ragcore.models.base import Base, TimestampMixin


class AnswerStatus(enum.StrEnum):
    ANSWERED = "answered"
    NOT_FOUND = "not_found"
    REJECTED_BUDGET = "rejected_budget"
    REJECTED_SECURITY = "rejected_security"
    DEGRADED = "degraded"


class Answer(Base, TimestampMixin):
    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    query_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("queries.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status: Mapped[AnswerStatus] = mapped_column(
        Enum(AnswerStatus), nullable=False
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    query: Mapped[Query] = relationship(back_populates="answer")  # noqa: F821
    citations: Mapped[list[Citation]] = relationship(  # noqa: F821
        back_populates="answer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Answer {self.id} [{self.status}]>"
