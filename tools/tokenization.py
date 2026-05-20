from __future__ import annotations

import math
from functools import lru_cache

CANONICAL_TOKENIZER = "cl100k_base"
FALLBACK_TOKENIZER = "char4_approx"


def count_tokens(text: str) -> int:
    count, _ = count_tokens_with_label(text)
    return count


def count_tokens_with_label(text: str) -> tuple[int, str]:
    if not text:
        return 0, CANONICAL_TOKENIZER
    encoder = _load_encoder()
    if encoder is None:
        return math.ceil(len(text.encode("utf-8")) / 4), FALLBACK_TOKENIZER
    return len(encoder.encode(text)), CANONICAL_TOKENIZER


@lru_cache(maxsize=1)
def _load_encoder():
    try:
        import tiktoken
    except ImportError:
        return None
    try:
        return tiktoken.get_encoding(CANONICAL_TOKENIZER)
    except Exception:
        return None
