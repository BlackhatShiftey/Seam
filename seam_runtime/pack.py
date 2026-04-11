from __future__ import annotations

import json
from typing import Iterable

from .mirl import IRBatch, MIRLRecord, Pack, RecordKind, token_count
from .symbols import build_symbol_maps


def pack_records(records: Iterable[MIRLRecord], lens: str = "general", budget: int = 512, mode: str = "context", profile: str = "default", namespace: str | None = None) -> Pack:
    ordered = sorted(records, key=lambda record: record.id)
    refs = [record.id for record in ordered]
    pack_id = f"pack:{mode}:{len(refs)}:{abs(hash((tuple(refs), lens, budget))) % 100000}"
    expansion_to_symbol, _ = build_symbol_maps(ordered, namespace=namespace)

    if mode == "exact":
        payload = {"records": [record.to_dict() for record in ordered]}
        body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return Pack(pack_id=pack_id, mode=mode, lens=lens, refs=refs, payload=payload, budget=budget, reversible=True, token_cost=token_count(body), profile=profile)

    if mode == "narrative":
        summary = _narrative_summary(ordered, lens=lens)
        return Pack(pack_id=pack_id, mode=mode, lens=lens, refs=refs, payload={"summary": summary}, budget=budget, reversible=False, token_cost=token_count(summary), profile=profile)

    entries = [{"id": record.id, "kind": record.kind.value, "signal": _compact_signal(_signal_for_record(record), expansion_to_symbol), "prov": record.prov, "evidence": record.evidence} for record in ordered]
    payload = {"lens": lens, "entries": entries[:budget], "refs": refs, "symbols": {symbol: expansion for expansion, symbol in expansion_to_symbol.items()}}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return Pack(pack_id=pack_id, mode="context", lens=lens, refs=refs, payload=payload, budget=budget, reversible=False, token_cost=token_count(body), profile=profile)


def unpack_exact_pack(pack: Pack) -> IRBatch:
    if pack.mode != "exact":
        raise ValueError("Only exact packs can be unpacked into IRBatch")
    return IRBatch.from_json(pack.payload["records"])


def pack_record(pack: Pack, ns: str = "local.default", scope: str = "project") -> MIRLRecord:
    return pack.to_record(ns=ns, scope=scope)


def score_pack(pack: Pack, records: Iterable[MIRLRecord]) -> dict[str, float | int | str]:
    ordered = sorted(records, key=lambda record: record.id)
    record_ids = {record.id for record in ordered}
    ref_coverage = len(record_ids & set(pack.refs)) / max(len(record_ids), 1)
    source_token_cost = _records_token_cost(ordered)
    budget_fit = 1.0 if pack.budget <= 0 or pack.token_cost <= pack.budget else pack.budget / max(pack.token_cost, 1)
    compression_ratio = source_token_cost / max(pack.token_cost, 1) if source_token_cost else 1.0
    compression_score = min(compression_ratio, 1.0)

    if pack.mode == "exact":
        reversibility = 1.0 if unpack_exact_pack(pack).to_json() == IRBatch(ordered).to_json() else 0.0
        provenance_retention = 1.0
        evidence_retention = 1.0
        traceability = 1.0
        overall = (0.50 * reversibility) + (0.20 * ref_coverage) + (0.15 * provenance_retention) + (0.15 * evidence_retention)
    elif pack.mode == "context":
        entries = _context_entries_by_id(pack)
        provenance_retention = _list_field_retention(ordered, entries, "prov")
        evidence_retention = _list_field_retention(ordered, entries, "evidence")
        reversibility = 0.0
        traceability = (ref_coverage + provenance_retention + evidence_retention) / 3
        overall = (0.40 * traceability) + (0.25 * budget_fit) + (0.20 * compression_score) + (0.15 * ref_coverage)
    else:
        provenance_retention = 0.0
        evidence_retention = 0.0
        reversibility = 0.0
        traceability = ref_coverage
        narrative_density = 1.0 if str(pack.payload.get("summary", "")).strip() else 0.0
        overall = (0.35 * ref_coverage) + (0.25 * budget_fit) + (0.20 * compression_score) + (0.20 * narrative_density)

    return {
        "mode": pack.mode,
        "record_count": len(ordered),
        "token_cost": pack.token_cost,
        "budget": pack.budget,
        "source_token_cost": source_token_cost,
        "ref_coverage": round(ref_coverage, 6),
        "provenance_retention": round(provenance_retention, 6),
        "evidence_retention": round(evidence_retention, 6),
        "traceability": round(traceability, 6),
        "reversibility": round(reversibility, 6),
        "budget_fit": round(budget_fit, 6),
        "compression_ratio": round(compression_ratio, 6),
        "overall": round(overall, 6),
    }


def _signal_for_record(record: MIRLRecord) -> dict[str, object]:
    attrs = record.attrs
    if record.kind == RecordKind.CLM:
        return {"subject": attrs.get("subject"), "predicate": attrs.get("predicate"), "object": attrs.get("object")}
    if record.kind == RecordKind.STA:
        return {"target": attrs.get("target"), "fields": attrs.get("fields")}
    if record.kind == RecordKind.EVT:
        return {"actor": attrs.get("actor"), "action": attrs.get("action"), "object": attrs.get("object")}
    if record.kind == RecordKind.REL:
        return {"src": attrs.get("src"), "predicate": attrs.get("predicate"), "dst": attrs.get("dst")}
    return attrs


def _narrative_summary(records: list[MIRLRecord], lens: str) -> str:
    claims = [record for record in records if record.kind == RecordKind.CLM]
    states = [record for record in records if record.kind == RecordKind.STA]
    if states:
        fields = states[0].attrs.get("fields", {})
        return f"[{lens}] " + "; ".join(f"{key}={value}" for key, value in fields.items())
    if claims:
        return f"[{lens}] " + "; ".join(f"{record.attrs.get('subject')} {record.attrs.get('predicate')} {record.attrs.get('object')}" for record in claims)
    return f"[{lens}] No narrative context available."


def _compact_signal(value: object, expansion_to_symbol: dict[str, str]) -> object:
    if isinstance(value, str):
        return expansion_to_symbol.get(value, value)
    if isinstance(value, list):
        return [_compact_signal(item, expansion_to_symbol) for item in value]
    if isinstance(value, dict):
        compacted: dict[str, object] = {}
        for key, item in value.items():
            compacted_key = expansion_to_symbol.get(key, key)
            compacted[compacted_key] = _compact_signal(item, expansion_to_symbol)
        return compacted
    return value


def _context_entries_by_id(pack: Pack) -> dict[str, dict[str, object]]:
    if pack.mode != "context":
        return {}
    entries = pack.payload.get("entries", [])
    return {str(entry.get("id")): entry for entry in entries if isinstance(entry, dict) and entry.get("id")}


def _list_field_retention(records: list[MIRLRecord], entries: dict[str, dict[str, object]], field: str) -> float:
    if not records:
        return 1.0
    scores: list[float] = []
    for record in records:
        expected = list(getattr(record, field))
        if not expected:
            scores.append(1.0)
            continue
        entry = entries.get(record.id)
        if entry is None:
            scores.append(0.0)
            continue
        scores.append(1.0 if list(entry.get(field, [])) == expected else 0.0)
    return sum(scores) / len(scores)


def _records_token_cost(records: list[MIRLRecord]) -> int:
    return sum(token_count(json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))) for record in records)
