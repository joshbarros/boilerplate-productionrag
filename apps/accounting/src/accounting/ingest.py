"""Accounting niche ingestion script.

Usage:
    cd apps/accounting
    uv run python -m accounting.ingest --queries "revenue recognition" "ASC 606" \\
        --out ./corpus

Each query → EDGAR full-text search → fetch filing → save markdown to <out>/.
"""

from __future__ import annotations

import argparse

from accounting.edgar import fetch_and_save


# Mix of accounting standards + topic queries
DEFAULT_QUERIES = [
    # Revenue recognition (ASC 606)
    "revenue recognition",
    "ASC 606 five step model",
    # Lease accounting (ASC 842)
    "lease accounting right of use asset",
    # Goodwill / impairment
    "goodwill impairment test",
    # Revenue / income statement basics
    "cost of goods sold",
    "operating expenses",
    # Balance sheet items
    "accounts receivable allowance",
    "inventory valuation",
    # Tax
    "deferred tax assets",
    "uncertain tax positions",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest EDGAR filings into the accounting corpus")
    parser.add_argument("--queries", nargs="*", help="Search queries (space-separated)")
    parser.add_argument("--out", default="./corpus", help="Output directory for .md files")
    parser.add_argument("--max-per-query", type=int, default=3, help="Max results per query")
    parser.add_argument(
        "--forms",
        default="10-K",
        help="Form types (10-K, 10-Q, 8-K, comma-separated)",
    )
    args = parser.parse_args()

    queries = args.queries or DEFAULT_QUERIES
    forms = args.forms
    print(f"Ingesting {len(queries)} queries (forms={forms}) → {args.out}")

    total = 0
    for q in queries:
        print(f"  • {q}…", end="", flush=True)
        try:
            paths = fetch_and_save(q, args.out, forms=forms, max_results=args.max_per_query)
        except Exception as e:  # noqa: BLE001
            print(f" ERROR: {e}")
            continue
        print(f" {len(paths)} filings")
        total += len(paths)

    print(f"\nDone. {total} filings saved to {args.out}/")


if __name__ == "__main__":
    main()
