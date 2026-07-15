"""Optional Postgres smoke — skips when VECTOR_BACKEND is not postgres."""

from __future__ import annotations

import os

import pytest

from ragcore.config import get_settings
from ragcore.db import ping_db, reset_engine


@pytest.mark.skipif(
    os.getenv("VECTOR_BACKEND", "memory") != "postgres",
    reason="Set VECTOR_BACKEND=postgres to run durable-store smoke",
)
def test_postgres_ping_and_migrate_tables() -> None:
    get_settings.cache_clear()
    reset_engine()
    assert ping_db() is True

    from sqlalchemy import text

    from ragcore.db import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        # Extensions + core tables from alembic 0001
        n = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name IN ('documents', 'chunks')
                """
            )
        ).scalar()
        assert n == 2
