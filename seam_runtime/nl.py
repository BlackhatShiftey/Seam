from __future__ import annotations

import re
from collections import Counter

from .mirl import IRBatch, MIRLRecord, RecordKind, Status


STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "it", "of", "on", "or", "that", "the", "this", "to", "we", "with", "without"}
SCOPE_PATTERNS = {
    "db": ["database", "databases", "db", "sql", "sqlite", "postgres"],
    "rag": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    "ctx": ["context window", "context windows", "context", "prompt window"],
    "cli": ["cli", "command line", "terminal", "shell"],
}
PRINCIPLE_PATTERNS = {
    "simplest_recoverable_form": ["simplest state possible", "simplest form possible", "simplest recoverable state", "simplest recoverable form"],
    "loss_minimization": ["without losing any information", "without losing meaning", "lossless"],
    "durable_memory": ["permanently remember", "permanent memory", "durable memory", "long-term memory"],
}


def compile_nl(raw_text: str, source_ref: str = "local://input", ns: str = "local.default", scope: str = "thread") -> IRBatch:
    raw_id = "raw:1"
    span_id = "span:1"
    prov_id = "prov:compile:1"
    user_id = "ent:user:local"
    project_id = "ent:project:seam"
    goal = _extract_goal(raw_text)
    scope_values = _detect_scope(raw_text)
    principles = _detect_principles(raw_text)
    constraints = _detect_constraints(raw_text)
    translator = any(token in raw_text.lower() for token in ("translate", "translator", "natural language"))

    records = [
        MIRLRecord(id=raw_id, kind=RecordKind.RAW, ns=ns, scope=scope, status=Status.OBSERVED, attrs={"source_ref": source_ref, "content": raw_text, "media_type": "text/plain"}),
        MIRLRecord(id=span_id, kind=RecordKind.SPAN, ns=ns, scope=scope, status=Status.OBSERVED, attrs={"raw_id": raw_id, "start": 0, "end": len(raw_text)}),
        MIRLRecord(id=prov_id, kind=RecordKind.PROV, ns=ns, scope=scope, status=Status.OBSERVED, attrs={"entity": raw_id, "activity": "compile_nl", "agent": "system.nl"}),
        MIRLRecord(id=user_id, kind=RecordKind.ENT, ns=ns, scope=scope, attrs={"entity_type": "user", "label": "local_user"}),
        MIRLRecord(id=project_id, kind=RecordKind.ENT, ns=ns, scope=scope, attrs={"entity_type": "project", "label": _infer_project_name(raw_text)}),
    ]

    claim_index = 1
    state_fields: dict[str, object] = {}

    def add_claim(predicate: str, obj: object, confidence: float = 0.92) -> None:
        nonlocal claim_index
        records.append(
            MIRLRecord(
                id=f"clm:{claim_index}",
                kind=RecordKind.CLM,
                ns=ns,
                scope=scope,
                conf=confidence,
                prov=[prov_id],
                evidence=[span_id],
                attrs={"subject": project_id, "predicate": predicate, "object": obj},
            )
        )
        claim_index += 1

    add_claim("goal", goal)
    state_fields["goal"] = goal
    if scope_values:
        add_claim("scope", scope_values)
        state_fields["scope"] = scope_values
    for principle in principles:
        add_claim("principle", principle, 0.88)
    if principles:
        state_fields["principle"] = principles
    for constraint in constraints:
        add_claim("constraint", constraint, 0.9)
    if constraints:
        state_fields["constraint"] = constraints if len(constraints) > 1 else constraints[0]
    if translator:
        add_claim("translator", "nl_ir_pack_roundtrip", 0.95)
        state_fields["translator"] = "nl_ir_pack_roundtrip"

    records.append(
        MIRLRecord(
            id=f"sta:{project_id}",
            kind=RecordKind.STA,
            ns=ns,
            scope=scope,
            conf=0.9,
            prov=[prov_id],
            evidence=[span_id],
            attrs={"target": project_id, "fields": state_fields},
        )
    )
    return IRBatch(records)


def suggest_symbols(batch: IRBatch, min_frequency: int = 2) -> list[MIRLRecord]:
    counter: Counter[str] = Counter()
    for record in batch.records:
        for key in ("predicate", "entity_type"):
            value = record.attrs.get(key)
            if isinstance(value, str) and len(value) > 8:
                counter[value] += 1
    symbols: list[MIRLRecord] = []
    for index, (value, frequency) in enumerate(counter.items(), start=1):
        if frequency < min_frequency:
            continue
        short = "".join(part[0] for part in value.split("_"))[:6] or f"sym{index}"
        symbols.append(MIRLRecord(id=f"sym:auto:{index}", kind=RecordKind.SYM, status=Status.INFERRED, conf=0.7, attrs={"symbol": short, "expansion": value, "frequency": frequency}))
    return symbols


def _extract_goal(text: str) -> str:
    lowered = text.lower()
    patterns = [
        r"(?:want|wants|need|needs)\s+to\s+([^.!?]+)",
        r"(?:want|wants|need|needs)\s+(?:a|an)?\s*([^.!?]+)",
        r"(?:goal|goals)\s+(?:is|are)\s+to\s+([^.!?]+)",
        r"(?:design|build|create)\s+([^.!?]+)",
        r"(?:should)\s+([^.!?]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            phrase = re.split(r"\b(?:for|across|with|that|which|and it should|it should)\b", match.group(1), maxsplit=1)[0]
            return _normalize_phrase(phrase)
    return _normalize_phrase(text)


def _detect_scope(text: str) -> list[str]:
    lowered = text.lower()
    return [code for code, patterns in SCOPE_PATTERNS.items() if any(pattern in lowered for pattern in patterns)]


def _detect_principles(text: str) -> list[str]:
    lowered = text.lower()
    return [code for code, patterns in PRINCIPLE_PATTERNS.items() if any(pattern in lowered for pattern in patterns)]


def _detect_constraints(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    if any(fragment in lowered for fragment in ("without losing", "preserve meaning", "lossless")):
        found.append("preserve_meaning")
    if "permanent" in lowered or "durable" in lowered:
        found.append("persistent_memory")
    return found


def _normalize_phrase(text: str) -> str:
    words = [word for word in re.findall(r"[A-Za-z0-9_:-]+", text.lower()) if word not in STOPWORDS]
    return "_".join(words[:10]) if words else "unspecified"


def _infer_project_name(text: str) -> str:
    patterns = [r"(?:called|named)\s+([A-Z][A-Za-z0-9_-]{1,20})", r'"([A-Z][A-Za-z0-9_-]{1,20})"', r"'([A-Z][A-Za-z0-9_-]{1,20})'"]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return "SEAM"
