"""Prompt-injection heuristics — block OWASP LLM01-style patterns (FR-014)."""

from __future__ import annotations

import re

# Conservative pattern set: high precision, medium recall. Over-blocking is
# preferred to leaking system prompts; false positives can be relaxed later.
_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"you\s+are\s+now\s+(dan|jailbroken|unrestricted)",
        r"system\s*prompt\s*:",
        r"<\s*/?\s*system\s*>",
        r"reveal\s+(your|the)\s+(system\s+)?prompt",
        r"print\s+(your|the)\s+(hidden\s+)?instructions",
        r"override\s+(safety|guardrails|policy)",
        r"do\s+not\s+follow\s+(the\s+)?(document|passages|rules)",
        r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions",
    )
]


class InjectionBlockedError(Exception):
    """Raised when a query matches an injection heuristic."""

    def __init__(self, reason: str = "prompt_injection") -> None:
        self.reason = reason
        super().__init__(reason)


def check_injection(text: str) -> None:
    """Raise InjectionBlockedError if ``text`` matches a blocked pattern."""
    if not text:
        return
    for pat in _PATTERNS:
        if pat.search(text):
            raise InjectionBlockedError(f"blocked_pattern:{pat.pattern[:40]}")
