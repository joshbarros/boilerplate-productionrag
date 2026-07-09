"""Medical niche ingestion script.

Usage:
    cd apps/medical
    uv run python -m medical.ingest --queries "metformin diabetes" "statin cholesterol" \\
        --out ./corpus

Each query → PubMed search → fetch → write markdown to <out>/.
Then start the API and ingest those files via the core's RAG service.
"""

from __future__ import annotations

import argparse

from medical.pubmed import fetch_and_save


DEFAULT_QUERIES = [
    "metformin type 2 diabetes",
    "statin cholesterol HMG-CoA",
    "ACE inhibitor cough side effects",
    "bacterial meningitis ceftriaxone treatment",
    "mRNA COVID-19 vaccine mechanism",
    "aspirin cardiovascular",
    "hypertension first-line treatment",
    "atrial fibrillation anticoagulation",
    "sepsis bundle care",
    "antibiotic resistance stewardship",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PubMed articles into the medical corpus")
    parser.add_argument("--queries", nargs="*", help="Search queries (space-separated)")
    parser.add_argument("--out", default="./corpus", help="Output directory for .md files")
    parser.add_argument("--max-per-query", type=int, default=5, help="Max results per query")
    args = parser.parse_args()

    queries = args.queries or DEFAULT_QUERIES
    print(f"Ingesting {len(queries)} queries → {args.out}")

    total = 0
    for q in queries:
        print(f"  • {q}…", end="", flush=True)
        paths = fetch_and_save(q, args.out, max_results=args.max_per_query)
        print(f" {len(paths)} articles")
        total += len(paths)

    print(f"\nDone. {total} articles saved to {args.out}/")


if __name__ == "__main__":
    main()
