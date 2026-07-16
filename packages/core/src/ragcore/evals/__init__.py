"""Eval suite — golden-set runner, offline mode, regression gate, matrix."""

from ragcore.evals.matrix import MatrixReport, run_matrix, run_matrix_sync
from ragcore.evals.regression import check_regression, write_baseline
from ragcore.evals.runner import EvalRunner, render_markdown_table
from ragcore.evals.types import EvalCase, EvalResult, EvalSummary

__all__ = [
    "EvalCase",
    "EvalResult",
    "EvalSummary",
    "EvalRunner",
    "MatrixReport",
    "check_regression",
    "write_baseline",
    "render_markdown_table",
    "run_matrix",
    "run_matrix_sync",
]
