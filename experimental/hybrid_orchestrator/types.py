from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from seam_runtime.mirl import MIRLRecord


class QueryIntent(str, Enum):
    STRUCTURED = "structured"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass
class QueryFilters:
    ids: list[str] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)
    namespace: str | None = None
    scope: str | None = None
    predicate: str | None = None
    subject: str | None = None
    object_text: str | None = None

    def matches(self, record: MIRLRecord) -> bool:
        if self.ids and record.id not in self.ids:
            return False
        if self.kinds and record.kind.value not in self.kinds:
            return False
        if self.namespace and record.ns != self.namespace:
            return False
        if self.scope and record.scope != self.scope:
            return False
        if self.predicate and str(record.attrs.get("predicate", "")).lower() != self.predicate.lower():
            return False
        if self.subject and str(record.attrs.get("subject", "")).lower() != self.subject.lower():
            return False
        if self.object_text:
            value = str(record.attrs.get("object", "")).lower()
            if self.object_text.lower() not in value:
                return False
        return True

    def active(self) -> bool:
        return any(
            [
                self.ids,
                self.kinds,
                self.namespace,
                self.scope,
                self.predicate,
                self.subject,
                self.object_text,
            ]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ids": list(self.ids),
            "kinds": list(self.kinds),
            "namespace": self.namespace,
            "scope": self.scope,
            "predicate": self.predicate,
            "subject": self.subject,
            "object_text": self.object_text,
        }


@dataclass
class RetrievalLeg:
    name: str
    limit: int
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "limit": self.limit, "rationale": self.rationale}


@dataclass
class RetrievalPlan:
    query: str
    normalized_query: str
    intent: QueryIntent
    filters: QueryFilters
    legs: list[RetrievalLeg]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "normalized_query": self.normalized_query,
            "intent": self.intent.value,
            "filters": self.filters.to_dict(),
            "legs": [leg.to_dict() for leg in self.legs],
        }


@dataclass
class LegHit:
    leg: str
    record: MIRLRecord
    score: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "leg": self.leg,
            "record": self.record.to_dict(),
            "score": round(self.score, 6),
            "reasons": list(self.reasons),
        }


@dataclass
class HybridCandidate:
    record: MIRLRecord
    score: float
    sources: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "score": round(self.score, 6),
            "sources": {key: round(value, 6) for key, value in self.sources.items()},
            "reasons": list(self.reasons),
        }


@dataclass
class HybridSearchResult:
    query: str
    normalized_query: str
    intent: QueryIntent
    candidates: list[HybridCandidate]
    trace: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "normalized_query": self.normalized_query,
            "intent": self.intent.value,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "trace": self.trace,
        }


@dataclass
class RAGResult:
    query: str
    backend: str
    candidate_ids: list[str]
    pack: dict[str, Any]
    trace: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "backend": self.backend,
            "candidate_ids": list(self.candidate_ids),
            "pack": self.pack,
            "trace": self.trace,
        }
