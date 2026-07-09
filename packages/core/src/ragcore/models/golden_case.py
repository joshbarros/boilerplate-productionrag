"""Golden case model — eval dataset entry (also versioned as golden.yaml)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ragcore.models.base import Base, TimestampMixin


class GoldenCaseStatus(enum.StrEnum):
    ACTIVE = "active"
    DISPUTED = "disputed"
    EXCLUDED = "excluded"


class GoldenCase(Base, TimestampMixin):
    __tablename__ = "golden_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    expected_document_fingerprint: Mapped[str] = mapped_column(
        Text, nullable=False, index=True
    )
    expected_pages: Mapped[list[int]] = mapped_column(
        ARRAY(Integer), nullable=False
    )
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="pt")
    answerable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    status: Mapped[GoldenCaseStatus] = mapped_column(
        Enum(GoldenCaseStatus),
        nullable=False,
        default=GoldenCaseStatus.ACTIVE,
    )
    audit_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<GoldenCase {self.id} [{self.status}]>"
