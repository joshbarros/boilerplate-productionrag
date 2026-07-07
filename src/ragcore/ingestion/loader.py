"""PDF loader — PyMuPDF fast-path for born-digital PDFs (D4).

Full Docling path (with OCR, tables, layout) is Phase 5 (T027).
For now, this is enough to load fixture PDFs and demo US1.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import fitz  # PyMuPDF

from ragcore.obs.otel import stage_span


@dataclass
class LoadedDocument:
    """Result of loading a PDF file."""

    filename: str
    title: str
    pages: list[str]  # per-page text, index = page number (0-based)
    full_text: str
    page_count: int
    fingerprint: str  # sha256 of file bytes
    extraction_method: str = "digital"  # digital | ocr | mixed


@stage_span("ingest.load_pdf")
def load_pdf(file_path: str) -> LoadedDocument:
    """Load a PDF file and extract text per page using PyMuPDF.

    Args:
        file_path: Path to the PDF file.

    Returns:
        LoadedDocument with per-page text and file fingerprint.

    Raises:
        ValueError: If the file cannot be read or is not a valid PDF.
    """
    # Compute fingerprint for dedup (FR-006)
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    fingerprint = hashlib.sha256(file_bytes).hexdigest()

    doc = fitz.open(file_path)
    if doc.is_encrypted:
        doc.close()
        raise ValueError(f"Password-protected PDF: {file_path}")

    pages: list[str] = []
    for page in doc:
        text = page.get_text("text")
        pages.append(text)

    full_text = "\n\n".join(pages)
    title = doc.metadata.get("title", "") or file_path.split("/")[-1]

    result = LoadedDocument(
        filename=file_path.split("/")[-1],
        title=title,
        pages=pages,
        full_text=full_text,
        page_count=len(pages),
        fingerprint=fingerprint,
        extraction_method="digital",
    )

    doc.close()
    return result
