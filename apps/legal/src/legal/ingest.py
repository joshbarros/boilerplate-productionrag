"""Legal niche ingestion script.

Usage:
    cd apps/legal
    uv run python -m legal.ingest --queries "fair use copyright" "Miranda rights" \\
        --out ./corpus

Each query → CourtListener search → save markdown to <out>/.
Then start the API and ingest those files via the core's RAG service.
"""

from __future__ import annotations

import argparse

from legal.courtlistener import fetch_and_save


# Mix of landmark cases + doctrinal queries
DEFAULT_QUERIES = [
    "fair use copyright 17 USC 107",
    "Miranda v Arizona warning rights",
    "Chevron deference agency interpretation",
    "qualified immunity police excessive force",
    "Fourth Amendment unreasonable search",
    "Lemon test establishment clause",
    "due process procedural",
    "antitrust Sherman Act rule of reason",
    "Title VII disparate impact employment discrimination",
    "patent obviousness Alice",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest CourtListener cases into the legal corpus")
    parser.add_argument("--queries", nargs="*", help="Search queries (space-separated)")
    parser.add_argument("--out", default="./corpus", help="Output directory for .md files")
    parser.add_argument("--max-per-query", type=int, default=3, help="Max results per query")
    args = parser.parse_args()

    queries = args.queries or DEFAULT_QUERIES
    print(f"Ingesting {len(queries)} queries → {args.out}")

    total = 0
    for q in queries:
        print(f"  • {q}…", end="", flush=True)
        paths = fetch_and_save(q, args.out, max_results=args.max_per_query)
        print(f" {len(paths)} cases")
        total += len(paths)

    print(f"\nDone. {total} cases saved to {args.out}/")


if __name__ == "__main__":
    main()
