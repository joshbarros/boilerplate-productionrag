"""Generation package — provider routing, prompts, grounding (D7)."""

from ragcore.generation.grounding import compose_answer, verify_citations
from ragcore.generation.router import generate_answer

__all__ = ["generate_answer", "verify_citations", "compose_answer"]
