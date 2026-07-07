"""Embedding provider — OpenAI text-embedding-3-small + local bge-m3 (D6).

Key invariant (Constitution D6): the same model MUST be used for indexing
and querying. This is enforced by storing the embedding model id on every
chunk and refusing mixed-model search.
"""

from __future__ import annotations

from typing import Protocol

from ragcore.config import get_settings
from ragcore.obs.otel import stage_span


class Embedder(Protocol):
    """Interface for embedding providers."""

    model_id: str

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts into vectors."""
        ...


class OpenAIEmbedder:
    """OpenAI text-embedding-3-small embedder (1536 dims)."""

    def __init__(self, api_key: str, model: str, base_url: str | None = None) -> None:
        from openai import OpenAI

        self.model_id = model
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)

    @stage_span("embed.openai")
    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(
            model=self.model_id,
            input=texts,
        )
        return [item.embedding for item in response.data]


class LocalEmbedder:
    """Local bge-m3 embedder via sentence-transformers (air-gap mode, D6)."""

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_id = model_name
        self._model = SentenceTransformer(model_name)

    @stage_span("embed.local")
    def embed(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [emb.tolist() for emb in embeddings]


def get_embedder() -> Embedder:
    """Factory: return the configured embedder based on settings."""
    settings = get_settings()

    if settings.embedding_provider.value == "local":
        return LocalEmbedder(settings.local_embedding_model)

    # Default: OpenAI (or OpenRouter-compatible if base_url is set)
    return OpenAIEmbedder(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
