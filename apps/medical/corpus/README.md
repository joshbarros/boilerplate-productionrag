# medical/corpus

PubMed Central open-access articles fetched via E-utilities (`medical/pubmed.py`).
Each file is a single article formatted as Markdown with a frontmatter-style header
and the abstract body.

**Files in this directory: 48 PMIDs** (sourced from `medical/ingest.py` queries).

## Reproduce

```bash
cd apps/medical
uv run python -m medical.ingest --max-per-query 3 --out ./corpus
```

This runs the default 10 queries (~3 requests/sec, no API key). To target
specific topics, pass `--queries "metformin first-line" "statin mechanism" ...`.

## Format

Each file `pmid_<id>.md` has the structure:

```markdown
# <Article Title>

**Authors:** <Last, Last, +N more>
**Journal:** <journal> (<year>)
**PMID:** <pmid>
**Source:** PubMed Central (open access)

## Abstract

<abstract text>
```

## License

All content is from PubMed Central open-access articles. License per article
follows PubMed's PMC OA terms (typically CC BY / CC BY-NC).
