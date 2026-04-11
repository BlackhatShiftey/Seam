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
