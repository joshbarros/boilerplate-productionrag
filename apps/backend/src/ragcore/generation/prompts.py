"""Grounded-answer prompt — answer ONLY from passages, cite chunk ids, else refuse.

This prompt enforces FR-002 (citations) and FR-003 (refuse when ungrounded).
The LLM is instructed to output structured JSON so we can parse citations
and verify them programmatically (Constitution I: evals gate everything).
"""

from __future__ import annotations

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


def build_prompt(question: str, passages: list[dict]) -> list[dict]:
    """Build the chat messages for the LLM.

    Args:
        question: The user's question.
        passages: List of dicts with chunk_id, page, text.

    Returns:
        List of message dicts for the OpenAI-compatible API.
    """
    passage_text = "\n\n---\n\n".join(
        f"[Passage {i + 1}] (chunk_id: {p['chunk_id']}, page: {p['page']})\n{p['text']}"
        for i, p in enumerate(passages)
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_TEMPLATE.format(
            passages=passage_text, question=question
        )},
    ]
