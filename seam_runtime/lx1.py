"""
SEAM-LX/1 compact notation — AI-readable, token-efficient encoding of MIRL records.

Unlike the byte-compression path in lossless.py, this format stays as readable text.
An AI model can reason over it directly; a compiler turns it back to natural language.

Line format:
  Header:  !LX1 ns=<ns> sc=<scope>
  Record:  <K> <id> [~meta...] [key=val...]

Kind codes (single char):
  E=ENT  C=CLM  R=REL  V=EVT  S=STA  Y=SYM
  P=PACK  F=FLOW  W=PROV  M=META  X=RAW  Z=SPAN

Meta tokens (tilde-prefixed, only written when non-default):
  ~n=<ns>     namespace (omitted when equal to header ns)
  ~sc=<scope> scope (omitted when equal to header scope)
  ~c=<float>  confidence (omitted when 1.0)
  ~s=<char>   status: a=asserted(default) o=observed i=inferred
                      h=hypothetical x=contradicted z=superseded
                      d=deprecated _=deleted_soft
  ~@<id>      provenance reference (repeatable)
  ~^<id>      evidence reference (repeatable)
  ~t0=<ts>    temporal start (omitted when null)
  ~t1=<ts>    temporal end (omitted when null)

Attr values:
  Bare token    — letter/underscore-starting simple strings
  "quoted"      — strings with spaces or special characters
  123 / 1.5     — integers and floats
  true/false    — booleans
  null          — None
  [...]/{...}   — lists and dicts (compact JSON)
"""
from __future__ import annotations

import json
import re
from typing import Any

from .mirl import IRBatch, MIRLRecord, RecordKind, Status

LX1_MAGIC = "!LX1"

_KIND_TO_CODE: dict[RecordKind, str] = {
    RecordKind.ENT: "E",
    RecordKind.CLM: "C",
    RecordKind.REL: "R",
    RecordKind.EVT: "V",
    RecordKind.STA: "S",
    RecordKind.SYM: "Y",
    RecordKind.PACK: "P",
    RecordKind.FLOW: "F",
    RecordKind.PROV: "W",
    RecordKind.META: "M",
    RecordKind.RAW: "X",
    RecordKind.SPAN: "Z",
}
_CODE_TO_KIND: dict[str, RecordKind] = {v: k for k, v in _KIND_TO_CODE.items()}

_STATUS_TO_CODE: dict[Status, str] = {
    Status.ASSERTED: "a",
    Status.OBSERVED: "o",
    Status.INFERRED: "i",
    Status.HYPOTHETICAL: "h",
    Status.CONTRADICTED: "x",
    Status.SUPERSEDED: "z",
    Status.DEPRECATED: "d",
    Status.DELETED_SOFT: "_",
}
_CODE_TO_STATUS: dict[str, Status] = {v: k for k, v in _STATUS_TO_CODE.items()}

_DEFAULT_CONF = 1.0
_DEFAULT_STATUS = Status.ASSERTED
_RESERVED_TOKENS = {"null", "true", "false"}
_SAFE_VALUE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_:./\-]*$")


def encode(batch: IRBatch, ns: str = "local.default", scope: str = "project") -> str:
    """Encode an IRBatch to LX/1 compact notation. AI-readable without decompression."""
    lines = [f"{LX1_MAGIC} ns={ns} sc={scope}"]
    for record in sorted(batch.records, key=lambda r: r.id):
        lines.append(encode_record(record, default_ns=ns, default_scope=scope))
    return "\n".join(lines)


def decode(text: str) -> IRBatch:
    """Decode LX/1 compact notation back to an IRBatch."""
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    if not lines:
        raise ValueError("Empty LX/1 input")

    header_ns = "local.default"
    header_scope = "project"
    record_lines: list[str] = []

    for line in lines:
        if line.startswith(LX1_MAGIC):
            for token in _split_tokens(line[len(LX1_MAGIC):].strip()):
                if token.startswith("ns="):
                    header_ns = _decode_val(token[3:])
                elif token.startswith("sc="):
                    header_scope = _decode_val(token[3:])
        else:
            record_lines.append(line)

    return IRBatch([decode_record(line, default_ns=header_ns, default_scope=header_scope) for line in record_lines])


def encode_record(record: MIRLRecord, default_ns: str = "local.default", default_scope: str = "project") -> str:
    """Encode a single MIRLRecord to a compact LX/1 line."""
    kind_code = _KIND_TO_CODE.get(record.kind)
    if kind_code is None:
        raise ValueError(f"Unknown record kind: {record.kind}")

    parts = [kind_code, record.id]

    if record.ns != default_ns:
        parts.append(f"~n={_encode_val(record.ns)}")
    if record.scope != default_scope:
        parts.append(f"~sc={_encode_val(record.scope)}")
    if abs(record.conf - _DEFAULT_CONF) > 1e-9:
        parts.append(f"~c={round(record.conf, 6)}")
    if record.status != _DEFAULT_STATUS:
        parts.append(f"~s={_STATUS_TO_CODE.get(record.status, 'a')}")
    for prov_id in record.prov:
        parts.append(f"~@{prov_id}")
    for ev_id in record.evidence:
        parts.append(f"~^{ev_id}")
    if record.t0:
        parts.append(f"~t0={_encode_val(record.t0)}")
    if record.t1:
        parts.append(f"~t1={_encode_val(record.t1)}")

    for key, value in record.attrs.items():
        parts.append(f"{key}={_encode_val(value)}")

    return " ".join(parts)


