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
# Use case names when possible — the free CourtListener search ranks
# case-name matches higher than doctrinal keyword matches.
DEFAULT_QUERIES = [
    # Fair use
    "Campbell v Acuff-Rose Music fair use parody",
    "fair use copyright 17 USC 107 four factors",
    "Authors Guild v Google book scanning fair use",
    # Miranda
    "Miranda v Arizona 384 US 436 warning rights",
    "Miranda rights Fifth Amendment self-incrimination",
    "Edwards v Arizona right to counsel",
    # Chevron
    "Chevron U.S.A. v Natural Resources Defense Council 1984",
    "Chevron deference agency interpretation reasonable",
    "Auer v Robbins agency interpretation",
    # 4A
    "Carroll v United States automobile exception probable cause",
    "Fourth Amendment unreasonable search vehicle",
    "Terry v Ohio stop and frisk",
    # Lemon
    "Lemon v Kurtzman establishment clause three prongs",
    "Lemon test secular purpose entanglement",
    "Wallace v Jaffree establishment clause",
    # 1983
    "Monell v Department Social Services 1983",
    "42 USC 1983 color of law",
    "Section 1983 municipal liability",
    # Other doctrines
    "Sherman Act rule of reason antitrust",
    "Alice Corp v CLS Bank patent abstract idea",
    "Title VII disparate impact employment",
    "due process procedural fourteenth amendment",
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
