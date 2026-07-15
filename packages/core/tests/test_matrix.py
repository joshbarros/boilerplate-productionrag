"""Config matrix offline smoke — memory backend only (no Qdrant/network)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ragcore.evals.matrix import run_matrix

_FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.asyncio
async def test_matrix_memory_cells() -> None:
    report = await run_matrix(
        golden_path=str(_FIXTURES / "golden_set.json"),
        fixture_paths=[str(_FIXTURES / "langchain_demo.pdf")],
        include_qdrant=False,
        # Keep the smoke matrix small
        chunking=["recursive"],
        retrieval=["hybrid", "keyword"],
        rerank_opts=[False, True],
    )
    assert report.cells
    assert all(c.error is None for c in report.cells), [
        (c.backend, c.retrieval, c.error) for c in report.cells if c.error
    ]
    # At least one cell should clear the 50% floor offline
    assert max(c.pass_rate for c in report.cells) >= 0.5
    md = report.to_markdown()
    assert "recursive" in md
    assert "hybrid" in md
