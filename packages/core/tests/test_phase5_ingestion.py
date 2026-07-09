"""Phase 5 ingestion tests: OCR fallback, ingest_batch, document_status."""

from __future__ import annotations

import uuid
from pathlib import Path

import fitz  # PyMuPDF
import pytest

import ragcore.ingestion.loader as loader_mod
from ragcore.ingestion.loader import LoadedDocument, _is_text_sparse, load_pdf
from ragcore.service import RagService

# ─── PDF fixtures ─────────────────────────────────────────────────────────────


def _make_digital_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    # Use enough text to stay well above the _MIN_CHARS_PER_PAGE threshold (50).
    page.insert_text(
        (72, 72),
        "LangChain is a framework for building LLM applications with "
        "retrieval-augmented generation, chains, agents, and document loaders.",
    )
    doc.save(str(path))
    doc.close()


def _make_scanned_pdf(path: Path) -> None:
    """Blank page — no text layer, simulates a scanned image PDF."""
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path))
    doc.close()


class FakeEmbedder:
    model_id = "fake/embedding-model"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]


# ─── _is_text_sparse ──────────────────────────────────────────────────────────


def test_is_text_sparse_false_for_rich_pages() -> None:
    pages = ["This page has lots of text about LangChain and embeddings." * 3]
    assert _is_text_sparse(pages) is False


def test_is_text_sparse_true_for_blank_pages() -> None:
    assert _is_text_sparse([""]) is True
    assert _is_text_sparse(["   "]) is True


def test_is_text_sparse_true_when_avg_below_threshold() -> None:
    pages = ["a" * 30, ""]  # avg 15 chars → below 50
    assert _is_text_sparse(pages) is True


def test_is_text_sparse_true_for_empty_list() -> None:
    assert _is_text_sparse([]) is True


# ─── load_pdf digital path ────────────────────────────────────────────────────


def test_digital_pdf_uses_pymupdf(tmp_path: Path) -> None:
    pdf = tmp_path / "digital.pdf"
    _make_digital_pdf(pdf)
    result = load_pdf(str(pdf))
    assert result.extraction_method == "digital"
    assert len(result.pages) == 1
    assert "LangChain" in result.full_text
    assert len(result.fingerprint) == 64  # sha256 hex


# ─── load_pdf OCR path ────────────────────────────────────────────────────────


def test_scanned_pdf_triggers_ocr_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Blank PDF → text-sparse → OCR path (Docling mocked)."""
    pdf = tmp_path / "scanned.pdf"
    _make_scanned_pdf(pdf)

    fake_doc = LoadedDocument(
        filename="scanned.pdf",
        title="scanned.pdf",
        pages=["OCR extracted text from page one."],
        full_text="OCR extracted text from page one.",
        page_count=1,
        fingerprint="fake-fingerprint",
        extraction_method="ocr",
    )
    monkeypatch.setattr(loader_mod, "_load_with_docling", lambda fp, fpr: fake_doc)

    result = load_pdf(str(pdf))
    assert result.extraction_method == "ocr"
    assert "OCR extracted text" in result.full_text


def test_ocr_disabled_skips_docling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ocr_enabled=False, sparse PDFs stay on the digital path."""

    class _FakeSettings:
        ocr_enabled = False

    monkeypatch.setattr(loader_mod, "get_settings", lambda: _FakeSettings())

    docling_called: list[int] = []
    monkeypatch.setattr(
        loader_mod, "_load_with_docling", lambda *a: docling_called.append(1)
    )

    pdf = tmp_path / "blank.pdf"
    _make_scanned_pdf(pdf)
    result = load_pdf(str(pdf))

    assert docling_called == []
    assert result.extraction_method == "digital"


def test_digital_pdf_with_ocr_enabled_skips_docling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rich-text digital PDF must NOT trigger Docling even if ocr_enabled."""
    docling_called: list[int] = []
    monkeypatch.setattr(
        loader_mod, "_load_with_docling", lambda *a: docling_called.append(1)
    )

    pdf = tmp_path / "rich.pdf"
    _make_digital_pdf(pdf)
    result = load_pdf(str(pdf))

    assert docling_called == []
    assert result.extraction_method == "digital"


# ─── ingest_batch ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_batch_two_documents(tmp_path: Path) -> None:
    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]

    pdf1 = tmp_path / "doc1.pdf"
    pdf2 = tmp_path / "doc2.pdf"
    _make_digital_pdf(pdf1)
    _make_digital_pdf(pdf2)

    results = await svc.ingest_batch([str(pdf1), str(pdf2)])

    assert len(results) == 2
    assert results[0].status == "succeeded"
    assert results[1].status == "succeeded"
    assert results[0].page_count == 1
    assert results[1].page_count == 1


@pytest.mark.asyncio
async def test_ingest_batch_duplicate_returns_duplicate_status(
    tmp_path: Path,
) -> None:
    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]

    pdf = tmp_path / "dup.pdf"
    _make_digital_pdf(pdf)

    results = await svc.ingest_batch([str(pdf), str(pdf)])

    assert results[0].status == "succeeded"
    assert results[1].status == "duplicate"


@pytest.mark.asyncio
async def test_ingest_batch_partial_failure(tmp_path: Path) -> None:
    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]

    pdf = tmp_path / "good.pdf"
    _make_digital_pdf(pdf)
    bad_path = str(tmp_path / "nonexistent.pdf")

    results = await svc.ingest_batch([str(pdf), bad_path])

    assert results[0].status == "succeeded"
    assert results[1].status == "failed"
    assert results[1].failure_reason is not None
    assert results[1].filename == "nonexistent.pdf"


@pytest.mark.asyncio
async def test_ingest_batch_empty_list_returns_empty() -> None:
    svc = RagService()
    results = await svc.ingest_batch([])
    assert results == []


# ─── document_status ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_document_status_returns_succeeded(tmp_path: Path) -> None:
    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]

    pdf = tmp_path / "status.pdf"
    _make_digital_pdf(pdf)
    svc.ingest(str(pdf))

    doc_meta = next(iter(svc._documents.values()))
    doc_id = uuid.UUID(doc_meta["id"])

    status = await svc.document_status(doc_id)

    assert status.status == "succeeded"
    assert status.filename == "status.pdf"
    assert status.page_count == 1
    assert status.id == doc_id


@pytest.mark.asyncio
async def test_document_status_not_found_raises() -> None:
    svc = RagService()
    with pytest.raises(KeyError, match="not found"):
        await svc.document_status(uuid.uuid4())
