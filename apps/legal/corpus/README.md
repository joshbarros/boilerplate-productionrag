# legal/corpus

US case law fetched from the public CourtListener Search API
([Free Law Project](https://free.law/), https://www.courtlistener.com/api/rest/v4/search/).

Each file is a single case formatted as Markdown with a citation block and
the opinion snippet(s) the search returned (up to 500 chars per snippet).

**Files in this directory: seeded by `python -m legal.ingest`.**

## Reproduce

```bash
cd apps/legal
uv run python -m legal.ingest --max-per-query 3 --out ./corpus
```

This runs the default 10 doctrinal queries. For landmark-case-specific
ingestion, pass `--queries "Miranda v Arizona" "Chevron deference" ...`.

## Format

Each file `cl_<cluster_id>_<slug>.md` has:

```markdown
# <Case Name>

**Citation:** <reporter cite>
**Court:** <court>
**Date Filed:** <YYYY-MM-DD>
**Docket Number:** <docket>
**CourtListener Cluster ID:** <id>
**Source:** CourtListener (Free Law Project, open access)

## Opinion Text

### Excerpt 1 (<author>)
<snippet with <mark> tags removed>
```

## Auth (optional)

Set `COURTLISTENER_API_KEY` to raise rate limits from "limited" to
5 req/min, 50 req/hour, 125 req/day. Free account at
https://www.courtlistener.com/profile/api-token/.

## License

Content is from CourtListener's open-access corpus. Free Law Project
distributes case law under terms consistent with the underlying court's
publication (typically public domain for older federal cases, CC terms
for newer collections).
