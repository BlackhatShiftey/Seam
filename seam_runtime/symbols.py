from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .mirl import IRBatch, MIRLRecord, RecordKind, Status


@dataclass
class SymbolCandidate:
    expansion: str
    symbol: str
    family: str
    namespace: str
    frequency: int
    ambiguity: float


CORE_SYMBOLS = {
    ("predicate", "goal"): "gl",
    ("predicate", "scope"): "sc",
    ("predicate", "principle"): "pr",
    ("predicate", "constraint"): "cs",
    ("predicate", "translator"): "tr",
    ("boolean", "yes"): "1",
    ("boolean", "true"): "1",
    ("boolean", "no"): "0",
    ("boolean", "false"): "0",
    ("status", "asserted"): "a",
    ("status", "observed"): "o",
    ("status", "inferred"): "i",
    ("status", "hypothetical"): "h",
    ("status", "contradicted"): "x",
    ("status", "superseded"): "s",
    ("status", "deprecated"): "d",
    ("status", "deleted_soft"): "z",
    ("time", "today"): "tdy",
    ("time", "tomorrow"): "tom",
    ("time", "yesterday"): "yst",
    ("generic", "memory"): "mem",
    ("generic", "translator"): "xlat",
    ("generic", "database"): "db",
    ("generic", "context"): "ctx",
}


def propose_symbols(batch: IRBatch, min_frequency: int = 2) -> list[MIRLRecord]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    expansions_by_symbol: dict[str, set[str]] = defaultdict(set)
    family_by_expansion: dict[str, str] = {}

    for record in batch.records:
        for family, expansion in _extract_symbol_material(record):
            if len(expansion) < 4:
                continue
            counts[(record.ns, expansion)] += 1
            symbol = abbreviate(expansion, family)
            expansions_by_symbol[symbol].add(expansion)
            family_by_expansion[expansion] = family

    proposed: list[MIRLRecord] = []
    index = 1
    for (namespace, expansion), frequency in counts.items():
        if frequency < min_frequency:
            continue
        family = family_by_expansion[expansion]
        symbol = abbreviate(expansion, family)
        ambiguity = _ambiguity(symbol, expansion, expansions_by_symbol)
        proposed.append(
            MIRLRecord(
                id=f"sym:auto:{index}",
                kind=RecordKind.SYM,
                ns=namespace,
                scope="project",
                status=Status.INFERRED,
                conf=max(0.4, 1.0 - ambiguity),
                attrs={
                    "symbol": symbol,
                    "expansion": expansion,
                    "family": family,
                    "frequency": frequency,
                    "ambiguity": round(ambiguity, 4),
                    "machine_only": True,
                    "reversible": True,
                },
            )
        )
        index += 1
    return proposed


def abbreviate(expansion: str, family: str = "generic") -> str:
    core = CORE_SYMBOLS.get((family, expansion.lower()))
    if core:
        return core
    parts = [part for part in expansion.lower().split("_") if part]
    if not parts:
        return expansion.lower()
    if family == "boolean":
        return "1" if expansion.lower() in {"yes", "true"} else "0"
    if family == "predicate":
        return "".join(part[:2] for part in parts)[:4]
    if len(parts) == 1:
        word = parts[0]
        if len(word) <= 3:
            return word
        if family == "time":
            return word[:3]
        if family == "status":
            return word[:1]
        if family == "entity":
            return _consonant_compact(word, 3)
        if family == "generic":
            return _generic_word_compact(word)
        return word[:3]
    if family == "generic":
        compact = "".join(_generic_word_compact(part)[:2] for part in parts)
        return compact[:8]
    return "".join(part[:2] for part in parts)[:8]


def build_symbol_maps(records: list[MIRLRecord], namespace: str | None = None) -> tuple[dict[str, str], dict[str, str]]:
    expansions_to_symbols: dict[str, str] = {}
    symbols_to_expansions: dict[str, str] = {}
    allowed_namespaces = set(namespace_chain(namespace)) if namespace else None
    for record in records:
        if record.kind != RecordKind.SYM:
            continue
        if allowed_namespaces is not None and record.ns not in allowed_namespaces:
            continue
        symbol = str(record.attrs.get("symbol"))
        expansion = str(record.attrs.get("expansion"))
        ambiguity = float(record.attrs.get("ambiguity", 1.0))
        if expansion and symbol and ambiguity <= 0.34:
            expansions_to_symbols[expansion] = symbol
            symbols_to_expansions[symbol] = expansion
    return expansions_to_symbols, symbols_to_expansions


