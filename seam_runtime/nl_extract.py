"""Opt-in LLM rich extractor for the MIRL compiler (SEAM spec §3.2, Stage 4).

The deterministic floor in ``nl.py`` is faithful but shallow: it grounds a
subject and preserves the verbatim proposition, but assigns no structured
relation and misses lowercase common-noun entities (``billing service``). This
module adds an OPT-IN extractor that asks a LOCAL model (Ollama, free) for real
(subject, relation, object) triples and entities, then passes them through a
GROUNDING GATE so the spec's "never fabricate" guarantee (§3.2 + §8) holds even
when the model hallucinates: a triple or entity is kept only when every span it
uses is drawn verbatim from the input. Anything ungrounded is dropped, and a
proposition with no surviving grounded claim falls back to the floor.

This is opt-in by construction. CI cannot reach a local model, so the
deterministic floor stays the default and the only CI-measured behavior;
determinism (§29.1) is the floor's guarantee, not the LLM path's (an LLM is at
best best-effort deterministic at temperature 0). Enable via
``compile_nl(text, extractor=OllamaExtractor(...))`` or, in production, the
``SEAM_NL_EXTRACTOR=ollama`` environment switch (see ``extractor_from_env``).
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

_WORD_RE = re.compile(r"[a-z0-9]+")
# Function words that do not need to be grounded for a phrase to count as drawn
# from the text (mirrors the fidelity harness's stopword handling).
_STOPWORDS = frozenset({
    "a", "an", "the", "of", "to", "in", "on", "at", "by", "with", "for",
    "is", "are", "was", "were", "be", "and", "or", "that", "this", "it",
    "as", "from", "into", "my", "our", "their", "his", "her", "its",
})


def _content_tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS)


@dataclass(frozen=True)
class ExtractedEntity:
    name: str
    entity_type: str = "entity"


@dataclass(frozen=True)
class ExtractedClaim:
    subject: str
    relation: str
    obj: str


@dataclass(frozen=True)
class Extraction:
    """Grounded entities + claims for one proposition."""

    entities: tuple[ExtractedEntity, ...] = ()
    claims: tuple[ExtractedClaim, ...] = ()

    def is_empty(self) -> bool:
        return not self.entities and not self.claims


@runtime_checkable
class Extractor(Protocol):
    """A per-proposition rich extractor. Returns a GROUNDED ``Extraction`` (all
    spans verbatim from ``text``); an empty result means "fall back to the floor"."""

    def extract(self, text: str) -> Extraction: ...


_SYSTEM = (
    "You extract structured facts from ONE sentence. Hard rules: every entity "
    "name, claim subject, claim relation and claim object MUST be a contiguous "
    "span of words copied VERBATIM from the sentence. Never invent, rephrase, or "
    "normalize a word. The relation is the verb or preposition exactly as written. "
    "Output JSON only."
)
_EXAMPLE_IN = "Akira teaches an evening pottery class at the community center."
_EXAMPLE_OUT = json.dumps(
    {
        "entities": [{"name": "Akira", "type": "person"}, {"name": "community center", "type": "place"}],
        "claims": [{"subject": "Akira", "relation": "teaches", "object": "an evening pottery class"}],
    }
)
_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "type": {"type": "string"}},
                "required": ["name", "type"],
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"subject": {"type": "string"}, "relation": {"type": "string"}, "object": {"type": "string"}},
                "required": ["subject", "relation", "object"],
            },
        },
    },
    "required": ["entities", "claims"],
}


@dataclass
class OllamaExtractor:
    """Calls a local Ollama model for grounded (S, R, O) triples + entities.

    Network-free of any cloud: talks to a local Ollama HTTP endpoint only. Uses
    ``urllib`` (no new dependency). Any failure (model down, bad JSON, timeout)
    returns an empty ``Extraction`` so the caller falls back to the floor."""

    model: str = field(default_factory=lambda: os.environ.get("SEAM_OLLAMA_MODEL", "qwen2.5:3b"))
    host: str = field(default_factory=lambda: os.environ.get("SEAM_OLLAMA_HOST", "http://127.0.0.1:11434"))
    timeout: float = 120.0
    temperature: float = 0.0
    seed: int = 7
    num_ctx: int = 2048

    def _generate(self, text: str) -> dict:
        prompt = f"{_SYSTEM}\n\nEXAMPLE\nSentence: {_EXAMPLE_IN}\nJSON: {_EXAMPLE_OUT}\n\nNOW\nSentence: {text}\nJSON:"
        body = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": _SCHEMA,
                "options": {"temperature": self.temperature, "seed": self.seed, "num_ctx": self.num_ctx},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.host.rstrip('/')}/api/generate", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:  # noqa: S310 (local loopback only)
            payload = json.loads(response.read())
        return json.loads(payload["response"])

    def extract(self, text: str) -> Extraction:
        try:
            raw = self._generate(text)
        except Exception:
            return Extraction()
        return ground_extraction(raw, text)


def ground_extraction(raw: dict, text: str) -> Extraction:
    """Filter a model's raw output against ``text`` — the fabrication firewall.

    Keep an entity only when its content tokens are a subset of the text's;
    keep a claim only when its subject, relation, AND object are each grounded.
    Empty/malformed input yields an empty Extraction (-> floor fallback)."""
    allowed = _content_tokens(text)
    if not isinstance(raw, dict):
        return Extraction()

    def grounded(value: object) -> bool:
        if not isinstance(value, str) or not value.strip():
            return False
        want = _content_tokens(value)
        return bool(want) and want <= allowed

    entities: list[ExtractedEntity] = []
    seen_ent: set[str] = set()
    for item in raw.get("entities", []) or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if grounded(name) and name.lower() not in seen_ent:
            seen_ent.add(name.lower())
            etype = str(item.get("type", "entity")).strip() or "entity"
            entities.append(ExtractedEntity(name=name, entity_type=etype))

    claims: list[ExtractedClaim] = []
    seen_clm: set[tuple[str, str, str]] = set()
    for item in raw.get("claims", []) or []:
        if not isinstance(item, dict):
            continue
        subject = str(item.get("subject", "")).strip()
        relation = str(item.get("relation", "")).strip()
        obj = str(item.get("object", "")).strip()
        if grounded(subject) and grounded(obj) and relation and (_content_tokens(relation) <= allowed):
            key = (subject.lower(), relation.lower(), obj.lower())
            if key not in seen_clm:
                seen_clm.add(key)
                claims.append(ExtractedClaim(subject=subject, relation=relation, obj=obj))

    return Extraction(entities=tuple(entities), claims=tuple(claims))


def extractor_from_env() -> Extractor | None:
    """Return an opt-in extractor if ``SEAM_NL_EXTRACTOR`` selects one, else None
    (the deterministic floor). Only ``ollama`` is wired today."""
    choice = os.environ.get("SEAM_NL_EXTRACTOR", "").strip().lower()
    if choice == "ollama":
        return OllamaExtractor()
    return None
