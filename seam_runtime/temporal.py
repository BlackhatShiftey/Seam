from __future__ import annotations

import re
from datetime import datetime, timedelta
from math import exp

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
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
_RELATIVE_RE = re.compile(
    r"\b(?P<count>\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"(?P<unit>days?|weeks?|months?|years?)\s+"
    r"(?P<direction>ago|before|after|later)\b",
    re.IGNORECASE,
)
_NAMED_RELATIVE_OFFSETS = {
    "yesterday": -1,
    "today": 0,
    "tomorrow": 1,
    "last week": -7,
    "this week": 0,
    "next week": 7,
    "last month": -30,
    "this month": 0,
    "next month": 30,
    "last year": -365,
    "this year": 0,
    "next year": 365,
}


def detect_temporal_tokens(question: str) -> list[str]:
    return [m.group(0) for m in _TEMPORAL_RE.finditer(question)]


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None


def parse_temporal_reference(question: str, *, anchor: datetime | None = None) -> datetime | None:
    """Parse one temporal reference from a question.

    Absolute ISO dates do not need an anchor. Relative dates use the supplied
    anchor, typically the first timestamp in the conversation scope.
    """
    tokens = detect_temporal_tokens(question)
    for token in tokens:
        parsed = parse_iso(token)
        if parsed is not None:
            return parsed
    if anchor is None:
        return None

    normalized = question.lower()
    for phrase, days in _NAMED_RELATIVE_OFFSETS.items():
        if re.search(rf"\b{re.escape(phrase)}\b", normalized):
            return anchor + timedelta(days=days)

    match = _RELATIVE_RE.search(question)
    if match is None:
        return None
    count = _parse_count(match.group("count"))
    unit_days = _unit_days(match.group("unit"))
    direction = match.group("direction").lower()
    days = count * unit_days
    if direction in {"ago", "before"}:
        days = -days
    return anchor + timedelta(days=days)


def temporal_distance_score(
    question_date_ref: datetime | None,
    candidate_timestamp: datetime | None,
    decay_constant: float = 30.0,
) -> float:
    if question_date_ref is None or candidate_timestamp is None:
        return 0.0
    if decay_constant <= 0:
        raise ValueError("decay_constant must be positive")
    delta_days = abs((candidate_timestamp - question_date_ref).total_seconds()) / 86400.0
    return exp(-delta_days / decay_constant)


def _parse_count(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return _NUMBER_WORDS[value.lower()]


def _unit_days(unit: str) -> int:
    normalized = unit.lower().rstrip("s")
    return {
        "day": 1,
        "week": 7,
        "month": 30,
        "year": 365,
    }[normalized]