def decode_record(line: str, default_ns: str = "local.default", default_scope: str = "project") -> MIRLRecord:
    """Decode a single LX/1 compact line to a MIRLRecord."""
    tokens = _split_tokens(line)
    if len(tokens) < 2:
        raise ValueError(f"Invalid LX/1 record line: {line!r}")

    kind = _CODE_TO_KIND.get(tokens[0])
    if kind is None:
        raise ValueError(f"Unknown LX/1 kind code: {tokens[0]!r} in: {line!r}")

    record_id = tokens[1]
    ns = default_ns
    scope = default_scope
    conf = _DEFAULT_CONF
    status = _DEFAULT_STATUS
    prov: list[str] = []
    evidence: list[str] = []
    t0 = None
    t1 = None
    attrs: dict[str, Any] = {}

    for token in tokens[2:]:
        if token.startswith("~"):
            meta = token[1:]
            if meta.startswith("n="):
                ns = _decode_val(meta[2:])
            elif meta.startswith("sc="):
                scope = _decode_val(meta[3:])
            elif meta.startswith("c="):
                conf = float(meta[2:])
            elif meta.startswith("s="):
                status = _CODE_TO_STATUS.get(meta[2:], Status.ASSERTED)
            elif meta.startswith("@"):
                prov.append(meta[1:])
            elif meta.startswith("^"):
                evidence.append(meta[1:])
            elif meta.startswith("t0="):
                t0 = _decode_val(meta[3:])
            elif meta.startswith("t1="):
                t1 = _decode_val(meta[3:])
        elif "=" in token:
            key, _, raw_val = token.partition("=")
            attrs[key] = _decode_val(raw_val)

    return MIRLRecord(
        id=record_id,
        kind=kind,
        ns=ns,
        scope=scope,
        conf=conf,
        status=status,
        prov=prov,
        evidence=evidence,
        t0=t0,
        t1=t1,
        attrs=attrs,
    )


def token_savings_report(original_mirl: str, compact: str) -> dict[str, object]:
    """Compute token savings between verbose MIRL text and LX/1 compact notation."""
    from .lossless import estimate_prompt_tokens
    orig = estimate_prompt_tokens(original_mirl)
    comp = estimate_prompt_tokens(compact)
    ratio = 1.0 - (comp / orig) if orig > 0 else 0.0
    gain = orig / comp if comp > 0 else 0.0
    return {
        "original_tokens": orig,
        "compact_tokens": comp,
        "token_savings_ratio": round(ratio, 6),
        "intelligence_per_token_gain": round(gain, 6),
        "original_chars": len(original_mirl),
        "compact_chars": len(compact),
        "char_savings_ratio": round(1.0 - len(compact) / len(original_mirl), 6) if original_mirl else 0.0,
    }


def _encode_val(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if _SAFE_VALUE_RE.match(value) and value not in _RESERVED_TOKENS:
            return value
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def _decode_val(raw: str) -> Any:
    if raw == "null":
        return None
    if raw == "true":
        return True
    if raw == "false":
        return False
    if raw.startswith('"'):
        return json.loads(raw)
    if raw.startswith(("[", "{")):
        return json.loads(raw)
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _split_tokens(line: str) -> list[str]:
    """Split a line into space-delimited tokens, respecting quoted strings and JSON brackets."""
    tokens: list[str] = []
    i = 0
    n = len(line)

    while i < n:
        while i < n and line[i] == " ":
            i += 1
        if i >= n:
            break

        start = i
        while i < n and line[i] != " ":
            ch = line[i]
            if ch == '"':
                i += 1
                while i < n:
                    if line[i] == "\\":
                        i += 2
                    elif line[i] == '"':
                        i += 1
                        break
                    else:
                        i += 1
            elif ch in "[{":
                depth = 0
                in_str = False
                while i < n:
                    c = line[i]
                    if in_str:
                        if c == "\\":
                            i += 2
                            continue
                        if c == '"':
                            in_str = False
                    else:
                        if c == '"':
                            in_str = True
                        elif c in "[{":
                            depth += 1
                        elif c in "]}":
                            depth -= 1
                            if depth == 0:
                                i += 1
                                break
                    i += 1
            else:
                i += 1

        if i > start:
            tokens.append(line[start:i])

    return tokens
