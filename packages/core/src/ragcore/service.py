"""Shared service layer — the ONLY thing api/ and mcp_server/ call (D13, VII).

Both FastAPI and FastMCP import from here so guarantees (citations, budgets,
security) cannot drift. Supports storage backends:

* ``memory`` (default) — in-process vector + keyword stores; CI-friendly
* ``postgres`` — documents/chunks in Postgres with pgvector + FTS
* ``qdrant`` — Qdrant vectors + in-memory keyword arm
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import text

from ragcore.budget.cache import ResponseCache
from ragcore.budget.ledger import BudgetExceededError, BudgetLedger, estimate_usd
from ragcore.chunking.fixed import FixedChunker
from ragcore.chunking.recursive import RecursiveChunker
from ragcore.chunking.semantic import SemanticChunker
from ragcore.config import ChunkingStrategy, VectorBackend, get_settings
from ragcore.embedding.provider import Embedder, get_embedder
from ragcore.generation.grounding import (
    compose_answer,
    parse_llm_response,
    verify_citations,
)
from ragcore.generation.prompts import PromptBuilder, default_build_prompt
from ragcore.generation.router import generate_answer
from ragcore.ingestion.loader import load_pdf
from ragcore.obs.metrics import record_ask, record_ingest, timed_ask
from ragcore.retrieval.fts import InMemoryKeywordSearch, PostgresKeywordSearch
from ragcore.retrieval.fusion import reciprocal_rank_fusion
from ragcore.retrieval.rerank import rerank
from ragcore.retrieval.vector_pg import (
    IndexedChunk,
    InMemoryVectorStore,
    MixedModelError,
    PostgresVectorStore,
)
from ragcore.retrieval.vector_qdrant import QdrantVectorStore
from ragcore.security.injection import InjectionBlockedError, check_injection
from ragcore.security.pii import mask_pii
from ragcore.types import (
    AnswerResult,
    BudgetStatusResult,
    DocumentStatusResult,
    SearchResult,
)


class RagService:
    """Use-case layer — called by both HTTP API and MCP server."""

    def __init__(
        self,
        *,
        backend: str | None = None,
        prompt_builder: PromptBuilder | Callable[..., list[dict]] | None = None,
    ) -> None:
        settings = get_settings()
        backend_name = backend or settings.vector_backend.value
        self._backend = VectorBackend(backend_name)
        self._prompt_builder: PromptBuilder = (
            prompt_builder or default_build_prompt  # type: ignore[assignment]
        )

        self._embedder: Embedder | None = None
        self._documents: dict[str, dict] = {}  # fingerprint → metadata
        self._ledger = BudgetLedger(
            daily_cap_usd=settings.daily_budget_usd,
            query_cap_usd=settings.query_budget_usd,
        )
        self._cache = ResponseCache(ttl_seconds=settings.cache_ttl_seconds)
        self._session_factory = None
        self._qdrant_bench: QdrantVectorStore | None = None

        if self._backend == VectorBackend.POSTGRES:
            from ragcore.db import get_session_factory

            self._session_factory = get_session_factory()
            self._vector_store: (
                InMemoryVectorStore | PostgresVectorStore | QdrantVectorStore
            ) = PostgresVectorStore(self._session_factory)
            self._keyword_search: InMemoryKeywordSearch | PostgresKeywordSearch = (
                PostgresKeywordSearch(self._session_factory)
            )
            self._hydrate_documents_from_db()
        elif self._backend == VectorBackend.QDRANT:
            # OpenAI text-embedding-3-small = 1536; local/hash paths pad to match
            dim = 1536 if settings.embedding_provider.value == "openai" else 64
            self._vector_store = QdrantVectorStore(
                url=settings.qdrant_url,
                collection=settings.qdrant_collection,
                vector_size=dim,
            )
            self._keyword_search = InMemoryKeywordSearch()
        else:
            self._vector_store = InMemoryVectorStore()
            self._keyword_search = InMemoryKeywordSearch()

        # Optional dual-write benchmark arm (never on the serving path alone)
        if settings.qdrant_bench_enabled and self._backend != VectorBackend.QDRANT:
            dim = 1536 if settings.embedding_provider.value == "openai" else 64
            self._qdrant_bench = QdrantVectorStore(
                url=settings.qdrant_url,
                collection="chunks_bench",
                vector_size=dim,
            )

    def _get_embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    def _make_chunker(self):
        settings = get_settings()
        if settings.chunking_strategy == ChunkingStrategy.FIXED:
            return FixedChunker(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )
        if settings.chunking_strategy == ChunkingStrategy.SEMANTIC:
            return SemanticChunker(
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                similarity_threshold=settings.semantic_similarity_threshold,
            )
        return RecursiveChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    def _hydrate_documents_from_db(self) -> None:
        """Load fingerprint map so dedup works across restarts."""
        if not self._session_factory:
            return
        sess = self._session_factory()
        try:
            rows = sess.execute(
                text(
                    """
                    SELECT id, fingerprint, title, filename, page_count, status
                    FROM documents
                    WHERE status = 'succeeded'
                    """
                )
            ).fetchall()
            for row in rows:
                self._documents[row.fingerprint] = {
                    "id": str(row.id),
                    "title": row.title,
                    "filename": row.filename,
                    "page_count": row.page_count,
                    "status": row.status,
                }
        except Exception:
            # DB not migrated yet — leave empty; ingest will surface errors
            pass
        finally:
            sess.close()

    def document_count(self) -> int:
        return len(self._documents)

    def ingest(self, file_path: str) -> dict:
        """Ingest a single PDF — load, chunk, embed, index."""
        loaded = load_pdf(file_path)
        return self._index_loaded(loaded)

    def ingest_text(
        self,
        text: str,
        *,
        filename: str = "document.md",
        title: str | None = None,
    ) -> dict:
        """Ingest raw text / markdown as a single-page document."""
        import hashlib

        from ragcore.ingestion.loader import LoadedDocument

        fingerprint = hashlib.sha256(text.encode("utf-8")).hexdigest()
        loaded = LoadedDocument(
            filename=filename,
            title=title or filename,
            pages=[text],
            full_text=text,
            page_count=1,
            fingerprint=fingerprint,
            extraction_method="text",
        )
        return self._index_loaded(loaded)

    def _index_loaded(self, loaded: Any) -> dict:
        """Shared path for PDF-loaded and text documents."""
        if loaded.fingerprint in self._documents:
            return {
                "status": "duplicate",
                "fingerprint": loaded.fingerprint,
                "id": self._documents[loaded.fingerprint]["id"],
            }

        doc_id = uuid.uuid4()
        chunker = self._make_chunker()
        chunk_results = chunker.chunk(loaded.full_text, loaded.pages, doc_id)

        embedder = self._get_embedder()
        texts = [c.text for c in chunk_results]
        embeddings = embedder.embed(texts) if texts else []

        indexed: list[IndexedChunk] = []
        for chunk, emb in zip(chunk_results, embeddings, strict=False):
            chunk_id = uuid.uuid4()
            strategy = chunk.metadata.get("strategy", "recursive")
            meta = {
                **chunk.metadata,
                "embedding_model": embedder.model_id,
                "title": loaded.title,
                "strategy": strategy,
            }
            indexed.append(
                IndexedChunk(
                    chunk_id=str(chunk_id),
                    text=chunk.text,
                    page=chunk.page_start,
                    document_id=str(doc_id),
                    embedding=emb,
                    metadata=meta,
                    embedding_model=embedder.model_id,
                )
            )

        if self._backend == VectorBackend.POSTGRES:
            self._ingest_postgres(doc_id, loaded, indexed)
        else:
            self._vector_store.add_batch(indexed)
            self._keyword_search.add_batch(indexed)

        if self._qdrant_bench is not None:
            try:
                self._qdrant_bench.add_batch(indexed)
            except Exception:
                # Benchmark arm must never fail primary ingest
                pass

        self._documents[loaded.fingerprint] = {
            "id": str(doc_id),
            "title": loaded.title,
            "filename": loaded.filename,
            "page_count": loaded.page_count,
            "status": "succeeded",
        }

        record_ingest()
        return {
            "status": "succeeded",
            "fingerprint": loaded.fingerprint,
            "id": str(doc_id),
            "title": loaded.title,
            "chunks": len(indexed),
            "page_count": loaded.page_count,
        }

    def _ingest_postgres(
        self,
        doc_id: uuid.UUID,
        loaded: Any,
        indexed: list[IndexedChunk],
    ) -> None:
        assert self._session_factory is not None
        sess = self._session_factory()
        try:
            sess.execute(
                text(
                    """
                    INSERT INTO documents (
                        id, fingerprint, title, filename, language,
                        page_count, status, extraction_summary
                    ) VALUES (
                        :id, :fingerprint, :title, :filename, :language,
                        :page_count, 'succeeded', CAST(:extraction AS jsonb)
                    )
                    """
                ),
                {
                    "id": str(doc_id),
                    "fingerprint": loaded.fingerprint,
                    "title": loaded.title,
                    "filename": loaded.filename,
                    "language": "en",
                    "page_count": loaded.page_count,
                    "extraction": __import__("json").dumps(
                        {"method": loaded.extraction_method}
                    ),
                },
            )
            store = self._vector_store
            assert isinstance(store, PostgresVectorStore)
            store.add_batch(indexed, session=sess)
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    async def ask(
        self,
        question: str,
        top_k: int = 8,
        config_override: dict[str, Any] | None = None,
    ) -> AnswerResult:
        """Answer a question with grounded citations or refuse (FR-001/002/003)."""
        settings = get_settings()
        top_k = top_k or settings.top_k
        override = config_override or {}

        with timed_ask() as _timer:
            result = await self._ask_inner(
                question, top_k, override, settings
            )
        latency = float(_timer.get("elapsed_ms", 0.0))
        result.latency_ms = result.latency_ms or int(latency)
        cache_hit = bool(result.config.get("cache_hit"))
        record_ask(
            status=result.status,
            latency_ms=latency,
            cost_usd=float(result.cost.usd_estimate or 0.0),
            cache_hit=cache_hit,
        )
        return result

    async def _ask_inner(
        self,
        question: str,
        top_k: int,
        override: dict[str, Any],
        settings: Any,
    ) -> AnswerResult:
        # Security gate (FR-014/015)
        if settings.security_enabled and not override.get("skip_security"):
            try:
                check_injection(question)
            except InjectionBlockedError as exc:
                return AnswerResult(
                    status="rejected_security",
                    config={"reason": str(exc), "kind": "injection"},
                )

        masked_question = mask_pii(question) if settings.security_enabled else question

        # Cache lookup (FR-012)
        cache_cfg = {
            "top_k": top_k,
            "retrieval": override.get("retrieval", settings.retrieval_mode.value),
            "backend": self._backend.value,
            "model": settings.openrouter_default_model
            if settings.default_provider.value == "openrouter"
            else settings.default_provider.value,
        }
        cache_key = ResponseCache.make_key(masked_question, cache_cfg)
        if settings.cache_enabled and not override.get("skip_cache"):
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached

        # Budget pre-flight
        preflight_tokens = 500
        model_hint = settings.openrouter_default_model
        preflight_usd = estimate_usd(model_hint, preflight_tokens, preflight_tokens)
        try:
            self._ledger.check(preflight_usd)
        except BudgetExceededError as exc:
            return AnswerResult(
                status="rejected_budget",
                config={
                    "reason": str(exc),
                    "kind": exc.kind,
                    "cap_usd": exc.cap_usd,
                },
            )

        mode = override.get("retrieval", settings.retrieval_mode.value)
        embedder = self._get_embedder()
        query_emb = embedder.embed([masked_question])[0]

        try:
            # Pull a wider pool when reranking so the cross-encoder has room.
            retrieve_k = top_k * 3 if settings.rerank_enabled else top_k
            if mode == "vector":
                fused = self._vector_store.search(
                    query_emb, top_k=retrieve_k, query_model=embedder.model_id
                )
            elif mode == "keyword":
                fused = self._keyword_search.search(masked_question, top_k=retrieve_k)
            else:
                vector_results = self._vector_store.search(
                    query_emb, top_k=retrieve_k, query_model=embedder.model_id
                )
                keyword_results = self._keyword_search.search(
                    masked_question, top_k=retrieve_k
                )
                fused = reciprocal_rank_fusion(
                    vector_results,
                    keyword_results,
                    k=settings.rrf_k,
                    top_k=retrieve_k,
                )
        except MixedModelError as exc:
            return AnswerResult(
                status="not_found",
                config={"error": str(exc), "kind": "mixed_model"},
            )

        if settings.rerank_enabled and fused:
            use_ce = override.get(
                "use_cross_encoder", settings.rerank_cross_encoder
            )
            fused = rerank(
                masked_question,
                fused,
                top_k=top_k,
                model_name=settings.rerank_model,
                use_cross_encoder=bool(use_ce),
            )
        else:
            fused = fused[:top_k]

        if not fused:
            result = AnswerResult(
                status="not_found",
                config={
                    "retrieval": mode,
                    "top_k": top_k,
                    "backend": self._backend.value,
                },
            )
            if settings.cache_enabled:
                self._cache.put(cache_key, result)
            return result

        # Use up to 5 passages (or top_k if smaller) so hybrid retrieval has room
        # to surface rare codes/acronyms that rank just outside the top 3.
        n_passages = min(max(top_k, 3), 5, len(fused))
        passages = [
            {
                "chunk_id": r.chunk_id,
                "page": r.page,
                "text": r.text[:800],
                "document_id": r.document_id,
                "title": r.metadata.get("title", ""),
            }
            for r in fused[:n_passages]
        ]

        model_override = override.get("model")
        gen_result = generate_answer(
            masked_question,
            passages,
            model_override=model_override,
            prompt_builder=self._prompt_builder,
        )

        cost_record = self._ledger.record(
            model=gen_result.model_used,
            prompt_tokens=gen_result.prompt_tokens,
            completion_tokens=gen_result.completion_tokens,
        )

        parsed = parse_llm_response(gen_result.text)
        verified = verify_citations(parsed, passages)
        config = {
            "retrieval": mode,
            "top_k": top_k,
            "model": gen_result.model_used,
            "rerank": settings.rerank_enabled,
            "rerank_cross_encoder": bool(
                override.get("use_cross_encoder", settings.rerank_cross_encoder)
            )
            if settings.rerank_enabled
            else False,
            "backend": self._backend.value,
            "chunking": settings.chunking_strategy.value,
            "niche_prompt": self._prompt_builder is not default_build_prompt,
        }
        if override:
            skip = ("skip_cache", "skip_security")
            config["override"] = {k: v for k, v in override.items() if k not in skip}

        answer = compose_answer(parsed, verified, gen_result, config)
        # Prefer ledger-computed USD (same table as preflight)
        answer.cost.usd_estimate = cost_record.usd

        if settings.cache_enabled:
            self._cache.put(cache_key, answer)
        return answer

    async def search(
        self,
        query: str,
        top_k: int = 8,
        mode: str = "hybrid",
    ) -> list[SearchResult]:
        """Return raw ranked chunks — retrieval-only surface."""
        settings = get_settings()
        if settings.security_enabled:
            check_injection(query)
            query = mask_pii(query)

        embedder = self._get_embedder()
        query_emb = embedder.embed([query])[0]

        if mode == "vector":
            results = self._vector_store.search(
                query_emb, top_k=top_k, query_model=embedder.model_id
            )
        elif mode == "keyword":
            results = self._keyword_search.search(query, top_k=top_k)
        else:
            vector_results = self._vector_store.search(
                query_emb, top_k=top_k, query_model=embedder.model_id
            )
            keyword_results = self._keyword_search.search(query, top_k=top_k)
            results = reciprocal_rank_fusion(
                vector_results, keyword_results, k=settings.rrf_k, top_k=top_k
            )

        return [
            SearchResult(
                chunk_id=uuid.UUID(r.chunk_id) if r.chunk_id else uuid.UUID(int=0),
                document_id=(
                    uuid.UUID(r.document_id) if r.document_id else uuid.UUID(int=0)
                ),
                page=r.page,
                text=r.text,
                scores={
                    "vector": r.vector_score,
                    "keyword": r.keyword_score,
                    "fused": r.fused_score,
                },
            )
            for r in results
        ]

    async def ingest_batch(self, file_paths: list[str]) -> list[DocumentStatusResult]:
        """Ingest a batch of PDFs, reporting per-document status."""
        results: list[DocumentStatusResult] = []
        for path in file_paths:
            filename = path.split("/")[-1]
            try:
                outcome = self.ingest(path)
                fp = outcome.get("fingerprint")
                doc_meta = self._documents.get(fp) if fp else None
                results.append(
                    DocumentStatusResult(
                        id=uuid.UUID(doc_meta["id"]) if doc_meta else uuid.UUID(int=0),
                        filename=filename,
                        status=outcome["status"],
                        page_count=doc_meta["page_count"] if doc_meta else 0,
                    )
                )
            except Exception as exc:
                results.append(
                    DocumentStatusResult(
                        id=uuid.UUID(int=0),
                        filename=filename,
                        status="failed",
                        page_count=0,
                        failure_reason=str(exc),
                    )
                )
        return results

    async def document_status(self, document_id: uuid.UUID) -> DocumentStatusResult:
        """Return ingestion status for a single document by its UUID."""
        doc_id_str = str(document_id)
        for meta in self._documents.values():
            if meta["id"] == doc_id_str:
                return DocumentStatusResult(
                    id=document_id,
                    filename=meta["filename"],
                    status=meta.get("status", "succeeded"),
                    page_count=meta["page_count"],
                )

        # Postgres fallback
        if self._session_factory:
            sess = self._session_factory()
            try:
                row = sess.execute(
                    text(
                        """
                        SELECT id, filename, status, page_count, failure_reason
                        FROM documents WHERE id = :id
                        """
                    ),
                    {"id": doc_id_str},
                ).fetchone()
                if row:
                    return DocumentStatusResult(
                        id=document_id,
                        filename=row.filename,
                        status=row.status,
                        page_count=row.page_count,
                        failure_reason=row.failure_reason,
                    )
            finally:
                sess.close()

        raise KeyError(f"Document {document_id} not found")

    async def budget_status(self) -> BudgetStatusResult:
        """Return current budget ledger snapshot."""
        snap = self._ledger.snapshot()
        return BudgetStatusResult(
            period=snap["period"],
            scope=snap["scope"],
            cap_usd=snap["daily_cap_usd"],
            consumed_usd=snap["consumed_usd"],
            rejected_count=snap["rejected_count"],
        )


# Singleton — both api/ and mcp_server/ import this
service = RagService()
