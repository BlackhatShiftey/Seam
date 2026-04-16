from __future__ import annotations

import base64
import bz2
import hashlib
import json
import lzma
import math
import re
import zlib
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable


LOSSLESS_MAGIC = "SEAM-LX/1"
LOSSLESS_CODECS = ("zlib", "bz2", "lzma")
LOSSLESS_TRANSFORMS = ("identity", "line_table", "paragraph_table")
TOKEN_ESTIMATOR = "char4_approx"
TOKENIZER_CHOICES = ("auto", TOKEN_ESTIMATOR, "cl100k_base", "o200k_base")

_COMPRESSORS: dict[str, Callable[[bytes], bytes]] = {
    "zlib": lambda payload: zlib.compress(payload, level=9),
    "bz2": lambda payload: bz2.compress(payload, compresslevel=9),
    "lzma": lambda payload: lzma.compress(payload, preset=9 | lzma.PRESET_EXTREME),
}
_DECOMPRESSORS: dict[str, Callable[[bytes], bytes]] = {
    "zlib": zlib.decompress,
    "bz2": bz2.decompress,
    "lzma": lzma.decompress,
}


@dataclass
class LosslessArtifact:
    codec: str
    transform: str
    machine_text: str
    sha256: str
    original_bytes: int
    transformed_bytes: int
    compressed_bytes: int
    machine_bytes: int
    original_tokens: int
    machine_tokens: int
    token_estimator: str = TOKEN_ESTIMATOR

    @property
    def byte_savings_ratio(self) -> float:
        if self.original_bytes <= 0:
            return 0.0
        return 1.0 - (self.machine_bytes / self.original_bytes)

    @property
    def token_savings_ratio(self) -> float:
        if self.original_tokens <= 0:
            return 0.0
        return 1.0 - (self.machine_tokens / self.original_tokens)

    @property
    def intelligence_per_token_gain(self) -> float:
        if self.machine_tokens <= 0:
            return 0.0
        return self.original_tokens / self.machine_tokens

    def to_dict(self, include_machine_text: bool = True) -> dict[str, object]:
        payload = {
            "codec": self.codec,
            "transform": self.transform,
            "sha256": self.sha256,
            "original_bytes": self.original_bytes,
            "transformed_bytes": self.transformed_bytes,
            "compressed_bytes": self.compressed_bytes,
            "machine_bytes": self.machine_bytes,
            "original_tokens": self.original_tokens,
            "machine_tokens": self.machine_tokens,
            "byte_savings_ratio": round(self.byte_savings_ratio, 6),
            "token_savings_ratio": round(self.token_savings_ratio, 6),
            "intelligence_per_token_gain": round(self.intelligence_per_token_gain, 6),
            "token_estimator": self.token_estimator,
        }
        if include_machine_text:
            payload["machine_text"] = self.machine_text
        return payload


@dataclass
class LosslessAttempt:
    iteration: int
    transform: str
    codec: str
    transformed_bytes: int
    compressed_bytes: int
    machine_bytes: int
    machine_tokens: int
    token_savings_ratio: float
    byte_savings_ratio: float
    delta_vs_best: float
    delta_vs_previous: float
    status: str
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "iteration": self.iteration,
            "transform": self.transform,
            "codec": self.codec,
            "transformed_bytes": self.transformed_bytes,
            "compressed_bytes": self.compressed_bytes,
            "machine_bytes": self.machine_bytes,
            "machine_tokens": self.machine_tokens,
            "token_savings_ratio": round(self.token_savings_ratio, 6),
            "byte_savings_ratio": round(self.byte_savings_ratio, 6),
            "delta_vs_best": round(self.delta_vs_best, 6),
            "delta_vs_previous": round(self.delta_vs_previous, 6),
            "status": self.status,
            "flags": list(self.flags),
        }


