"""In-memory budget ledger — per-day spend tracking with dual-cap enforcement.

Two caps are enforced (Constitution VI):
  * daily_budget_usd  — rolling 24-hour wall-clock window per service instance
  * query_budget_usd  — single-query hard ceiling

Token → USD conversion uses OpenRouter public pricing for the default free
model (effectively $0), but the logic is model-agnostic: callers pass the
actual token counts and the ledger applies a per-model rate table with a
conservative fallback rate so that paid-model usage is always tracked.

Rate table (input/output $/1k tokens):
  nvidia/nemotron-*      0.00 / 0.00  (free tier)
  gpt-4o-mini            0.15 / 0.60  (per OpenAI public pricing)
  gpt-4o                 5.00 / 15.00
  claude-*haiku*         0.25 / 1.25
  claude-*sonnet*        3.00 / 15.00
  <fallback>             1.00 / 3.00  (conservative default for unknown models)
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime

# ─── Pricing table ────────────────────────────────────────────────────────────
# Each entry: (input_$/1k_tokens, output_$/1k_tokens)
_RATES: list[tuple[str, float, float]] = [
    ("nvidia/nemotron", 0.0, 0.0),
    ("gpt-4o-mini", 0.00015, 0.0006),
    ("gpt-4o", 0.005, 0.015),
    ("claude-haiku", 0.00025, 0.00125),
    ("claude-sonnet", 0.003, 0.015),
    ("claude-opus", 0.015, 0.075),
    ("mistral", 0.0002, 0.0006),
    ("llama", 0.0, 0.0),
    ("qwen", 0.0, 0.0),
]
_FALLBACK_RATE = (0.001, 0.003)  # $1/$3 per 1M tokens (conservative)


def estimate_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost in USD for a single LLM call.

    Args:
        model: Model identifier string (partial match is fine).
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.

    Returns:
        Estimated cost in USD (may be 0.0 for free models).
    """
    if not model:
        return 0.0
    model_lower = model.lower()
    in_rate, out_rate = _FALLBACK_RATE
    for prefix, ir, or_ in _RATES:
        if prefix in model_lower:
            in_rate, out_rate = ir, or_
            break
    return (prompt_tokens / 1000 * in_rate) + (completion_tokens / 1000 * out_rate)


# ─── Ledger ───────────────────────────────────────────────────────────────────


@dataclass
class QueryCost:
    """Cost record for a single query."""

    prompt_tokens: int
    completion_tokens: int
    embed_tokens: int
    usd: float
    model: str
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))


class BudgetExceededError(Exception):
    """Raised when a budget cap would be breached.

    Attributes:
        kind: ``"daily"`` or ``"query"``
        cap_usd: The applicable limit.
        projected_usd: What the call would cost.
    """

    def __init__(self, kind: str, cap_usd: float, projected_usd: float) -> None:
        self.kind = kind
        self.cap_usd = cap_usd
        self.projected_usd = projected_usd
        super().__init__(
            f"{kind} budget cap ${cap_usd:.4f} would be exceeded "
            f"(projected ${projected_usd:.4f})"
        )


class BudgetLedger:
    """Thread-safe in-memory budget ledger.

    Tracks per-day spending and enforces two caps:
    * query cap  — reject any single call that would cost more than the limit
    * daily cap  — reject calls once the rolling 24-h window is exhausted

    The window resets when the calendar UTC day changes (wall-clock, not
    sliding window — simplest and most auditable).
    """

    def __init__(self, daily_cap_usd: float, query_cap_usd: float) -> None:
        self._daily_cap = daily_cap_usd
        self._query_cap = query_cap_usd
        self._lock = threading.Lock()
        self._day: str = self._today()
        self._consumed: float = 0.0
        self._rejected: int = 0
        self._records: list[QueryCost] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def check(self, estimated_usd: float) -> None:
        """Raise BudgetExceededError if the projected cost would breach any cap.

        Args:
            estimated_usd: Projected cost for the call about to be made.

        Raises:
            BudgetExceededError: On query-cap or daily-cap breach.
        """
        with self._lock:
            self._maybe_reset()
            if estimated_usd > self._query_cap:
                self._rejected += 1
                raise BudgetExceededError("query", self._query_cap, estimated_usd)
            if self._consumed + estimated_usd > self._daily_cap:
                self._rejected += 1
                raise BudgetExceededError("daily", self._daily_cap, estimated_usd)

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        embed_tokens: int = 0,
    ) -> QueryCost:
        """Record actual cost after a successful call and return the record.

        Args:
            model: Model identifier used for the call.
            prompt_tokens: Actual prompt tokens billed.
            completion_tokens: Actual completion tokens billed.
            embed_tokens: Embedding tokens (free for most providers, tracked anyway).

        Returns:
            QueryCost with the computed USD estimate.
        """
        usd = estimate_usd(model, prompt_tokens, completion_tokens)
        entry = QueryCost(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            embed_tokens=embed_tokens,
            usd=usd,
            model=model,
        )
        with self._lock:
            self._maybe_reset()
            self._consumed += usd
            self._records.append(entry)
        return entry

    def snapshot(self) -> dict:
        """Return a point-in-time snapshot of today's ledger state.

        Returns:
            Dict with period, daily_cap_usd, consumed_usd, rejected_count,
            and query_count.
        """
        with self._lock:
            self._maybe_reset()
            return {
                "period": self._day,
                "scope": "daily",
                "daily_cap_usd": self._daily_cap,
                "query_cap_usd": self._query_cap,
                "consumed_usd": round(self._consumed, 6),
                "rejected_count": self._rejected,
                "query_count": len(self._records),
            }

    # ── Internals ─────────────────────────────────────────────────────────────

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d")

    def _maybe_reset(self) -> None:
        """Reset counters when the UTC calendar day changes (caller holds lock)."""
        today = self._today()
        if today != self._day:
            self._day = today
            self._consumed = 0.0
            self._rejected = 0
            self._records = []
