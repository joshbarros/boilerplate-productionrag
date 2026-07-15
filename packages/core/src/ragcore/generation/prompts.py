"""Grounded-answer prompt — answer ONLY from passages, cite chunk ids, else refuse.

Supports niche isolation via ``PromptBuilder`` callables passed into RagService
or registered as the process default — no monkey-patching required.
"""

from __future__ import annotations

from collections.abc import Callable

type PromptBuilder = Callable[[str, list[dict]], list[dict]]

SYSTEM_PROMPT = (
    "You are a document QA assistant. Answer questions using ONLY the provided"
    " passages.\n\n"
    "Rules:\n"
    "1. Answer ONLY from the passages. Do not use outside knowledge.\n"
    "2. If the answer is not in the passages, return status \"not_found\".\n"
    "3. Include at least one citation with a verbatim excerpt from the passage.\n"
    "4. Never fabricate information.\n\n"
    "Output JSON:\n"
    '{"status": "answered", "answer": "your answer", "citations": '
    '[{"chunk_id": "id", "page": 0, "excerpt": "verbatim text"}]}\n'
    "or\n"
    '{"status": "not_found", "answer": null, "citations": []}'
)

USER_TEMPLATE = """Passages:
{passages}

Question: {question}

Respond in JSON only."""

# Process-level default builder (niches should prefer RagService(prompt_builder=...))
_default_builder: PromptBuilder | None = None


def set_default_prompt_builder(builder: PromptBuilder | None) -> None:
    """Set the process-wide default prompt builder (optional convenience)."""
    global _default_builder
    _default_builder = builder


def default_build_prompt(question: str, passages: list[dict]) -> list[dict]:
    """Core grounded-answer messages (generic corpus)."""
    passage_text = "\n\n---\n\n".join(
        f"[Passage {i + 1}] (chunk_id: {p['chunk_id']}, page: {p['page']})\n{p['text']}"
        for i, p in enumerate(passages)
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(
                passages=passage_text, question=question
            ),
        },
    ]


def build_prompt(question: str, passages: list[dict]) -> list[dict]:
    """Build chat messages — uses registered default builder if set."""
    if _default_builder is not None:
        return _default_builder(question, passages)
    return default_build_prompt(question, passages)


def niche_prompt_builder(
    system_prompt: str,
    *,
    source_label: str = "source",
) -> PromptBuilder:
    """Factory for domain skins (medical / legal / accounting).

    Produces a builder that keeps the same JSON citation contract as core
    while swapping the system instructions and passage labeling.
    """

    def _builder(question: str, passages: list[dict]) -> list[dict]:
        blocks = []
        for p in passages:
            cid = p.get("chunk_id", "?")
            src = p.get("document_id", p.get("title", "?"))
            blocks.append(
                f"[chunk_id={cid}] [{source_label}={src}]\n{p['text']}"
            )
        body = (
            "Passages:\n\n"
            + "\n\n---\n\n".join(blocks)
            + f"\n\nQuestion: {question}\n\n"
            "Respond in JSON with this exact schema:\n"
            '{"status": "answered" or "not_found",\n'
            ' "answer": "string",\n'
            ' "citations": [{"chunk_id": "<the chunk_id from the passage you used>", '
            '"excerpt": "<a short verbatim quote from that passage>", "page": 0}]}\n'
            "\nRules:\n"
            "- Citations MUST include the exact chunk_id from passages\n"
            "- excerpt MUST be a verbatim substring of that passage\n"
            '- If unsupported, status="not_found" and answer=null'
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": body},
        ]

    return _builder