@dataclass
class LosslessBenchmarkResult:
    artifact: LosslessArtifact
    roundtrip_text: str
    roundtrip_match: bool
    target_token_savings: float
    search_log: list[LosslessAttempt] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    stop_reason: str = ""

    @property
    def meets_target(self) -> bool:
        return self.artifact.token_savings_ratio >= self.target_token_savings

    @property
    def passed(self) -> bool:
        return self.roundtrip_match and self.meets_target

    def to_dict(self, include_machine_text: bool = False, include_roundtrip_text: bool = False) -> dict[str, object]:
        payload = {
            "passed": self.passed,
            "roundtrip_match": self.roundtrip_match,
            "meets_target": self.meets_target,
            "target_token_savings": round(self.target_token_savings, 6),
            "stop_reason": self.stop_reason,
            "flags": list(self.flags),
            "artifact": self.artifact.to_dict(include_machine_text=include_machine_text),
            "search_log": [attempt.to_dict() for attempt in self.search_log],
        }
        if include_roundtrip_text:
            payload["roundtrip_text"] = self.roundtrip_text
        return payload


def estimate_prompt_tokens(text: str, tokenizer: str = "auto") -> int:
    return count_prompt_tokens(text, tokenizer=tokenizer)[0]


def count_prompt_tokens(text: str, tokenizer: str = "auto") -> tuple[int, str]:
    counter, estimator = _resolve_token_counter(tokenizer)
    return counter(text), estimator


def compress_text_lossless(
    text: str,
    codec: str = "auto",
    transform: str = "auto",
    max_rounds: int = 4,
    tokenizer: str = "auto",
) -> LosslessArtifact:
    artifact, _, _, _ = _run_lossless_search(text, codec=codec, transform=transform, max_rounds=max_rounds, tokenizer=tokenizer)
    return artifact


def decompress_text_lossless(machine_text: str) -> str:
    codec, transform, sha256, payload = parse_lossless_machine_text(machine_text)
    compressed_bytes = base64.b85decode(payload.encode("ascii"))
    transformed_bytes = _DECOMPRESSORS[codec](compressed_bytes)
    raw_text = _restore_transform(transform, transformed_bytes)
    raw_bytes = raw_text.encode("utf-8")
    actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    if actual_sha256 != sha256:
        raise ValueError(f"Lossless payload hash mismatch: expected {sha256}, got {actual_sha256}")
    return raw_text


def benchmark_text_lossless(
    text: str,
    codec: str = "auto",
    transform: str = "auto",
    min_token_savings: float = 0.30,
    max_rounds: int = 4,
    tokenizer: str = "auto",
) -> LosslessBenchmarkResult:
    artifact, search_log, flags, stop_reason = _run_lossless_search(text, codec=codec, transform=transform, max_rounds=max_rounds, tokenizer=tokenizer)
    roundtrip_text = decompress_text_lossless(artifact.machine_text)
    result = LosslessBenchmarkResult(
        artifact=artifact,
        roundtrip_text=roundtrip_text,
        roundtrip_match=roundtrip_text == text,
        target_token_savings=min_token_savings,
        search_log=search_log,
        flags=flags,
        stop_reason=stop_reason,
    )
    if not result.roundtrip_match:
        result.flags.append("roundtrip_mismatch")
    if not result.meets_target:
        result.flags.append("target_not_met")
    return result


