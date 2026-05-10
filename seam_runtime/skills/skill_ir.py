"""Canonical SkillIR for SEAM Skill Factory."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

SCHEMA_VERSION = "1.0"
SKILL_IR_VERSION = "0.1.0"


class SkillIRError(ValueError):
    """Raised when SkillIR input is invalid."""


@dataclass(frozen=True)
class SkillIR:
    schema_version: str
    name: str
    title: str
    description: str
    short_description: str
    purpose: str
    safety_rules: tuple[str, ...] = field(default_factory=tuple)
    workflow: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    output_format: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillIR":
        if not isinstance(data, Mapping):
            raise SkillIRError("SkillIR source must be a mapping")
        required = ("schema_version", "name", "title", "description", "short_description", "purpose")
        for key in required:
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                raise SkillIRError(f"{key} must be a non-empty string")
        if data["schema_version"] != SCHEMA_VERSION:
            raise SkillIRError(f"schema_version mismatch: expected {SCHEMA_VERSION}")
        return cls(
            schema_version=data["schema_version"],
            name=data["name"],
            title=data["title"],
            description=data["description"],
            short_description=data["short_description"],
            purpose=data["purpose"],
            safety_rules=_str_tuple(data.get("safety_rules"), "safety_rules"),
            workflow=_workflow_tuple(data.get("workflow")),
            output_format=_optional_str(data.get("output_format"), "output_format"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "short_description": self.short_description,
            "purpose": self.purpose,
            "safety_rules": list(self.safety_rules),
            "workflow": list(self.workflow),
            "output_format": self.output_format,
        }


def canonical_bytes(ir: SkillIR) -> bytes:
    return json.dumps(ir.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_of_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _optional_str(value: Any, key: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SkillIRError(f"{key} must be a string")
    return value


def _str_tuple(value: Any, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SkillIRError(f"{key} must be a list of strings")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise SkillIRError(f"{key}[{index}] must be a string")
    return tuple(value)


def _workflow_tuple(value: Any) -> tuple[dict[str, Any], ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SkillIRError("workflow must be a list")
    out: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise SkillIRError(f"workflow[{index}] must be a mapping")
        out.append(dict(item))
    return tuple(out)
