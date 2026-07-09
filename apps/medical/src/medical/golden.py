"""Medical niche golden set — 8 hand-written Q&A pairs for eval.

Mix of:
- Factual recall (e.g., mechanism of metformin)
- Clinical comparison (e.g., first-line for X)
- Out-of-scope refusals (e.g., legal advice)

Each case has a `keyword_hint` and `expected_status`. Once a PubMed
corpus is ingested, the eval runner uses these to score the answers.
"""

from __future__ import annotations

import json
from pathlib import Path

# 6 in-scope, 2 out-of-scope
GOLDEN = [
    {
        "id": "med-001",
        "question": "What is the first-line pharmacological treatment for type 2 diabetes?",
        "expected_status": "answered",
        "keyword_hints": ["metformin"],
        "expected_pages": [0],
    },
    {
        "id": "med-002",
        "question": "What class of drug is metformin?",
        "expected_status": "answered",
        "keyword_hints": ["biguanide"],
        "expected_pages": [0],
    },
    {
        "id": "med-003",
        "question": "What is the mechanism of action of statins?",
        "expected_status": "answered",
        "keyword_hints": ["HMG-CoA reductase"],
        "expected_pages": [0],
    },
    {
        "id": "med-004",
        "question": "What are the most common side effects of ACE inhibitors?",
        "expected_status": "answered",
        "keyword_hints": ["cough"],
        "expected_pages": [0],
    },
    {
        "id": "med-005",
        "question": "What is the recommended treatment for bacterial meningitis?",
        "expected_status": "answered",
        "keyword_hints": ["antibiotics", "ceftriaxone"],
        "expected_pages": [0],
    },
    {
        "id": "med-006",
        "question": "How does the mRNA COVID-19 vaccine work?",
        "expected_status": "answered",
        "keyword_hints": ["spike", "protein"],
        "expected_pages": [0],
    },
    {
        "id": "med-oos-001",
        "question": "What are the side effects of the latest Apple iPhone?",
        "expected_status": "not_found",
        "keyword_hints": [],
        "expected_pages": [],
    },
    {
        "id": "med-oos-002",
        "question": "Should I sue my landlord for not fixing the heater?",
        "expected_status": "not_found",
        "keyword_hints": [],
        "expected_pages": [],
    },
]


def write_golden(path: str) -> None:
    """Write the golden set to disk in the eval format."""
    data = {"version": "1", "fixture": "medical_pubmed", "cases": GOLDEN}
    Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import sys

    target = sys.argv[1] if len(sys.argv) > 1 else "golden_set.json"
    write_golden(target)
    print(f"Wrote {len(GOLDEN)} cases to {target}")