def render_lossless_benchmark_pretty(payload: dict[str, object]) -> str:
    artifact = payload.get("artifact", {})
    status = "PASS" if payload.get("passed") else "FAIL"
    roundtrip = "PASS" if payload.get("roundtrip_match") else "FAIL"
    target = float(payload.get("target_token_savings", 0.0))
    token_savings = float(artifact.get("token_savings_ratio", 0.0))
    lines = [
        f"Benchmark: {status}",
        f"Lossless roundtrip: {roundtrip}",
        f"Transform: {artifact.get('transform')}",
        f"Codec: {artifact.get('codec')}",
        f"Original tokens: {artifact.get('original_tokens')}",
        f"Machine tokens: {artifact.get('machine_tokens')}",
        f"Token savings: {token_savings:.1%}",
        f"Target savings: {target:.1%}",
        f"Intelligence per token gain: {float(artifact.get('intelligence_per_token_gain', 0.0)):.2f}x",
        f"Original bytes: {artifact.get('original_bytes')}",
        f"Machine bytes: {artifact.get('machine_bytes')}",
        f"SHA256: {artifact.get('sha256')}",
        f"Estimator: {artifact.get('token_estimator')}",
        f"Stop reason: {payload.get('stop_reason') or '(none)'}",
    ]
    flags = payload.get("flags", [])
    if flags:
        lines.append(f"Flags: {', '.join(str(flag) for flag in flags)}")
    search_log = payload.get("search_log", [])
    if search_log:
        lines.extend(["", "Search log:"])
        for attempt in search_log:
            attempt_flags = f" flags={','.join(attempt.get('flags', []))}" if attempt.get("flags") else ""
            lines.append(
                f"- iter={attempt.get('iteration')} transform={attempt.get('transform')} codec={attempt.get('codec')} "
                f"tokens={attempt.get('machine_tokens')} savings={float(attempt.get('token_savings_ratio', 0.0)):.1%} "
                f"status={attempt.get('status')}{attempt_flags}"
            )
    if "machine_text" in artifact:
        lines.extend(["", "Machine text:", str(artifact["machine_text"])])
    return "\n".join(lines)


def parse_lossless_machine_text(machine_text: str) -> tuple[str, str, str, str]:
    lines = [line.rstrip("\n") for line in machine_text.splitlines() if line.strip()]
    if not lines or lines[0] != LOSSLESS_MAGIC:
        raise ValueError(f"Expected {LOSSLESS_MAGIC} header")
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if "=" not in line:
            raise ValueError(f"Invalid lossless payload line: {line}")
        key, value = line.split("=", 1)
        fields[key] = value
    codec = fields.get("c")
    transform = fields.get("t", "identity")
    sha256 = fields.get("h")
    payload = fields.get("p")
    if codec not in LOSSLESS_CODECS:
        raise ValueError(f"Unsupported or missing lossless codec: {codec}")
    if transform not in LOSSLESS_TRANSFORMS:
        raise ValueError(f"Unsupported or missing lossless transform: {transform}")
    if not sha256 or not payload:
        raise ValueError("Lossless machine text is missing required fields")
    return codec, transform, sha256, payload


def lossless_benchmark_json(
    text: str,
    codec: str = "auto",
    transform: str = "auto",
    min_token_savings: float = 0.30,
    tokenizer: str = "auto",
    include_machine_text: bool = False,
) -> str:
    result = benchmark_text_lossless(text, codec=codec, transform=transform, min_token_savings=min_token_savings, tokenizer=tokenizer)
    return json.dumps(result.to_dict(include_machine_text=include_machine_text), indent=2)


