"""CourtListener fetcher — open US case law (Free Law Project).

Uses the public CourtListener Search API v4 (https://www.courtlistener.com/api/rest/v4/search/).
No auth required for default rate limits; token recommended for production.

API: GET /api/rest/v4/search/?q=<query>&type=o
- type=o → case law opinion clusters
- Each result has: caseName, citation, court, dateFiled, opinions[].snippet
- snippet is up to 500 chars with <mark> highlights around matches
- Rate limits (no token): limited; with token: 5/min, 50/hr, 125/day
"""

from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request


SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
TOOL = "production-rag-legal"
TOKEN = os.getenv("COURTLISTENER_API_KEY", "")  # optional but recommended


def _throttle() -> None:
    """CourtListener is polite. Without a token: keep it light.

    Unauth rate limit is ~1 req/sec. With a token it's 5/min, 50/hr,
    125/day — still slow. 3s is a safe default.
    """
    time.sleep(3.0 if not TOKEN else 0.5)


def _get(url: str) -> dict:
    """GET with timeout, error handling, and optional auth."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"{TOOL} (https://github.com/joshbarros/boilerplate-productionrag)",
            "Accept": "application/json",
        },
    )
    if TOKEN:
        req.add_header("Authorization", f"Token {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_mark(text: str) -> str:
    """CourtListener snippets use <mark>...</mark> for highlights."""
    if not text:
        return ""
    # remove <mark>/</mark> tags but keep inner text
    cleaned = re.sub(r"</?mark>", "", text)
    return html.unescape(cleaned).strip()


def search(query: str, max_results: int = 10) -> list[dict]:
    """Search case law, return list of result dicts with caseName, snippet, etc."""
    params = {
        "q": query,
        "type": "o",  # opinion clusters
        "order_by": "score desc",
        "highlight": "on",
    }
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
    _throttle()
    data = _get(url)
    return data.get("results", [])[:max_results]


def to_markdown(result: dict, full_text: str | None = None) -> str:
    """Render a CourtListener result as a Markdown document for ingestion.

    Layout is opinion-first, metadata-last. This matters for the
    chunker: the recursive chunker splits on \\n\\n, so we want
    the substantive opinion text to land in the FIRST chunk, not
    the metadata header. The legal domain cares about the opinion
    body; the citation block is reference material.

    full_text: optional richer text fetched separately (e.g., opinion
    plain_text from a follow-up call). If provided, it is used as the
    primary body and the snippets are dropped.
    """
    case_name = result.get("caseName", "Unknown Case")
    citations = result.get("citation", [])
    cite_str = "; ".join(citations) if citations else "n/a"
    court = result.get("court", "Unknown Court")
    date = result.get("dateFiled", "Unknown Date")
    cluster_id = result.get("cluster_id", "?")
    docket = result.get("docketNumber", "n/a")

    # Build the body
    body_parts: list[str] = []

    if full_text:
        # Fetched separately — use it verbatim
        body_parts.append(f"# {case_name}")
        body_parts.append("")
        body_parts.append(full_text.strip())
        body_parts.append("")
    else:
        # Fall back to snippets. Combine all opinion snippets into one
        # continuous block so the chunker doesn't split them across chunks.
        snippets: list[str] = []
        for op in result.get("opinions", []):
            text = _strip_mark(op.get("snippet", ""))
            if text:
                snippets.append(text)
        body_parts.append(f"# {case_name}")
        body_parts.append("")
        if snippets:
            body_parts.append("\n\n".join(snippets))
            body_parts.append("")
        else:
            body_parts.append("(no opinion text available)")
            body_parts.append("")

    # Metadata at the end — won't be in the primary retrieval chunks
    body_parts.append("---")
    body_parts.append("")
    body_parts.append(f"**Citation:** {cite_str}")
    body_parts.append(f"**Court:** {court}")
    body_parts.append(f"**Date Filed:** {date}")
    body_parts.append(f"**Docket Number:** {docket}")
    body_parts.append(f"**CourtListener Cluster ID:** {cluster_id}")
    body_parts.append(f"**Source:** CourtListener (Free Law Project, open access)")

    return "\n".join(body_parts)


def fetch_and_save(query: str, out_dir: str, max_results: int = 10) -> list[str]:
    """Search → save each result as a .md file. Returns the list of paths."""
    import pathlib

    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    results = search(query, max_results=max_results)
    paths: list[str] = []
    for r in results:
        cluster_id = r.get("cluster_id")
        if cluster_id is None:
            continue
        slug = re.sub(r"[^a-z0-9]+", "_", (r.get("caseName") or "case").lower())[:50].strip("_")
        fname = f"cl_{cluster_id}_{slug}.md"
        path = pathlib.Path(out_dir) / fname
        try:
            path.write_text(to_markdown(r), encoding="utf-8")
            paths.append(str(path))
        except Exception as e:  # noqa: BLE001
            print(f"  ! failed to write {fname}: {e}")
    return paths


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "fair use copyright"
    paths = fetch_and_save(q, "./corpus", max_results=5)
    print(f"Q: {q}")
    print(f"Saved {len(paths)} cases to ./corpus/")
