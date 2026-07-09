"""Eval run model — one execution of the eval suite."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ragcore.models.base import Base, TimestampMixin


class EvalVerdict(enum.StrEnum):
    PASS = "pass"
    REGRESSION = "regression"


class EvalRun(Base, TimestampMixin):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    git_sha: Mapped[str | None] = mapped_column(String(40), nullable=True)
    config_matrix: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    baseline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id"),
        nullable=True,
    )
    verdict: Mapped[EvalVerdict | None] = mapped_column(
        Enum(EvalVerdict), nullable=True
    )
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<EvalRun {self.id} [{self.verdict}]>"
