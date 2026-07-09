"""PDF loader — PyMuPDF fast-path for born-digital PDFs (D4).

Scanned / text-sparse PDFs fall back to Docling (OCR + layout analysis)
when ``ocr_enabled=True`` in settings.  The threshold is
``_MIN_CHARS_PER_PAGE``: if the average extracted characters per page is
below that value the document is treated as a scanned image PDF.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import fitz  # PyMuPDF

from ragcore.config import get_settings
from ragcore.obs.otel import stage_span

# Below this average char count per page → treat as scanned
_MIN_CHARS_PER_PAGE: int = 50


@dataclass
class LoadedDocument:
    """Result of loading a PDF file."""

    filename: str
    title: str
    pages: list[str]  # per-page text, index = page number (0-based)
    full_text: str
    page_count: int
    fingerprint: str  # sha256 of file bytes
    extraction_method: str = "digital"  # digital | ocr


def _is_text_sparse(pages: list[str]) -> bool:
    """Return True when the average page text is below the digital threshold."""
    if not pages:
        return True
    avg_chars = sum(len(p.strip()) for p in pages) / len(pages)
    return avg_chars < _MIN_CHARS_PER_PAGE


def _load_with_docling(file_path: str, fingerprint: str) -> LoadedDocument:
    """OCR + layout analysis via Docling for scanned / mixed PDFs.

    Docling is imported lazily so it doesn't slow down startup when OCR
    is not needed.
    """
    from docling.document_converter import DocumentConverter  # noqa: PLC0415

    converter = DocumentConverter()
    conv_result = converter.convert(file_path)
    doc = conv_result.document

    page_count = len(doc.pages)
    # doc.pages keys are 1-indexed integers
    page_texts: dict[int, list[str]] = {pg: [] for pg in doc.pages}

    for item, _ in doc.iterate_items():
        text = getattr(item, "text", None)
        provs = getattr(item, "prov", None)
        if not text or not provs:
            continue
        for prov in provs:
            pg = getattr(prov, "page_no", None)
            if pg is not None and pg in page_texts:
                page_texts[pg].append(text)

    sorted_pages = sorted(page_texts.keys())
    pages = [" ".join(page_texts[pg]) for pg in sorted_pages]
    if not pages:
        pages = [""] * max(page_count, 1)

    full_text = "\n\n".join(pages)
    filename = file_path.split("/")[-1]
    title = getattr(doc, "name", None) or filename

    return LoadedDocument(
        filename=filename,
        title=title,
        pages=pages,
        full_text=full_text,
        page_count=page_count or len(pages),
        fingerprint=fingerprint,
        extraction_method="ocr",
    )


@stage_span("ingest.load_pdf")
def load_pdf(file_path: str) -> LoadedDocument:
    """Load a PDF — fast PyMuPDF path for digital PDFs, Docling for scanned.

    Args:
        file_path: Absolute path to the PDF file.

    Returns:
        LoadedDocument with per-page text, fingerprint, and extraction method.

    Raises:
        ValueError: If the PDF is password-protected or cannot be read.
    """
    # Fingerprint for dedup (FR-006)
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    fingerprint = hashlib.sha256(file_bytes).hexdigest()

    # ── Fast PyMuPDF path ──────────────────────────────────────────────────
    doc = fitz.open(file_path)
    if doc.is_encrypted:
        doc.close()
        raise ValueError(f"Password-protected PDF: {file_path}")

    pages: list[str] = [page.get_text("text") for page in doc]
    full_text = "\n\n".join(pages)
    title = doc.metadata.get("title", "") or file_path.split("/")[-1]
    page_count = len(pages)
    doc.close()

    # ── OCR fallback (Phase 5) ─────────────────────────────────────────────
    settings = get_settings()
    if settings.ocr_enabled and _is_text_sparse(pages):
        return _load_with_docling(file_path, fingerprint)

    return LoadedDocument(
        filename=file_path.split("/")[-1],
        title=title,
        pages=pages,
        full_text=full_text,
        page_count=page_count,
        fingerprint=fingerprint,
        extraction_method="digital",
    )
