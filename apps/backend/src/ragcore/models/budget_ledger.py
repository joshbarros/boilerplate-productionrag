"""Budget ledger model — per-query and per-day cost tracking."""

from __future__ import annotations

import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, Integer, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ragcore.models.base import Base, TimestampMixin


class BudgetScope(enum.StrEnum):
    QUERY = "query"
    DAY = "day"


class BudgetLedger(Base, TimestampMixin):
    __tablename__ = "budget_ledger"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scope: Mapped[BudgetScope] = mapped_column(
        Enum(BudgetScope), nullable=False
    )
    cap_usd: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    consumed_usd: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, default=0
    )
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"<BudgetLedger {self.period} [{self.scope}] "
            f"${self.consumed_usd}/${self.cap_usd}>"
        )
