"""Security gate — rate limit, injection heuristics, PII masking (FR-014/015)."""

from ragcore.security.injection import InjectionBlockedError, check_injection
from ragcore.security.pii import mask_pii
from ragcore.security.rate_limit import (
    RateLimiter,
    RateLimitExceeded,
    RateLimitExceededError,
)

__all__ = [
    "check_injection",
    "InjectionBlockedError",
    "mask_pii",
    "RateLimiter",
    "RateLimitExceeded",
    "RateLimitExceededError",
]
