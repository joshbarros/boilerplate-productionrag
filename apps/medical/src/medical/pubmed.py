"""PubMed Central fetcher — open-access biomedical literature.

Uses the E-utilities API (free, no auth) at eutils.ncbi.nlm.nih.gov.

API reference: https://www.ncbi.nlm.nih.gov/books/NBK25500/

Rate limit: 3 requests/sec without an API key. We self-throttle to 1/sec
to be polite. For higher throughput, register an API key at
https://www.ncbi.nlm.nih.gov/account/settings/ and pass it via the
NCBI_API_KEY env var.
"""

from __future__ import annotations

import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PubMedArticle:
    """A single PubMed Central article, simplified for ingestion."""

    pmid: str
    title: str
    abstract: str
    authors: list[str]
    journal: str
    year: str


EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "production-rag-medical"
EMAIL = os.getenv("NCBI_EMAIL", "anonymous@example.com")  # NCBI requires contact
API_KEY = os.getenv("NCBI_API_KEY", "")


def _throttle() -> None:
    """Sleep to stay under 3 req/sec (polite, no key)."""
    time.sleep(1.1 if not API_KEY else 0.34)


def _get(url: str) -> bytes:
    """GET with timeout + error handling."""
    req = urllib.request.Request(url, headers={"User-Agent": f"{TOOL}/{EMAIL}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def search(query: str, max_results: int = 10) -> list[str]:
    """Search PubMed for `query`, return list of PMIDs."""
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": str(max_results),
        "retmode": "json",
        "tool": TOOL,
        "email": EMAIL,
    }
    if API_KEY:
        params["api_key"] = API_KEY
    url = f"{EUTILS}/esearch.fcgi?{urllib.parse.urlencode(params)}"
    _throttle()
    data = json.loads(_get(url).decode("utf-8"))
    return data.get("esearchresult", {}).get("idlist", [])


def fetch(pmids: list[str]) -> list[PubMedArticle]:
    """Fetch full metadata for a list of PMIDs (efetch)."""
    if not pmids:
        return []
    params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "retmode": "xml",
        "tool": TOOL,
        "email": EMAIL,
    }
    if API_KEY:
        params["api_key"] = API_KEY
    url = f"{EUTILS}/efetch.fcgi?{urllib.parse.urlencode(params)}"
    _throttle()
    body = _get(url).decode("utf-8")

    # Parse PubMed's XML
    root = ET.fromstring(body)
    articles: list[PubMedArticle] = []
    for art in root.findall(".//PubmedArticle"):
        pmid_el = art.find(".//PMID")
        title_el = art.find(".//ArticleTitle")
        abst_el = art.find(".//Abstract/AbstractText")
        journal_el = art.find(".//Journal/Title")
        year_el = art.find(".//PubDate/Year")
        author_els = art.findall(".//AuthorList/Author/LastName")

        articles.append(
            PubMedArticle(
                pmid=pmid_el.text if pmid_el is not None else "",
                title=(title_el.text or "").strip() if title_el is not None else "",
                abstract=abst_el.text or "" if abst_el is not None else "",
                authors=[a.text or "" for a in author_els if a.text],
                journal=journal_el.text or "" if journal_el is not None else "",
                year=year_el.text or "" if year_el is not None else "",
            )
        )
    return articles


def to_markdown(article: PubMedArticle) -> str:
    """Render an article as a Markdown document for ingestion."""
    authors = ", ".join(article.authors[:5])
    if len(article.authors) > 5:
        authors += f", +{len(article.authors) - 5} more"
    body = f"""# {article.title}

**Authors:** {authors}
**Journal:** {article.journal} ({article.year})
**PMID:** {article.pmid}
**Source:** PubMed Central (open access)

## Abstract

{article.abstract}
"""
    return body


def fetch_and_save(query: str, out_dir: str, max_results: int = 10) -> list[Path]:
    """Search + fetch + save to `out_dir/*.md`. Returns the list of paths."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    pmids = search(query, max_results=max_results)
    if not pmids:
        return []
    articles = fetch(pmids)
    paths: list[Path] = []
    for art in articles:
        if not art.title or not art.abstract:
            continue
        path = Path(out_dir) / f"pmid_{art.pmid}.md"
        path.write_text(to_markdown(art), encoding="utf-8")
        paths.append(path)
    return paths


# json import kept local — _get returns raw bytes
import json  # noqa: E402
