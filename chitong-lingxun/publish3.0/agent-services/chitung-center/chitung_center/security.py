from __future__ import annotations

import re


PHONE_RE = re.compile(r"(?<!\d)(?:\+?852[-\s]?)?\d{4}[-\s]?\d{4}(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
HKID_RE = re.compile(r"\b[A-Z]{1,2}\d{6}\([0-9A]\)\b", re.IGNORECASE)


def sanitize_for_llm(text: str) -> str:
    """Remove common personal identifiers before cloud LLM calls."""
    sanitized = PHONE_RE.sub("[PHONE]", text)
    sanitized = EMAIL_RE.sub("[EMAIL]", sanitized)
    sanitized = HKID_RE.sub("[HKID]", sanitized)
    return sanitized


def compact_context(text: str, max_chars: int = 4000) -> str:
    stripped = " ".join(text.split())
    if len(stripped) <= max_chars:
        return stripped
    return stripped[: max_chars - 20] + "...[TRUNCATED]"
