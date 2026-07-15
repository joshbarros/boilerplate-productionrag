"""PII masking — redact CPF/CNPJ/phone/email before external LLM calls (FR-015)."""

from __future__ import annotations

import re

# Brazilian CPF: 000.000.000-00 or 11 digits
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
# CNPJ: 00.000.000/0000-00
_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
# Email
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# Phone (BR-ish + generic international)
_PHONE = re.compile(
    r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,3}\)?[\s-]?)?\d{4,5}[\s-]?\d{4}\b"
)


def mask_pii(text: str) -> str:
    """Return a copy of ``text`` with common PII patterns replaced by tokens."""
    if not text:
        return text
    out = _EMAIL.sub("[EMAIL]", text)
    out = _CNPJ.sub("[CNPJ]", out)
    out = _CPF.sub("[CPF]", out)
    out = _PHONE.sub("[PHONE]", out)
    return out
