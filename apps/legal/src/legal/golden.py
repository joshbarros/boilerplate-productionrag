"""Legal niche golden set — 8 hand-written Q&A pairs for eval.

Mix of:
- Doctrinal recall (e.g., fair use factors)
- Procedural (e.g., Miranda warning content)
- Out-of-scope refusals (e.g., non-legal questions)

Each case has a `keyword_hint` and `expected_status`. Once a CourtListener
corpus is ingested, the eval runner uses these to score the answers.
"""

from __future__ import annotations

import json
from pathlib import Path

# 6 in-scope, 2 out-of-scope
GOLDEN = [
    {
        "id": "legal-001",
        "question": "What are the four statutory factors courts consider when evaluating a fair use defense under 17 U.S.C. § 107?",
        "expected_status": "answered",
        "keyword_hints": ["purpose", "character", "nature", "amount", "effect", "market"],
        "expected_pages": [0],
    },
    {
        "id": "legal-002",
        "question": "What rights must police inform a suspect of under the Miranda rule?",
        "expected_status": "answered",
        "keyword_hints": ["attorney", "right to remain silent", "lawyer"],
        "expected_pages": [0],
    },
    {
        "id": "legal-003",
        "question": "What is the Chevron doctrine and what did it require courts to do?",
        "expected_status": "answered",
        "keyword_hints": ["deference", "agency", "reasonable", "interpretation"],
        "expected_pages": [0],
    },
    {
        "id": "legal-004",
        "question": "When may police conduct a warrantless search of a vehicle under the Fourth Amendment automobile exception?",
        "expected_status": "answered",
        "keyword_hints": ["probable cause"],
        "expected_pages": [0],
    },
    {
        "id": "legal-005",
        "question": "What is the Lemon test for Establishment Clause violations?",
        "expected_status": "answered",
        "keyword_hints": ["secular", "purpose", "effect", "entanglement"],
        "expected_pages": [0],
    },
    {
        "id": "legal-006",
        "question": "What constitutes a Section 1983 claim?",
        "expected_status": "answered",
        "keyword_hints": ["color of law", "rights", "secured"],
        "expected_pages": [0],
    },
    {
        "id": "legal-oos-001",
        "question": "What is the best recipe for chocolate chip cookies?",
        "expected_status": "not_found",
        "keyword_hints": [],
        "expected_pages": [],
    },
    {
        "id": "legal-oos-002",
        "question": "How do I install Python 3.12 on macOS?",
        "expected_status": "not_found",
        "keyword_hints": [],
        "expected_pages": [],
    },
]


def write_golden(path: str) -> None:
    """Write the golden set to disk in the eval format."""
    data = {"version": "1", "fixture": "legal_courtlistener", "cases": GOLDEN}
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "golden_set.json"
    write_golden(target)
    print(f"Wrote {len(GOLDEN)} cases to {target}")
