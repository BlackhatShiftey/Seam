from __future__ import annotations

import hashlib
import json
import math
import os
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class EmbeddingModel(Protocol):
    name: str
    dimension: int

    def embed(self, text: str) -> list[float]:
        ...


@dataclass
class HashEmbeddingModel:
    name: str = "hash-bow-v1"
    dimension: int = 64

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in _tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        return _normalize(vector)


@dataclass
class OpenAICompatibleEmbeddingModel:
    model: str
    api_key_env: str = "OPENAI_API_KEY"
    base_url: str = "https://api.openai.com/v1/embeddings"
    name: str = ""
    dimension: int = 1536

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"openai-compatible:{self.model}"

    def embed(self, text: str) -> list[float]:
        api_key = os.environ.get(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key in {self.api_key_env}")
        body = json.dumps({"model": self.model, "input": text}).encode("utf-8")
        request = urllib.request.Request(
            self.base_url,
            data=body,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        vector = payload["data"][0]["embedding"]
        self.dimension = len(vector)
        return vector


def default_embedding_model() -> EmbeddingModel:
    provider = os.environ.get("SEAM_EMBEDDING_PROVIDER", "hash").lower()
    if provider == "openai":
        model_name = os.environ.get("SEAM_EMBEDDING_MODEL", "text-embedding-3-small")
        base_url = os.environ.get("SEAM_EMBEDDING_BASE_URL", "https://api.openai.com/v1/embeddings")
        api_key_env = os.environ.get("SEAM_EMBEDDING_API_KEY_ENV", "OPENAI_API_KEY")
        return OpenAICompatibleEmbeddingModel(model=model_name, base_url=base_url, api_key_env=api_key_env)
    return HashEmbeddingModel()


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]


def _tokens(text: str) -> list[str]:
    return [part for part in text.lower().replace("\n", " ").split(" ") if part]