def namespace_chain(namespace: str | None) -> list[str]:
    if not namespace:
        return []
    parts = namespace.split(".")
    chain = []
    for index in range(1, len(parts) + 1):
        chain.append(".".join(parts[:index]))
    return chain


def export_symbol_markdown(records: list[MIRLRecord], namespace: str | None = None) -> str:
    lines = ["# SEAM Symbol Nursery", ""]
    symbols = [record for record in records if record.kind == RecordKind.SYM and (namespace is None or record.ns == namespace)]
    if not symbols:
        lines.append("No symbols registered.")
        return "\n".join(lines)
    grouped: dict[str, list[MIRLRecord]] = defaultdict(list)
    for record in symbols:
        grouped[str(record.attrs.get("family", "generic"))].append(record)
    for family in sorted(grouped):
        lines.append(f"## {family}")
        lines.append("")
        for record in sorted(grouped[family], key=lambda item: item.id):
            attrs = record.attrs
            lines.append(
                f"- `{attrs.get('symbol')}` -> `{attrs.get('expansion')}` "
                f"(ns=`{record.ns}`, ambiguity=`{attrs.get('ambiguity')}`, freq=`{attrs.get('frequency')}`)"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _extract_symbol_material(record: MIRLRecord) -> list[tuple[str, str]]:
    attrs = record.attrs
    material: list[tuple[str, str]] = []
    if record.kind == RecordKind.CLM:
        predicate = attrs.get("predicate")
        if isinstance(predicate, str):
            material.append(("predicate", predicate))
        obj = attrs.get("object")
        material.extend(_extract_value_material(obj))
    elif record.kind == RecordKind.STA:
        for key, value in attrs.get("fields", {}).items():
            if isinstance(key, str):
                material.append(("predicate", key))
            material.extend(_extract_value_material(value))
    elif record.kind == RecordKind.ENT:
        entity_type = attrs.get("entity_type")
        if isinstance(entity_type, str):
            material.append(("entity", entity_type))
    return material


def _infer_family(expansion: str) -> str:
    lowered = expansion.lower()
    if lowered in {"yes", "no", "true", "false"}:
        return "boolean"
    if lowered.endswith("_at") or lowered in {"tomorrow", "today", "yesterday"}:
        return "time"
    if lowered in {"asserted", "observed", "inferred", "hypothetical", "contradicted", "superseded"}:
        return "status"
    if lowered in {"goal", "scope", "principle", "constraint", "translator"}:
        return "predicate"
    return "generic"


def _ambiguity(symbol: str, expansion: str, expansions_by_symbol: dict[str, set[str]]) -> float:
    variants = expansions_by_symbol.get(symbol, set())
    if not variants or variants == {expansion}:
        return 0.0
    return min(1.0, (len(variants) - 1) / max(len(variants), 1))


def _generic_word_compact(word: str) -> str:
    core = CORE_SYMBOLS.get(("generic", word))
    if core:
        return core
    return _consonant_compact(word, 3)


def _consonant_compact(word: str, length: int) -> str:
    vowels = {"a", "e", "i", "o", "u"}
    letters = [char for char in word.lower() if char.isalnum()]
    if not letters:
        return word.lower()
    compact = [letters[0]]
    compact.extend(char for char in letters[1:] if char not in vowels)
    joined = "".join(compact)
    return joined[:length] if len(joined) >= length else word[:length].lower()


def _extract_value_material(value: object) -> list[tuple[str, str]]:
    material: list[tuple[str, str]] = []
    if isinstance(value, str):
        if "_" in value:
            family = _infer_family(value)
            material.append((family, value))
            for part in value.split("_"):
                if len(part) >= 4:
                    material.append((_infer_family(part), part))
        elif len(value) >= 4:
            material.append((_infer_family(value), value))
    elif isinstance(value, list):
        for item in value:
            material.extend(_extract_value_material(item))
    return material
