from __future__ import annotations

import re
from datetime import datetime, timedelta

_MONTH = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_DATE_PATTERNS = [
    rf"\b({_MONTH})\s+\d{{4}}\b",
    r"\b\d{1,2}\s+" + _MONTH + r"\s+\d{4}\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    r"\b(?:last|this|next)\s+(?:week|month|year)\b",
    r"\b(?:yesterday|today|tomorrow)\b",
    r"\b\d+\s+(?:days?|weeks?|months?|years?)\s+(?:ago|after|before|later)\b",
]
_TEMPORAL_RE = re.compile("|".join(_DATE_PATTERNS), re.IGNORECASE)


def detect_temporal_tokens(question: str) -> list[str]:
    return [m.group(0) for m in _TEMPORAL_RE.finditer(question)]


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts[: len(fmt) + 4], fmt)
        except ValueError:
            continue
    return None
