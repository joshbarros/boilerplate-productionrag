"""Shared service layer — the ONLY thing api/ and mcp_server/ call (D13, VII).

This module defines the use-case signatures. Implementation is filled in
Phase 3 (US1 MVP) and beyond. Both FastAPI and FastMCP import from here,
so guarantees (citations, budgets, security) cannot drift.
"""

from __future__ import annotations

import uuid
from typing import Any

from ragcore.budget.ledger import BudgetExceededError, BudgetLedger, estimate_usd
from ragcore.chunking.recursive import RecursiveChunker
from ragcore.config import get_settings
from ragcore.embedding.provider import Embedder, get_embedder
from ragcore.generation.grounding import (
    compose_answer,
    parse_llm_response,
    verify_citations,
)
from ragcore.generation.router import generate_answer
from ragcore.ingestion.loader import load_pdf
from ragcore.retrieval.fts import InMemoryKeywordSearch
from ragcore.retrieval.fusion import reciprocal_rank_fusion
from ragcore.retrieval.vector_pg import IndexedChunk, InMemoryVectorStore
from ragcore.types import (
    AnswerResult,
    BudgetStatusResult,
    DocumentStatusResult,
    SearchResult,
)


class RagService:
    """Use-case layer — called by both HTTP API and MCP server.

    In Phase 3 (MVP), this uses in-memory stores. pgvector + Postgres
    are wired in later phases. The pipeline is:
    load → chunk → embed → index → retrieve → fuse → generate → ground
    """

    def __init__(self) -> None:
        self._vector_store = InMemoryVectorStore()
        self._keyword_search = InMemoryKeywordSearch()
        self._embedder: Embedder | None = None
        self._documents: dict[str, dict] = {}  # fingerprint → metadata
        settings = get_settings()
        self._ledger = BudgetLedger(
            daily_cap_usd=settings.daily_budget_usd,
            query_cap_usd=settings.query_budget_usd,
        )

    def _get_embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = get_embedder()
        return self._embedder

    def ingest(self, file_path: str) -> dict:
        """Ingest a single PDF — load, chunk, embed, index."""
        # Load PDF
        loaded = load_pdf(file_path)

        # Dedup check (FR-006)
        if loaded.fingerprint in self._documents:
            return {"status": "duplicate", "fingerprint": loaded.fingerprint}

        # Chunk
        chunker = RecursiveChunker(chunk_size=1000, chunk_overlap=200)
        chunk_results = chunker.chunk(
            loaded.full_text, loaded.pages, uuid.uuid4()
        )

        # Embed
        embedder = self._get_embedder()
        texts = [c.text for c in chunk_results]
        embeddings = embedder.embed(texts)

        # Index
        doc_id = str(uuid.uuid4())
        indexed: list[IndexedChunk] = []
        for i, (chunk, emb) in enumerate(zip(chunk_results, embeddings, strict=False)):
            ic = IndexedChunk(
                chunk_id=str(uuid.uuid4()),
                text=chunk.text,
                page=chunk.page_start,
                document_id=doc_id,
                embedding=emb,
                metadata={
                    **chunk.metadata,
                    "embedding_model": embedder.model_id,
                    "title": loaded.title,
                },
            )
            indexed.append(ic)

        self._vector_store.add_batch(indexed)
        self._keyword_search.add_batch(indexed)
        self._documents[loaded.fingerprint] = {
            "id": doc_id,
            "title": loaded.title,
            "filename": loaded.filename,
            "page_count": loaded.page_count,
        }

        return {
            "status": "succeeded",
            "fingerprint": loaded.fingerprint,
            "title": loaded.title,
            "chunks": len(indexed),
        }

    async def ask(
        self,
        question: str,
        top_k: int = 8,
        config_override: dict[str, Any] | None = None,
    ) -> AnswerResult:
        """Answer a question with grounded citations or refuse (FR-001/002/003)."""
        settings = get_settings()
        top_k = top_k or settings.top_k

        # 0. Budget pre-flight — estimate cost before doing any LLM work
        #    Use a conservative 500-token estimate for the pre-call check;
        #    actual tokens are recorded after the call.
        preflight_tokens = 500
        preflight_usd = estimate_usd(
            settings.openrouter_default_model, preflight_tokens, preflight_tokens
        )
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

        # 1. Embed the query
        embedder = self._get_embedder()
        query_emb = embedder.embed([question])[0]

        # 2. Vector search
        vector_results = self._vector_store.search(query_emb, top_k=top_k)

        # 3. Keyword search
        keyword_results = self._keyword_search.search(question, top_k=top_k)

        # 4. RRF fusion (Constitution IV: hybrid by default)
        fused = reciprocal_rank_fusion(
            vector_results, keyword_results, k=settings.rrf_k, top_k=top_k
        )

        if not fused:
            return AnswerResult(
                status="not_found",
                config={"retrieval": settings.retrieval_mode.value, "top_k": top_k},
            )

        # 5. Build passages for the LLM (top 3 to limit token usage)
        passages = [
            {
                "chunk_id": r.chunk_id,
                "page": r.page,
                "text": r.text[:500],  # truncate to keep prompt small
                "document_id": r.document_id,
                "title": r.metadata.get("title", ""),
            }
            for r in fused[:3]
        ]

        # 6. Generate
        gen_result = generate_answer(question, passages)

        # 6a. Record actual cost in the ledger
        self._ledger.record(
            model=gen_result.model_used,
            prompt_tokens=gen_result.prompt_tokens,
            completion_tokens=gen_result.completion_tokens,
        )

        # 7. Parse + verify citations + compose (cite-or-refuse)
        parsed = parse_llm_response(gen_result.text)
        verified = verify_citations(parsed, passages)
        config = {
            "retrieval": settings.retrieval_mode.value,
            "top_k": top_k,
            "model": gen_result.model_used,
            "rerank": False,
            "backend": "in_memory",
        }

        return compose_answer(parsed, verified, gen_result, config)

    async def search(
        self,
        query: str,
        top_k: int = 8,
        mode: str = "hybrid",
    ) -> list[SearchResult]:
        """Return raw ranked chunks — retrieval-only surface."""
        settings = get_settings()
        embedder = self._get_embedder()
        query_emb = embedder.embed([query])[0]

        if mode == "vector":
            results = self._vector_store.search(query_emb, top_k=top_k)
        elif mode == "keyword":
            results = self._keyword_search.search(query, top_k=top_k)
        else:
            vector_results = self._vector_store.search(query_emb, top_k=top_k)
            keyword_results = self._keyword_search.search(query, top_k=top_k)
            results = reciprocal_rank_fusion(
                vector_results, keyword_results, k=settings.rrf_k, top_k=top_k
            )

        return [
            SearchResult(
                chunk_id=uuid.UUID(r.chunk_id) if r.chunk_id else uuid.UUID(int=0),
                document_id=(
                    uuid.UUID(r.document_id)
                    if r.document_id
                    else uuid.UUID(int=0)
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
        """Ingest a batch of PDFs, reporting per-document status.

        Each file is processed independently; a failure on one file does not
        abort the rest of the batch.
        """
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
                    status="succeeded",
                    page_count=meta["page_count"],
                )
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
