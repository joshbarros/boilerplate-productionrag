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
    """CourtListener is polite. Without a token: keep it light."""
    time.sleep(2.0 if not TOKEN else 0.5)


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


def to_markdown(result: dict) -> str:
    """Render a CourtListener result as a Markdown document for ingestion."""
    case_name = result.get("caseName", "Unknown Case")
    citations = result.get("citation", [])
    cite_str = "; ".join(citations) if citations else "n/a"
    court = result.get("court", "Unknown Court")
    date = result.get("dateFiled", "Unknown Date")
    cluster_id = result.get("cluster_id", "?")
    docket = result.get("docketNumber", "n/a")

    # collect all opinion snippets (the substantive content)
    opinions = result.get("opinions", [])
    body_parts = [
        f"# {case_name}",
        "",
        f"**Citation:** {cite_str}",
        f"**Court:** {court}",
        f"**Date Filed:** {date}",
        f"**Docket Number:** {docket}",
        f"**CourtListener Cluster ID:** {cluster_id}",
        f"**Source:** CourtListener (Free Law Project, open access)",
        "",
        "## Opinion Text",
        "",
    ]
    for i, op in enumerate(opinions, 1):
        snippet = _strip_mark(op.get("snippet", ""))
        if not snippet:
            continue
        author = op.get("author_str") or "Court"
        body_parts.append(f"### Excerpt {i} ({author})")
        body_parts.append("")
        body_parts.append(snippet)
        body_parts.append("")

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
