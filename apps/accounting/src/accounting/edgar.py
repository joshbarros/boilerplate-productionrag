"""SEC EDGAR fetcher — US public-company filings (Free public API).

Two endpoints used:

1. **Full-text search** (EFTS): https://efts.sec.gov/LATEST/search-index
   - Returns ranked filings matching a query string
   - No auth required, but must set a User-Agent with contact email
   - Rate limit: 10 req/sec
   - Each result has _id like "0001493152-24-021380:ex23-1.htm"
     pointing to the actual filing in EDGAR Archives

2. **Filing archives**: https://www.sec.gov/Archives/edgar/data/{cik}/{accession}.htm
   - The actual filing document (HTML)
   - For ingestion we use the filing INDEX which lists all files
   - INDEX URL: https://www.sec.gov/Archives/edgar/data/{cik}/{accession-no-dashes}/{accession}-index.htm

For the niche we focus on 10-K (annual) and 10-Q (quarterly) filings.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request


EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
TOOL = "production-rag-accounting"
EMAIL = os.getenv("SEC_EDGAR_EMAIL", "anonymous@example.com")  # SEC requires contact
API_KEY = os.getenv("SEC_EDGAR_API_KEY", "")


def _throttle() -> None:
    """SEC asks for 10 req/sec max."""
    time.sleep(0.12 if not API_KEY else 0.1)


def _get(url: str, *, raw: bool = False) -> bytes:
    """GET with timeout, error handling, and required User-Agent.

    SEC requires 'Sample Company Name AdminContact@<domain>' format.
    Handles gzip transparently (SEC serves gzipped by default).
    """
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": f"{TOOL} {EMAIL}",
            "Accept-Encoding": "gzip, deflate",
            "Host": urllib.parse.urlparse(url).netloc,
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw_bytes = resp.read()
    # If gzipped, decompress
    if raw_bytes[:2] == b"\x1f\x8b":
        import gzip
        raw_bytes = gzip.decompress(raw_bytes)
    if raw:
        return raw_bytes
    return json.loads(raw_bytes.decode("utf-8"))


def _strip_html(text: str) -> str:
    """HTML stripper for EDGAR filing text — strips XBRL/HTML and keeps prose.

    10-K filings from EDGAR contain:
    - Inline XBRL metadata (`ix:hidden`, `ix:references`, etc.) → numbers/IDs
    - `script`/`style` blocks → CSS/JS
    - HTML tables → financial statement data (numeric, useful but not narrative)
    - HTML body text → the actual readable 10-K narrative

    For a RAG corpus over a niche, we want the NARRATIVE text (Item 1, Item 7,
    risk factors, accounting policies, etc.), not raw XBRL/HTML tables.
    """
    if not text:
        return ""
    # remove inline XBRL hidden blocks (these contain XBRL-tagged numbers
    # in spans that don't render visually but bloat the text)
    text = re.sub(r"<ix:hidden[^>]*>.*?</ix:hidden>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # remove script/style blocks
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # remove HTML comments (XBRL often has <!-- ... --> with metadata)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    # strip standalone XBRL schema URLs and namespace declarations
    text = re.sub(r"https?://(www\.)?fasb\.org/[^\s]+", " ", text)
    text = re.sub(r"https?://(www\.)?xbrl\.org/[^\s]+", " ", text)
    # remove tags (keep text content; tables become flat)
    text = re.sub(r"<[^>]+>", " ", text)
    # decode entities
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&#x27;", "'")
        .replace("&#x2F;", "/")
    )
    # collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def search(query: str, *, forms: str = "10-K", max_results: int = 10) -> list[dict]:
    """Full-text search EDGAR. Returns ranking results.

    Each result: {id, score, source: {ciks, display_names, file_date,
                                       file_type, form, adsh, ...}}
    """
    params = {
        "q": f'"{query}"',
        "forms": forms,
        "dateRange": "custom",
        "startdt": "2023-01-01",
        "enddt": "2024-12-31",
    }
    url = f"{EFTS_URL}?{urllib.parse.urlencode(params)}"
    _throttle()
    data = _get(url)
    hits = data.get("hits", {}).get("hits", [])
    return hits[:max_results]


def get_filing_index(adsh: str, ciks: list[str]) -> list[dict]:
    """Fetch the filing's index.json (file list for the accession).

    Returns a list of {name, type, size} dicts. Use this to find the
    main 10-K/10-Q document (typically named like `<ticker>-<date>.htm`)
    rather than the exhibit the search result points to.
    """
    acc_clean = adsh.replace("-", "")
    cik = ciks[0].lstrip("0") or "0"
    index_url = f"{ARCHIVES_URL}/{cik}/{acc_clean}/index.json"
    _throttle()
    try:
        data = _get(index_url)
    except urllib.error.HTTPError:
        return []
    items = data.get("directory", {}).get("item", [])
    return items


def find_main_filing_filename(items: list[dict], form: str) -> str | None:
    """Pick the main 10-K/10-Q document from the index.

    Heuristics:
    - Exclude exhibits (ex-*.htm, ex_*.htm, ex*.htm)
    - Exclude XBRL/data files (R*.htm, *_htm.xml, *.xsd, etc.)
    - Prefer .htm files
    - Pick the LARGEST remaining (the main filing body is usually 2-10MB,
      while R*.htm fragments and exhibits are <500KB)
    """
    if not items:
        return None
    # Filter to .htm candidates, excluding exhibits and XBRL reports
    candidates = [
        i for i in items
        if i.get("name", "").endswith(".htm")
        and not re.search(r"(?:^|/)(?:ex[-_]|R\d+\.htm)", i.get("name", ""))
    ]
    if not candidates:
        return None
    # Pick the largest (main filing body is several MB; R-fragments are <100KB)
    candidates.sort(key=lambda i: int(i.get("size", "0") or "0"), reverse=True)
    return candidates[0].get("name")


def get_filing_text(adsh: str, ciks: list[str], file_type: str) -> str:
    """Fetch the actual filing HTML and extract readable text.

    adsh: accession like '0001493152-24-021380' (no dashes, but we accept either)
    ciks: list of CIK strings like ['0001493152']
    file_type: e.g. 'ex23-1.htm', 'form10-k.htm' (used as fallback only)

    Strategy: fetch the index.json to find the main 10-K document. If
    the index is unavailable, fall back to the file_type from the
    search result (which often points to an exhibit).
    """
    # First try to find the main document via the index
    items = get_filing_index(adsh, ciks)
    main_name = find_main_filing_filename(items, form="10-K")
    if main_name:
        return _fetch_filing_html(adsh, ciks, main_name)

    # Fall back to the search result's file_type (often an exhibit)
    if file_type:
        return _fetch_filing_html(adsh, ciks, file_type)

    return f"(No filing documents found for {adsh})"


def _fetch_filing_html(adsh: str, ciks: list[str], file_name: str) -> str:
    """Internal: fetch a single document from the filing archive."""
    acc_clean = adsh.replace("-", "")
    cik = ciks[0].lstrip("0") or "0"
    filing_url = f"{ARCHIVES_URL}/{cik}/{acc_clean}/{file_name}"
    _throttle()
    try:
        raw = _get(filing_url, raw=True).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return f"(Could not fetch {file_name}: HTTP {e.code})"
    return _strip_html(raw)[:200000]  # cap at 200k chars (full 10-K narrative)


def to_markdown(result: dict, full_text: str | None = None) -> str:
    """Render an EDGAR search result as a Markdown document for ingestion.

    Opinion-first layout: the substantive filing text comes first, the
    metadata comes last (separated by ---). This keeps the first chunk
    from being dominated by metadata.
    """
    src = result.get("_source", {})
    ciks = src.get("ciks", ["?"])
    display = src.get("display_names", ["Unknown Filer"])
    form = src.get("form", "?")
    file_type = src.get("file_type", "?")
    file_date = src.get("file_date", "?")
    period_ending = src.get("period_ending", "?")
    adsh = src.get("adsh", "?")
    sic = src.get("sics", ["?"])
    file_num = src.get("file_num", ["?"])
    inc_state = src.get("inc_states", ["?"])
    biz_state = src.get("biz_states", ["?"])

    filer = display[0] if display else "Unknown Filer"

    body = []
    body.append(f"# {filer} — {form}")
    body.append("")
    if full_text:
        body.append(full_text)
        body.append("")
    else:
        body.append("(Filing text not fetched — see accession below)")
        body.append("")

    body.append("---")
    body.append("")
    body.append(f"**Filer:** {filer}")
    body.append(f"**CIK:** {ciks[0] if ciks else '?'}")
    body.append(f"**Form Type:** {form}")
    body.append(f"**File Type:** {file_type}")
    body.append(f"**Period Ending:** {period_ending}")
    body.append(f"**File Date:** {file_date}")
    body.append(f"**Accession Number:** {adsh}")
    body.append(f"**SIC Code:** {sic[0] if sic else '?'}")
    body.append(f"**File Number:** {file_num[0] if file_num else '?'}")
    body.append(f"**State of Incorporation:** {inc_state[0] if inc_state else '?'}")
    body.append(f"**Business State:** {biz_state[0] if biz_state else '?'}")
    body.append(f"**Source:** SEC EDGAR (https://www.sec.gov)")

    return "\n".join(body)


def fetch_and_save(query: str, out_dir: str, *, forms: str = "10-K", max_results: int = 5) -> list[str]:
    """Search → fetch → save each result as a .md file.

    Returns the list of saved file paths.
    """
    import pathlib

    pathlib.Path(out_dir).mkdir(parents=True, exist_ok=True)
    results = search(query, forms=forms, max_results=max_results)
    paths: list[str] = []
    for r in results:
        src = r.get("_source", {})
        adsh = src.get("adsh", "")
        ciks = src.get("ciks", [])
        file_type = src.get("file_type", "")
        if not (adsh and ciks and file_type):
            continue

        # Slug from filer name
        display = src.get("display_names", ["filing"])
        slug = re.sub(r"[^a-z0-9]+", "_", (display[0] or "filing").lower())[:50].strip("_")
        acc = adsh.replace("-", "")
        fname = f"edgar_{acc}_{slug}.md"
        path = pathlib.Path(out_dir) / fname

        full_text = get_filing_text(adsh, ciks, file_type)
        try:
            path.write_text(to_markdown(r, full_text=full_text), encoding="utf-8")
            paths.append(str(path))
        except Exception as e:  # noqa: BLE001
            print(f"  ! failed to write {fname}: {e}")
    return paths


if __name__ == "__main__":
    import sys

    q = " ".join(sys.argv[1:]) or "revenue recognition"
    paths = fetch_and_save(q, "./corpus", max_results=3)
    print(f"Q: {q}")
    print(f"Saved {len(paths)} filings to ./corpus/")