def _run_lossless_search(
    text: str,
    codec: str = "auto",
    transform: str = "auto",
    max_rounds: int = 4,
    tokenizer: str = "auto",
) -> tuple[LosslessArtifact, list[LosslessAttempt], list[str], str]:
    codecs = [codec] if codec != "auto" else list(LOSSLESS_CODECS)
    transforms = [transform] if transform != "auto" else list(LOSSLESS_TRANSFORMS)
    invalid_codecs = [name for name in codecs if name not in LOSSLESS_CODECS]
    invalid_transforms = [name for name in transforms if name not in LOSSLESS_TRANSFORMS]
    if invalid_codecs:
        raise ValueError(f"Unsupported lossless codec: {invalid_codecs[0]}")
    if invalid_transforms:
        raise ValueError(f"Unsupported lossless transform: {invalid_transforms[0]}")

    search_space = [(transform_name, codec_name) for transform_name in transforms for codec_name in codecs]
    attempts: list[LosslessAttempt] = []
    flags: list[str] = []
    previous_ratio = 0.0
    best_artifact: LosslessArtifact | None = None
    best_key: tuple[int, int, int, str, str] | None = None
    iteration = 1
    remaining = search_space[:]
    stop_reason = "search space exhausted"

    while remaining and iteration <= max_rounds:
        improved_this_round = False
        round_best_artifact: LosslessArtifact | None = None
        round_best_key: tuple[int, int, int, str, str] | None = None
        round_best_index: int | None = None
        current_best_ratio = best_artifact.token_savings_ratio if best_artifact is not None else 0.0

        for index, (transform_name, codec_name) in enumerate(remaining):
            artifact = _compress_variant(text, transform_name, codec_name, tokenizer=tokenizer)
            candidate_key = _artifact_key(artifact)
            delta_vs_best = artifact.token_savings_ratio - current_best_ratio
            delta_vs_previous = artifact.token_savings_ratio - previous_ratio
            attempt_flags: list[str] = []
            status = "baseline"
            if delta_vs_previous < -0.02:
                attempt_flags.append("compression_regressed")
            if best_key is not None and candidate_key < best_key:
                status = "improved"
                improved_this_round = True
                if round_best_key is None or candidate_key < round_best_key:
                    round_best_artifact = artifact
                    round_best_key = candidate_key
                    round_best_index = index
            elif best_key is None:
                status = "improved"
                improved_this_round = True
                if round_best_key is None or candidate_key < round_best_key:
                    round_best_artifact = artifact
                    round_best_key = candidate_key
                    round_best_index = index
            elif delta_vs_best < -0.02:
                status = "regressed"
                attempt_flags.append("below_best")
            else:
                status = "flat"

            attempts.append(
                LosslessAttempt(
                    iteration=iteration,
                    transform=transform_name,
                    codec=codec_name,
                    transformed_bytes=artifact.transformed_bytes,
                    compressed_bytes=artifact.compressed_bytes,
                    machine_bytes=artifact.machine_bytes,
                    machine_tokens=artifact.machine_tokens,
                    token_savings_ratio=artifact.token_savings_ratio,
                    byte_savings_ratio=artifact.byte_savings_ratio,
                    delta_vs_best=delta_vs_best,
                    delta_vs_previous=delta_vs_previous,
                    status=status,
                    flags=attempt_flags,
                )
            )
            previous_ratio = artifact.token_savings_ratio

        if not improved_this_round or round_best_artifact is None or round_best_key is None:
            stop_reason = "no further improvement across known lossless rules"
            break

        best_artifact = round_best_artifact
        best_key = round_best_key
        flags.extend(flag for flag in _collect_round_flags(attempts, iteration) if flag not in flags)

        if round_best_index is not None:
            remaining.pop(round_best_index)
        if not remaining:
            stop_reason = "search space exhausted after selecting best candidate"
            break
        iteration += 1

    if best_artifact is None:
        raise ValueError("Lossless search did not produce any artifact")
    return best_artifact, attempts, flags, stop_reason


def _artifact_key(artifact: LosslessArtifact) -> tuple[int, int, int, str, str]:
    return (
        artifact.machine_tokens,
        artifact.machine_bytes,
        artifact.compressed_bytes,
        artifact.transform,
        artifact.codec,
    )


def _compress_variant(text: str, transform: str, codec: str, tokenizer: str = "auto") -> LosslessArtifact:
    transformed_bytes = _apply_transform(text, transform)
    compressed_bytes = _COMPRESSORS[codec](transformed_bytes)
    payload = base64.b85encode(compressed_bytes).decode("ascii")
    raw_bytes = text.encode("utf-8")
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    machine_text = "\n".join(
        [
            LOSSLESS_MAGIC,
            f"c={codec}",
            f"t={transform}",
            f"h={sha256}",
            f"p={payload}",
        ]
    )
    original_tokens, estimator = count_prompt_tokens(text, tokenizer=tokenizer)
    machine_tokens, _ = count_prompt_tokens(machine_text, tokenizer=tokenizer)
    return LosslessArtifact(
        codec=codec,
        transform=transform,
        machine_text=machine_text,
        sha256=sha256,
        original_bytes=len(raw_bytes),
        transformed_bytes=len(transformed_bytes),
        compressed_bytes=len(compressed_bytes),
        machine_bytes=len(machine_text.encode("utf-8")),
        original_tokens=original_tokens,
        machine_tokens=machine_tokens,
        token_estimator=estimator,
    )


