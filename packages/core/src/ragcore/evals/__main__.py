"""CLI: python -m ragcore.evals --mode offline --gate

Examples::

    # CI gate (deterministic)
    python -m ragcore.evals \\
      --golden tests/fixtures/golden_set.json \\
      --fixture tests/fixtures/langchain_demo.pdf \\
      --mode offline --gate \\
      --baseline evals/results/baseline_core_offline.json \\
      --out evals/results/latest_core_offline.json

    # Write a new baseline
    python -m ragcore.evals ... --mode offline --write-baseline path.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from ragcore.evals.regression import (
    check_regression,
    load_baseline,
    summary_to_dict,
    verdict_to_dict,
    write_baseline,
)
from ragcore.evals.runner import EvalRunner, render_markdown_table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Production RAG eval runner")
    parser.add_argument("--golden", required=True, help="Path to golden_set.json")
    parser.add_argument(
        "--fixture",
        action="append",
        dest="fixtures",
        default=[],
        help="Fixture path (PDF/md/txt). Repeatable.",
    )
    parser.add_argument(
        "--mode",
        choices=("offline", "live"),
        default="offline",
        help="offline = HashEmbedder + deterministic answers (default)",
    )
    parser.add_argument("--baseline", help="Baseline JSON for regression gate")
    parser.add_argument(
        "--max-drop-pts",
        type=float,
        default=2.0,
        help="Max allowed pass_rate drop in percentage points (default 2.0)",
    )
    parser.add_argument(
        "--min-pass-rate",
        type=float,
        default=0.70,
        help="Absolute minimum pass_rate (default 0.70). Set 0 to disable.",
    )
    parser.add_argument("--gate", action="store_true", help="Exit 1 on regression")
    parser.add_argument("--out", help="Write full results JSON here")
    parser.add_argument("--md-out", help="Write markdown report here")
    parser.add_argument(
        "--write-baseline",
        help="Also write this run as a baseline JSON at the given path",
    )
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Run config matrix (chunk × retrieval × rerank × backend)",
    )
    parser.add_argument(
        "--matrix-qdrant",
        action="store_true",
        help="Include Qdrant arm in matrix when reachable",
    )
    args = parser.parse_args(argv)

    if not args.fixtures:
        parser.error("at least one --fixture is required")

    if args.matrix:
        from ragcore.evals.matrix import run_matrix_sync

        report = run_matrix_sync(
            args.golden,
            args.fixtures,
            include_qdrant=args.matrix_qdrant or None,
        )
        print(report.to_markdown())
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(
                json.dumps(report.to_dict(), indent=2) + "\n",
                encoding="utf-8",
            )
            print(f"Wrote matrix → {args.out}")
        if args.md_out:
            Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.md_out).write_text(report.to_markdown(), encoding="utf-8")
        # Matrix is informational; exit 0 unless every cell errored
        if report.cells and all(c.error for c in report.cells):
            return 1
        return 0

    runner = EvalRunner(
        golden_path=args.golden,
        fixture_paths=args.fixtures,
        mode=args.mode,  # type: ignore[arg-type]
    )
    summary = asyncio.run(runner.run())

    print(render_markdown_table(summary))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(summary_to_dict(summary), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote results → {args.out}")

    if args.md_out:
        Path(args.md_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md_out).write_text(render_markdown_table(summary), encoding="utf-8")
        print(f"Wrote markdown → {args.md_out}")

    if args.write_baseline:
        write_baseline(args.write_baseline, summary)
        print(f"Wrote baseline → {args.write_baseline}")

    baseline = None
    baseline_path = args.baseline
    if not baseline_path and args.write_baseline:
        # Freshly written baseline is the reference for this run's gate.
        baseline_path = args.write_baseline
    if baseline_path and Path(baseline_path).exists():
        baseline = load_baseline(baseline_path)
    elif baseline_path:
        print(f"WARNING: baseline not found at {baseline_path}", file=sys.stderr)

    min_rate = args.min_pass_rate if args.min_pass_rate > 0 else None
    verdict = check_regression(
        summary,
        baseline,
        max_drop_pts=args.max_drop_pts,
        min_pass_rate=min_rate,
    )
    print(
        f"\nRegression verdict: {verdict.verdict} "
        f"(current={verdict.current_pass_rate:.1%}, "
        f"baseline={verdict.baseline_pass_rate}, "
        f"drop_pts={verdict.drop_pts})"
    )
    print(json.dumps(verdict_to_dict(verdict), indent=2))

    if args.gate and not verdict.ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
