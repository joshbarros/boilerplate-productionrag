"""Response cache model — content-hash keyed answer cache."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ragcore.models.base import Base, TimestampMixin


class ResponseCache(Base, TimestampMixin):
    __tablename__ = "response_cache"

    key: Mapped[str] = mapped_column(
        String(64), primary_key=True  # sha256 hex digest
    )
    answer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("answers.id", ondelete="CASCADE"),
        nullable=False,
    )
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ttl: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<ResponseCache {self.key[:16]}… hits={self.hits}>"
