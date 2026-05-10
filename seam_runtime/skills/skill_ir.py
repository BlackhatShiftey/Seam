"""SkillIR — structured canonical representation of a SEAM skill.

Source specs live at skills/source/<name>.yaml and are loaded into SkillIR
instances by tools.skills.source_loader. Renderers under
tools/skills/targets/ consume SkillIR + a model profile to produce
target-specific instruction artifacts.

This module has no external dependencies beyond the Python standard library.
YAML loading happens in tools/skills/source_loader.py so PyYAML is not pulled
into seam-runtime base dependencies.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "1.0"
"""Source spec schema version. Bump on incompatible YAML schema changes."""

SKILL_IR_VERSION = "0.1.0"
"""SkillIR runtime version. Bump on incompatible IR shape changes."""


class SkillIRError(ValueError):
    """Raised when a SkillIR cannot be constructed from input data."""


@dataclass(frozen=True)
class ModelTarget:
    """Model/agent operating preferences for this skill."""

    description: str = ""
    preferences: tuple[str, ...] = ()


@dataclass(frozen=True)
class Triggers:
    """When the skill should and should not be used."""

    use_when: tuple[str, ...] = ()
    do_not_use_when: tuple[str, ...] = ()


@dataclass(frozen=True)
class NamedRule:
    """A titled rule block (e.g. 'Non-Negotiable Index Rule')."""

    title: str
    body: str


@dataclass(frozen=True)
class StartupCheck:
    """Commands and reads required before the skill executes."""

    inspect_commands: tuple[str, ...] = ()
    required_reads: tuple[str, ...] = ()
    bounded_reads: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class WorkflowStep:
    """One numbered step in the skill's workflow section."""

    number: int
    title: str
    body: str


