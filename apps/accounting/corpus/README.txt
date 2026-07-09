# accounting/corpus

US public-company filings fetched from the public SEC EDGAR
full-text search API (https://efts.sec.gov/LATEST/search-index).

Each file is a single filing formatted as Markdown with a metadata
block (filer, CIK, form, period, accession) and the filing's HTML
text (up to 20k chars) stripped to plain text.

**Files in this directory: seeded by `python -m accounting.ingest`.**

## Reproduce

```bash
cd apps/accounting
uv run python -m accounting.ingest --max-per-query 3 --out ./corpus
```

This runs the default 10 accounting queries (ASC 606, ASC 842,
goodwill, COGS, etc.) and fetches the top 3 results per query.
Form type defaults to 10-K (annual reports); pass `--forms 10-K,10-Q`
to mix in quarterly reports.

## Auth (none required)

EDGAR full-text search and the Archives endpoint do not require an
API key. SEC does ask that automated tools include a User-Agent with
contact info — set `SEC_EDGAR_EMAIL=you@example.com` in `.env` for
polite operation. Rate limit: 10 req/sec.

## Format

Each file `edgar_<accession>_<slug>.md` has:

```markdown
# <Filer Name> — <Form Type>

<filing text, up to 20k chars>

---

**Filer:** ...
**CIK:** ...
**Form Type:** ...
**Period Ending:** <YYYY-MM-DD>
**File Date:** <YYYY-MM-DD>
**Accession Number:** <accession>
**SIC Code:** ...
**File Number:** ...
**State of Incorporation:** ...
**Business State:** ...
**Source:** SEC EDGAR (https://www.sec.gov)
```

## License

Filings are public SEC disclosures. Company-authored text retains the
copyright of the filer; fair use applies for research, education, and
news reporting.
