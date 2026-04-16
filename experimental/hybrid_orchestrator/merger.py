from __future__ import annotations

from .types import HybridCandidate, LegHit


def merge_hits(grouped_hits: list[list[LegHit]], limit: int) -> list[HybridCandidate]:
    merged: dict[str, HybridCandidate] = {}
    for hits in grouped_hits:
        for hit in hits:
            candidate = merged.get(hit.record.id)
            if candidate is None:
                candidate = HybridCandidate(record=hit.record, score=0.0)
                merged[hit.record.id] = candidate
            candidate.sources[hit.leg] = max(candidate.sources.get(hit.leg, 0.0), hit.score)
            candidate.reasons.extend(f"{hit.leg}:{reason}" for reason in hit.reasons)

    for candidate in merged.values():
        overlap_bonus = 0.15 * max(len(candidate.sources) - 1, 0)
        candidate.score = sum(candidate.sources.values()) + overlap_bonus
        candidate.reasons = list(dict.fromkeys(candidate.reasons))

    return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:limit]