def _approximate_prompt_tokens(text: str) -> int:
    if not text:
        return 0
    return int(math.ceil(len(text.encode("utf-8")) / 4))


def _resolve_token_counter(tokenizer: str) -> tuple[Callable[[str], int], str]:
    if tokenizer == "auto":
        try:
            encoder = _load_tiktoken_encoding("cl100k_base")
        except RuntimeError:
            return _approximate_prompt_tokens, TOKEN_ESTIMATOR
        return lambda text: len(encoder.encode(text)), "tiktoken:cl100k_base"
    if tokenizer == TOKEN_ESTIMATOR:
        return _approximate_prompt_tokens, TOKEN_ESTIMATOR
    if tokenizer in TOKENIZER_CHOICES:
        encoder = _load_tiktoken_encoding(tokenizer)
        return lambda text: len(encoder.encode(text)), f"tiktoken:{tokenizer}"
    raise ValueError(f"Unsupported tokenizer: {tokenizer}")


@lru_cache(maxsize=None)
def _load_tiktoken_encoding(name: str):
    try:
        import tiktoken
    except ImportError as exc:
        raise RuntimeError("tiktoken is not installed. Install it or use the char4_approx tokenizer.") from exc
    try:
        return tiktoken.get_encoding(name)
    except ValueError as exc:
        raise ValueError(f"Unsupported tiktoken encoding: {name}") from exc


def _collect_round_flags(attempts: list[LosslessAttempt], iteration: int) -> list[str]:
    round_attempts = [attempt for attempt in attempts if attempt.iteration == iteration]
    if not round_attempts:
        return []
    flagged = [attempt for attempt in round_attempts if attempt.flags]
    flags: list[str] = []
    if flagged:
        flags.append(f"iteration_{iteration}_fluctuations")
    regressed = [attempt for attempt in round_attempts if attempt.status == "regressed"]
    if regressed:
        flags.append(f"iteration_{iteration}_regressions")
    return flags


def _apply_transform(text: str, transform: str) -> bytes:
    if transform == "identity":
        return text.encode("utf-8")
    if transform == "line_table":
        lines = text.splitlines(keepends=True)
        payload = _build_table_payload(lines)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if transform == "paragraph_table":
        blocks = _split_paragraph_blocks(text)
        payload = _build_table_payload(blocks)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    raise ValueError(f"Unsupported lossless transform: {transform}")


def _restore_transform(transform: str, transformed_bytes: bytes) -> str:
    if transform == "identity":
        return transformed_bytes.decode("utf-8")
    data = json.loads(transformed_bytes.decode("utf-8"))
    chunks = data.get("chunks", [])
    order = data.get("order", [])
    return "".join(str(chunks[index]) for index in order)


def _build_table_payload(parts: list[str]) -> dict[str, object]:
    chunk_to_index: dict[str, int] = {}
    chunks: list[str] = []
    order: list[int] = []
    for part in parts:
        chunk_index = chunk_to_index.get(part)
        if chunk_index is None:
            chunk_index = len(chunks)
            chunk_to_index[part] = chunk_index
            chunks.append(part)
        order.append(chunk_index)
    return {"chunks": chunks, "order": order}


def _split_paragraph_blocks(text: str) -> list[str]:
    parts = re.split(r"(\n\s*\n)", text)
    return [part for part in parts if part]
