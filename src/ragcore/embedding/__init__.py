"""Embedding package — provider abstraction with model-id pinning (D6)."""

from ragcore.embedding.provider import Embedder, get_embedder

__all__ = ["Embedder", "get_embedder"]
