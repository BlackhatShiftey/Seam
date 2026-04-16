from __future__ import annotations

import re

from .types import QueryFilters, QueryIntent, RetrievalLeg, RetrievalPlan


FILTER_PATTERN = re.compile(r"\b(?P<key>id|kind|ns|scope|predicate|subject|object):(?P<value>[^\s]+)")


def build_plan(query: str, scope: str | None = None, budget: int = 5) -> RetrievalPlan:
    filters = _extract_filters(query, scope=scope)
    normalized_query = _strip_filters(query)
    intent = _classify_intent(filters, normalized_query)
    leg_limit = max(budget * 2, 5) if intent == QueryIntent.HYBRID else max(budget, 5)
    legs: list[RetrievalLeg] = []

    if intent in {QueryIntent.STRUCTURED, QueryIntent.HYBRID}:
        legs.append(RetrievalLeg(name="sql", limit=leg_limit, rationale="Apply explicit field filters and lexical matching"))
    if intent in {QueryIntent.SEMANTIC, QueryIntent.HYBRID}:
        legs.append(RetrievalLeg(name="vector", limit=leg_limit, rationale="Use embedding similarity for semantic recall"))

    return RetrievalPlan(
        query=query,
        normalized_query=normalized_query,
        intent=intent,
        filters=filters,
        legs=legs,
    )


def _extract_filters(query: str, scope: str | None = None) -> QueryFilters:
    filters = QueryFilters(scope=scope)
    for match in FILTER_PATTERN.finditer(query):
        key = match.group("key")
        value = match.group("value")
        if key == "id":
            filters.ids.extend(_split_csv(value))
        elif key == "kind":
            filters.kinds.extend(item.upper() for item in _split_csv(value))
        elif key == "ns":
            filters.namespace = value
        elif key == "scope":
            filters.scope = value
        elif key == "predicate":
            filters.predicate = value
        elif key == "subject":
            filters.subject = value
        elif key == "object":
            filters.object_text = value
    return filters


def _strip_filters(query: str) -> str:
    stripped = FILTER_PATTERN.sub(" ", query)
    return " ".join(part for part in stripped.split() if part)


def _classify_intent(filters: QueryFilters, normalized_query: str) -> QueryIntent:
    has_filters = filters.active()
    semantic_terms = len(normalized_query.split())
    if has_filters and semantic_terms:
        return QueryIntent.HYBRID
    if has_filters:
        return QueryIntent.STRUCTURED
    return QueryIntent.SEMANTIC


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]
