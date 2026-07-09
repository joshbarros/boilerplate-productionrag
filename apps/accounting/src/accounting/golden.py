"""Accounting niche golden set — 8 hand-written Q&A pairs for eval.

Mix of:
- Accounting standards (ASC 606, ASC 842)
- Standard financial concepts (COGS, goodwill)
- Out-of-scope refusals (e.g., non-accounting questions)

Each case has a `keyword_hint` and `expected_status`. Once a 10-K corpus
is ingested, the eval runner uses these to score the answers.
"""

from __future__ import annotations

import json
from pathlib import Path

# 6 in-scope, 2 out-of-scope
GOLDEN = [
    {
        "id": "acct-001",
        "question": "What is the five-step model for revenue recognition under ASC 606?",
        "expected_status": "answered",
        "keyword_hints": ["contract", "performance", "obligation", "transaction", "price"],
        "expected_pages": [0],
    },
    {
        "id": "acct-002",
        "question": "How should a lessee recognize a right-of-use asset and lease liability under ASC 842?",
        "expected_status": "answered",
        "keyword_hints": ["right-of-use", "lease liability", "present value"],
        "expected_pages": [0],
    },
    {
        "id": "acct-003",
        "question": "When should goodwill be tested for impairment?",
        "expected_status": "answered",
        "keyword_hints": ["annual", "reporting unit", "fair value"],
        "expected_pages": [0],
    },
    {
        "id": "acct-004",
        "question": "How is cost of goods sold (COGS) typically classified on the income statement?",
        "expected_status": "answered",
        "keyword_hints": ["cost", "sales", "revenue", "expense"],
        "expected_pages": [0],
    },
    {
        "id": "acct-005",
        "question": "What is the difference between accounts receivable and the allowance for doubtful accounts?",
        "expected_status": "answered",
        "keyword_hints": ["receivable", "allowance", "doubtful", "expected"],
        "expected_pages": [0],
    },
    {
        "id": "acct-006",
        "question": "How are deferred tax assets recognized on the balance sheet?",
        "expected_status": "answered",
        "keyword_hints": ["deferred", "tax", "temporary", "difference"],
        "expected_pages": [0],
    },
    {
        "id": "acct-oos-001",
        "question": "What is the best recipe for chocolate chip cookies?",
        "expected_status": "not_found",
        "keyword_hints": [],
        "expected_pages": [],
    },
    {
        "id": "acct-oos-002",
        "question": "How do I install Python 3.12 on macOS?",
        "expected_status": "not_found",
        "keyword_hints": [],
        "expected_pages": [],
    },
]


def write_golden(path: str) -> None:
    """Write the golden set to disk in the eval format."""
    data = {"version": "1", "fixture": "accounting_edgar", "cases": GOLDEN}
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "golden_set.json"
    write_golden(target)
    print(f"Wrote {len(GOLDEN)} cases to {target}")
