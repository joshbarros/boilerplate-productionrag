# Test Fixtures

Fixture PDFs for integration tests and eval suite.

## Requirements (Constitution: no third-party corpus content)

All fixtures must be **owner-generated or public domain**. No real regulatory
documents, no copyrighted material, no PII.

## Planned fixture set (T009 — 20 PDFs)

| # | Type | Language | Purpose |
|---|---|---|---|
| 1–5 | Clean digital PT-BR fiscal | pt | Codes, acronyms, exact identifiers |
| 6–8 | Clean digital EN regulatory | en | Cross-language retrieval |
| 9–12 | Table-heavy layouts | pt | Docling table extraction |
| 13–16 | Scanned pages (image PDFs) | pt | OCR path (Tesseract por+eng) |
| 17–18 | Mixed-layout (headers + tables + prose) | mixed | Layout-aware parsing |
| 19 | Corrupted / truncated | — | Graceful failure (US2-AS3) |
| 20 | Password-protected | — | Rejection with actionable error |

## Provenance

Each fixture PDF must have its source documented here when added.