@dataclass(frozen=True)
class SkillIR:
    """Canonical structured representation of a SEAM skill.

    Construct via SkillIR.from_dict(...). Provenance hashes are computed
    separately from the source bytes via sha256_of_bytes(); they are not
    fields on SkillIR itself, so the IR remains pure data and round-trips
    losslessly through to_dict.
    """

    schema_version: str
    name: str
    title: str
    description: str
    short_description: str
    purpose: str
    model_target: ModelTarget = field(default_factory=ModelTarget)
    triggers: Triggers = field(default_factory=Triggers)
    non_negotiable_rules: tuple[NamedRule, ...] = ()
    startup_check: StartupCheck = field(default_factory=StartupCheck)
    safety_rules: tuple[str, ...] = ()
    workflow: tuple[WorkflowStep, ...] = ()
    output_format: str = ""
    validation_prompts: tuple[str, ...] = ()
    failure_conditions: tuple[str, ...] = ()

    REQUIRED_FIELDS = (
        "schema_version",
        "name",
        "title",
        "description",
        "short_description",
        "purpose",
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillIR":
        if not isinstance(data, Mapping):
            raise SkillIRError(
                f"SkillIR source must be a mapping, got {type(data).__name__}"
            )

        for required in cls.REQUIRED_FIELDS:
            if required not in data:
                raise SkillIRError(f"missing required field: {required}")
            value = data[required]
            if not isinstance(value, str) or not value.strip():
                raise SkillIRError(
                    f"required field {required!r} must be a non-empty string"
                )

        if data["schema_version"] != SCHEMA_VERSION:
            raise SkillIRError(
                f"schema_version mismatch: got {data['schema_version']!r}, "
                f"expected {SCHEMA_VERSION!r}"
            )

        return cls(
            schema_version=data["schema_version"],
            name=data["name"],
            title=data["title"],
            description=data["description"],
            short_description=data["short_description"],
            purpose=data["purpose"],
            model_target=_model_target_from(data.get("model_target")),
            triggers=_triggers_from(data.get("triggers")),
            non_negotiable_rules=_named_rules_from(
                data.get("non_negotiable_rules"), key="non_negotiable_rules"
            ),
            startup_check=_startup_check_from(data.get("startup_check")),
            safety_rules=_str_tuple(data.get("safety_rules"), key="safety_rules"),
            workflow=_workflow_from(data.get("workflow")),
            output_format=_optional_str(
                data.get("output_format"), key="output_format"
            ),
            validation_prompts=_str_tuple(
                data.get("validation_prompts"), key="validation_prompts"
            ),
            failure_conditions=_str_tuple(
                data.get("failure_conditions"), key="failure_conditions"
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Lossless round-trippable mapping representation."""

        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "short_description": self.short_description,
            "purpose": self.purpose,
            "model_target": {
                "description": self.model_target.description,
                "preferences": list(self.model_target.preferences),
            },
            "triggers": {
                "use_when": list(self.triggers.use_when),
                "do_not_use_when": list(self.triggers.do_not_use_when),
            },
            "non_negotiable_rules": [
                {"title": rule.title, "body": rule.body}
                for rule in self.non_negotiable_rules
            ],
            "startup_check": {
                "inspect_commands": list(self.startup_check.inspect_commands),
                "required_reads": list(self.startup_check.required_reads),
                "bounded_reads": list(self.startup_check.bounded_reads),
                "notes": self.startup_check.notes,
            },
            "safety_rules": list(self.safety_rules),
            "workflow": [
                {"number": step.number, "title": step.title, "body": step.body}
                for step in self.workflow
            ],
            "output_format": self.output_format,
            "validation_prompts": list(self.validation_prompts),
            "failure_conditions": list(self.failure_conditions),
        }


def canonical_bytes(ir: SkillIR) -> bytes:
    """Stable canonical serialization of a SkillIR for hashing.

    Uses json.dumps with sort_keys and no extra whitespace so the output is
    deterministic across Python versions.
    """

    return json.dumps(
        ir.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_of_bytes(data: bytes) -> str:
    """Hex SHA-256 of bytes. Used for source-spec and profile hashes."""

    return hashlib.sha256(data).hexdigest()


# ----- Helpers -----


def _str_tuple(value: Any, *, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SkillIRError(f"{key} must be a list of strings")
    out: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise SkillIRError(
                f"{key}[{index}] must be a string, got {type(item).__name__}"
            )
        out.append(item)
    return tuple(out)


def _optional_str(value: Any, *, key: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SkillIRError(f"{key} must be a string")
    return value


def _model_target_from(value: Any) -> ModelTarget:
    if value is None:
        return ModelTarget()
    if not isinstance(value, Mapping):
        raise SkillIRError("model_target must be a mapping")
    description = _optional_str(value.get("description"), key="model_target.description")
    preferences = _str_tuple(value.get("preferences"), key="model_target.preferences")
    return ModelTarget(description=description, preferences=preferences)


def _triggers_from(value: Any) -> Triggers:
    if value is None:
        return Triggers()
    if not isinstance(value, Mapping):
        raise SkillIRError("triggers must be a mapping")
    return Triggers(
        use_when=_str_tuple(value.get("use_when"), key="triggers.use_when"),
        do_not_use_when=_str_tuple(
            value.get("do_not_use_when"), key="triggers.do_not_use_when"
        ),
    )


def _named_rules_from(value: Any, *, key: str) -> tuple[NamedRule, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SkillIRError(f"{key} must be a list of mappings")
    out: list[NamedRule] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise SkillIRError(f"{key}[{index}] must be a mapping")
        title = item.get("title")
        body = item.get("body")
        if not isinstance(title, str) or not title.strip():
            raise SkillIRError(f"{key}[{index}].title must be a non-empty string")
        if not isinstance(body, str):
            raise SkillIRError(f"{key}[{index}].body must be a string")
        out.append(NamedRule(title=title, body=body))
    return tuple(out)


def _startup_check_from(value: Any) -> StartupCheck:
    if value is None:
        return StartupCheck()
    if not isinstance(value, Mapping):
        raise SkillIRError("startup_check must be a mapping")
    return StartupCheck(
        inspect_commands=_str_tuple(
            value.get("inspect_commands"), key="startup_check.inspect_commands"
        ),
        required_reads=_str_tuple(
            value.get("required_reads"), key="startup_check.required_reads"
        ),
        bounded_reads=_str_tuple(
            value.get("bounded_reads"), key="startup_check.bounded_reads"
        ),
        notes=_optional_str(value.get("notes"), key="startup_check.notes"),
    )


def _workflow_from(value: Any) -> tuple[WorkflowStep, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SkillIRError("workflow must be a list of step mappings")
    out: list[WorkflowStep] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise SkillIRError(f"workflow[{index}] must be a mapping")
        number = item.get("number")
        title = item.get("title")
        body = item.get("body")
        if not isinstance(number, int) or number < 1:
            raise SkillIRError(
                f"workflow[{index}].number must be a positive int"
            )
        if not isinstance(title, str) or not title.strip():
            raise SkillIRError(
                f"workflow[{index}].title must be a non-empty string"
            )
        if not isinstance(body, str):
            raise SkillIRError(f"workflow[{index}].body must be a string")
        out.append(WorkflowStep(number=number, title=title, body=body))
    return tuple(out)
