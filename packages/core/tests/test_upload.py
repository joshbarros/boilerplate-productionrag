"""Multipart upload + ingest_text tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ragcore.api.app import create_app
from ragcore.service import RagService


class FakeEmbedder:
    model_id = "fake-embedder-v1"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(t)), 1.0, 0.0] for t in texts]


def test_ingest_text_indexes_markdown() -> None:
    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]
    out = svc.ingest_text(
        "# Revenue recognition\n\nASC 606 has a five-step model.",
        filename="asc606.md",
    )
    assert out["status"] == "succeeded"
    assert out["chunks"] >= 1


def test_upload_endpoint_accepts_text_file(monkeypatch) -> None:
    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]
    app = create_app(svc)
    client = TestClient(app)

    files = {
        "files": (
            "note.md",
            b"# Hello\n\nThis is a test document about widgets.",
            "text/markdown",
        )
    }
    res = client.post(
        "/v1/documents/upload",
        files=files,
        headers={"Authorization": "Bearer changeme"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["results"][0]["status"] == "succeeded"
    assert body["results"][0]["filename"] == "note.md"


def test_upload_rejects_bad_extension() -> None:
    svc = RagService()
    app = create_app(svc)
    client = TestClient(app)
    files = {"files": ("evil.exe", b"MZ", "application/octet-stream")}
    res = client.post(
        "/v1/documents/upload",
        files=files,
        headers={"Authorization": "Bearer changeme"},
    )
    assert res.status_code == 200
    assert res.json()["results"][0]["status"] == "failed"


def test_upload_pdf_fixture(monkeypatch) -> None:
    svc = RagService()
    svc._get_embedder = lambda: FakeEmbedder()  # type: ignore[method-assign]
    app = create_app(svc)
    client = TestClient(app)
    fixture = Path(__file__).parent / "fixtures" / "langchain_demo.pdf"
    data = fixture.read_bytes()
    files = {"files": ("langchain_demo.pdf", data, "application/pdf")}
    res = client.post(
        "/v1/documents/upload",
        files=files,
        headers={"Authorization": "Bearer changeme"},
    )
    assert res.status_code == 200
    assert res.json()["results"][0]["status"] in {"succeeded", "duplicate"}
