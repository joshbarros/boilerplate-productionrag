"""Offline / deterministic eval helpers — no live LLM or paid APIs.

Uses a hash embedder (stable, local) and a passage-grounded answerer that
emits cite-or-refuse JSON so the full service path can be exercised in CI.
"""

from __future__ import annotations

import hashlib
import json
import math
import re

from ragcore.generation.router import GenerationResult

_TOKEN = re.compile(r"[a-zà-ÿ0-9]{2,}", re.IGNORECASE)

# Common EN + PT stopwords — offline answers require content-term overlap.
_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "of",
    "to",
    "in",
    "on",
    "for",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "that",
    "this",
    "these",
    "those",
    "with",
    "as",
    "by",
    "from",
    "at",
    "it",
    "its",
    "what",
    "which",
    "who",
    "whom",
    "how",
    "when",
    "where",
    "why",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "may",
    "might",
    "must",
    "will",
    "shall",
    "i",
    "you",
    "he",
    "she",
    "we",
    "they",
    "me",
    "my",
    "your",
    "our",
    "their",
    "de",
    "da",
    "do",
    "das",
    "dos",
    "em",
    "no",
    "na",
    "nos",
    "nas",
    "um",
    "uma",
    "uns",
    "umas",
    "os",
    "as",
    "o",
    "a",
    "e",
    "ou",
    "que",
    "qual",
    "quais",
    "como",
    "quando",
    "onde",
    "por",
    "para",
    "com",
    "sem",
    "sobre",
    "entre",
    "ao",
    "aos",
    "à",
    "às",
    "se",
    "ser",
    "são",
    "foi",
    "era",
    "tem",
    "têm",
    "há",
    "não",
    "sim",
    "mais",
    "menos",
    "muito",
    "muitos",
    "sua",
    "seu",
    "suas",
    "seus",
}


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def content_terms(text: str) -> set[str]:
    return {t for t in tokenize(text) if t not in _STOP and len(t) >= 3}


class HashEmbedder:
    """Deterministic bag-of-hashed-tokens embedder (no network)."""

    model_id = "hash-embedder-v1"
    dims = 64

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def _vec(self, text: str) -> list[float]:
        vec = [0.0] * self.dims
        for tok in tokenize(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % self.dims] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]


def offline_generate_answer(
    question: str,
    passages: list[dict],
    model_override: str | None = None,
    prompt_builder=None,
) -> GenerationResult:
    """Answer only on strong content-term overlap with retrieved passages."""
    q_terms = content_terms(question)
    if not q_terms or not passages:
        return _not_found()

    best: dict | None = None
    best_score = 0.0
    best_overlap: set[str] = set()
    for p in passages:
        p_terms = content_terms(p.get("text", ""))
        if not p_terms:
            continue
        overlap = q_terms & p_terms
        score = len(overlap) / len(q_terms)
        if score > best_score:
            best_score = score
            best = p
            best_overlap = overlap

    # Require real topical overlap: ≥2 content terms and ≥30% of question terms.
    if best is None or len(best_overlap) < 2 or best_score < 0.30:
        return _not_found()

    # Use a large verbatim body so keyword_hints in the golden set are likely hit.
    body = " ".join(best["text"].split())
    excerpt = body[:160] if len(body) >= 12 else body
    # Prefer a window covering an overlapping content term
    for tok in best_overlap:
        idx = body.lower().find(tok)
        if idx >= 0:
            start = max(0, idx - 30)
            excerpt = body[start : start + 160]
            break

    payload = {
        "status": "answered",
        "answer": body[:800],
        "citations": [
            {
                "chunk_id": best["chunk_id"],
                "page": best.get("page", 0),
                "excerpt": excerpt,
            }
        ],
    }
    return GenerationResult(
        text=json.dumps(payload),
        model_used="offline/deterministic",
        prompt_tokens=0,
        completion_tokens=0,
        latency_ms=1,
    )


def _not_found() -> GenerationResult:
    return GenerationResult(
        text=json.dumps(
            {"status": "not_found", "answer": None, "citations": []}
        ),
        model_used="offline/deterministic",
        prompt_tokens=0,
        completion_tokens=0,
        latency_ms=1,
    )
