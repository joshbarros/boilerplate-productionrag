"""Initial schema: documents, chunks (pgvector + FTS), queries, answers, citations,
golden_cases, eval_runs, budget_ledger, response_cache.

Revision ID: 0001
Revises:
Create Date: 2026-07-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_enum(name: str, *values: str) -> None:
    """Idempotent CREATE TYPE — avoids DuplicateObject on SQLAlchemy table emit."""
    vals = ", ".join(f"'{v}'" for v in values)
    op.execute(
        sa.text(
            f"""
            DO $$ BEGIN
                CREATE TYPE {name} AS ENUM ({vals});
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ── enums (create once; column defs must use create_type=False) ─────────
    _create_enum(
        "documentstatus", "pending", "processing", "succeeded", "failed"
    )
    _create_enum("chunkingstrategy", "fixed", "recursive", "semantic")
    _create_enum(
        "answerstatus",
        "answered",
        "not_found",
        "rejected_budget",
        "rejected_security",
        "degraded",
    )
    _create_enum("goldencasestatus", "active", "disputed", "excluded")
    _create_enum("evalverdict", "pass", "regression")
    _create_enum("budgetscope", "query", "day")

    document_status = postgresql.ENUM(
        "pending",
        "processing",
        "succeeded",
        "failed",
        name="documentstatus",
        create_type=False,
    )
    chunking_strategy = postgresql.ENUM(
        "fixed",
        "recursive",
        "semantic",
        name="chunkingstrategy",
        create_type=False,
    )
    answer_status = postgresql.ENUM(
        "answered",
        "not_found",
        "rejected_budget",
        "rejected_security",
        "degraded",
        name="answerstatus",
        create_type=False,
    )
    golden_status = postgresql.ENUM(
        "active",
        "disputed",
        "excluded",
        name="goldencasestatus",
        create_type=False,
    )
    eval_verdict = postgresql.ENUM(
        "pass",
        "regression",
        name="evalverdict",
        create_type=False,
    )
    budget_scope = postgresql.ENUM(
        "query",
        "day",
        name="budgetscope",
        create_type=False,
    )

    # ── documents ──────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="pt"),
        sa.Column("page_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "status",
            document_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("extraction_summary", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_documents_fingerprint", "documents", ["fingerprint"], unique=True
    )

    # ── chunks ─────────────────────────────────────────────────────────────
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("strategy", chunking_strategy, nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=False),
        sa.Column("page_end", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_chunks_document_id", "chunks", ["document_id"])
    op.create_index("ix_chunks_embedding_model", "chunks", ["embedding_model"])

    op.execute("ALTER TABLE chunks ADD COLUMN embedding vector(1536)")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
        ON chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )
    op.execute(
        """
        ALTER TABLE chunks
        ADD COLUMN tsv tsvector
        GENERATED ALWAYS AS (to_tsvector('simple', coalesce(text, ''))) STORED
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_chunks_tsv_gin ON chunks USING gin (tsv)"
    )

    # ── queries ────────────────────────────────────────────────────────────
    op.create_table(
        "queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("masked_text", sa.Text(), nullable=False),
        sa.Column("client_id", sa.Text(), nullable=True),
        sa.Column("budget_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── answers ────────────────────────────────────────────────────────────
    op.create_table(
        "answers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("queries.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", answer_status, nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=True),
        sa.Column("config", postgresql.JSONB(), nullable=True),
        sa.Column("cost", postgresql.JSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── citations ──────────────────────────────────────────────────────────
    op.create_table(
        "citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "answer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("answers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chunk_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chunks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("page", sa.Integer(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("support_score", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_citations_answer_id", "citations", ["answer_id"])
    op.create_index("ix_citations_chunk_id", "citations", ["chunk_id"])
    op.create_index("ix_citations_document_id", "citations", ["document_id"])

    # ── golden_cases ───────────────────────────────────────────────────────
    op.create_table(
        "golden_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column("expected_document_fingerprint", sa.Text(), nullable=False),
        sa.Column("expected_pages", postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="pt"),
        sa.Column("answerable", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "status",
            golden_status,
            nullable=False,
            server_default="active",
        ),
        sa.Column("audit_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_golden_cases_fingerprint",
        "golden_cases",
        ["expected_document_fingerprint"],
    )

    # ── eval_runs ──────────────────────────────────────────────────────────
    op.create_table(
        "eval_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("git_sha", sa.String(40), nullable=True),
        sa.Column("config_matrix", postgresql.JSONB(), nullable=True),
        sa.Column("scores", postgresql.JSONB(), nullable=True),
        sa.Column(
            "baseline_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("eval_runs.id"),
            nullable=True,
        ),
        sa.Column("verdict", eval_verdict, nullable=True),
        sa.Column("report_path", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # ── budget_ledger ──────────────────────────────────────────────────────
    op.create_table(
        "budget_ledger",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("scope", budget_scope, nullable=False),
        sa.Column("cap_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column(
            "consumed_usd", sa.Numeric(10, 4), nullable=False, server_default="0"
        ),
        sa.Column("rejected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_budget_ledger_period", "budget_ledger", ["period"])

    # ── response_cache ─────────────────────────────────────────────────────
    op.create_table(
        "response_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column(
            "answer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("answers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "ttl",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("response_cache")
    op.drop_table("budget_ledger")
    op.drop_table("eval_runs")
    op.drop_table("golden_cases")
    op.drop_table("citations")
    op.drop_table("answers")
    op.drop_table("queries")
    op.drop_table("chunks")
    op.drop_table("documents")

    for name in (
        "budgetscope",
        "evalverdict",
        "goldencasestatus",
        "answerstatus",
        "chunkingstrategy",
        "documentstatus",
    ):
        op.execute(f"DROP TYPE IF EXISTS {name}")
