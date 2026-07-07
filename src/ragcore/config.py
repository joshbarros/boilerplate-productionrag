"""Application configuration — every knob env-driven (Constitution II, V, VI)."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Provider(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"


class EmbeddingProvider(StrEnum):
    OPENAI = "openai"
    LOCAL = "local"


class RetrievalMode(StrEnum):
    HYBRID = "hybrid"
    VECTOR = "vector"
    KEYWORD = "keyword"


class Settings(BaseSettings):
    """All configuration loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─── LLM Providers ───
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    openrouter_api_key: str = ""

    # ─── Generation routing ───
    default_provider: Provider = Provider.OPENROUTER
    anthropic_default_model: str = "claude-haiku-4-5-20251001"
    anthropic_escalation_model: str = "claude-sonnet-4-6"
    openai_default_model: str = "gpt-4o-mini"
    # OpenRouter (OpenAI-compatible API at https://openrouter.ai/api/v1)
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_default_model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    # "none" = skip reasoning chain → fast clean JSON; "low"/"high" for complex tasks
    openrouter_reasoning_effort: str = "none"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # ─── Embeddings ───
    embedding_provider: EmbeddingProvider = EmbeddingProvider.OPENAI
    openai_embedding_model: str = "text-embedding-3-small"
    local_embedding_model: str = "BAAI/bge-m3"

    # ─── Retrieval ───
    retrieval_mode: RetrievalMode = RetrievalMode.HYBRID
    top_k: int = 8
    rrf_k: int = 60
    rerank_enabled: bool = False
    rerank_model: str = "BAAI/bge-reranker-v2-m3"

    # ─── Vector backends ───
    pgvector_connection: str = (
        "postgresql+psycopg://ragcore:ragcore@localhost:5432/ragcore"
    )
    qdrant_url: str = "http://localhost:6333"
    qdrant_bench_enabled: bool = False

    # ─── Budget ───
    daily_budget_usd: float = 5.00
    query_budget_usd: float = 0.10
    cache_ttl_seconds: int = 3600

    # ─── Security ───
    api_token: str = Field(default="changeme")
    rate_limit_per_minute: int = 30

    # ─── Feature flags ───
    local_llm_enabled: bool = True
    ocr_enabled: bool = True

    # ─── Observability ───
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "ragcore"

    # ─── Server ───
    api_host: str = "0.0.0.0"
    api_port: int = 8800
    mcp_port: int = 8801


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
