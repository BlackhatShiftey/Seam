"""Adaptive Skill Factory primitives.

The Skill Factory is the higher-level layer above SkillIR. It lets SEAM
identify the active agent, record repeated issues or automation opportunities,
propose skill changes, and promote only reviewed/verified skill candidates.

This module intentionally stays stdlib-only so the runtime can reason about
skill evolution without pulling in YAML or renderer dependencies.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


FACTORY_SCHEMA_VERSION = "1.0"
FACTORY_VERSION = "0.1.0"


class SkillFactoryError(ValueError):
    """Raised when Skill Factory records are invalid."""


@dataclass(frozen=True)
class AgentIdentity:
    """Detected agent or harness identity."""

    agent: str
    confidence: float
    evidence: tuple[str, ...] = ()
    profile: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "profile": self.profile,
        }


@dataclass(frozen=True)
class SkillObservation:
    """A note that SEAM or an operator can turn into a skill proposal."""

    observation_id: str
    agent: str
    task: str
    issue: str
    automatable: bool
    suggested_skill: str = ""
    evidence: tuple[str, ...] = ()
    proposed_rule: str = ""
    repeat_count: int = 1
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SkillObservation":
        _require_mapping(data, "SkillObservation")
        required = ("observation_id", "agent", "task", "issue", "automatable")
        for key in required:
            if key not in data:
                raise SkillFactoryError(f"missing required observation field: {key}")
        return cls(
            observation_id=_required_str(data, "observation_id"),
            agent=_required_str(data, "agent"),
            task=_required_str(data, "task"),
            issue=_required_str(data, "issue"),
            automatable=_required_bool(data, "automatable"),
            suggested_skill=_optional_str(data.get("suggested_skill"), "suggested_skill"),
            evidence=_str_tuple(data.get("evidence"), "evidence"),
            proposed_rule=_optional_str(data.get("proposed_rule"), "proposed_rule"),
            repeat_count=_positive_int(data.get("repeat_count", 1), "repeat_count"),
            created_at=_optional_str(data.get("created_at"), "created_at") or datetime.now(timezone.utc).isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["evidence"] = list(self.evidence)
        return out


@dataclass(frozen=True)
class SkillProposal:
    """A proposed new skill or improvement derived from observations."""

    proposal_id: str
    skill: str
    agent: str
    source_observations: tuple[str, ...]
    rationale: str
    proposed_rules: tuple[str, ...] = ()
    status: str = "proposed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "skill": self.skill,
            "agent": self.agent,
            "source_observations": list(self.source_observations),
            "rationale": self.rationale,
            "proposed_rules": list(self.proposed_rules),
            "status": self.status,
        }


def identify_agent(environ: Mapping[str, str] | None = None, files: Mapping[str, bool] | None = None) -> AgentIdentity:
    """Best-effort local agent/harness detection.

    Detection is deliberately conservative. Callers may pass explicit env/file
    evidence from the CLI or tests. Unknown agents return `generic` with low
    confidence instead of pretending certainty.
    """

    environ = environ or {}
    files = files or {}
    evidence: list[str] = []

    if environ.get("SEAM_AGENT"):
        agent = environ["SEAM_AGENT"].strip().lower()
        return AgentIdentity(agent=agent, confidence=1.0, evidence=("SEAM_AGENT override",), profile=f"tools/skills/model_profiles/{agent}.yaml")

    checks = [
        ("claude", "CLAUDECODE", "Claude Code environment"),
        ("codex", "CODEX_SANDBOX", "Codex sandbox environment"),
        ("gemini", "GEMINI_CLI", "Gemini CLI environment"),
        ("aider", "AIDER_MODEL", "Aider environment"),
    ]
    for agent, key, reason in checks:
        if environ.get(key):
            evidence.append(reason)
            return AgentIdentity(agent=agent, confidence=0.9, evidence=tuple(evidence), profile=f"tools/skills/model_profiles/{agent}.yaml")

    file_checks = [
        ("cursor", ".cursor/rules", "Cursor rules directory present"),
        ("codex", "AGENTS.md", "AGENTS.md present"),
        ("gemini", "GEMINI.md", "GEMINI.md present"),
        ("aider", ".aider.conf.yml", "Aider config present"),
    ]
    for agent, path, reason in file_checks:
        if files.get(path):
            evidence.append(reason)
            return AgentIdentity(agent=agent, confidence=0.7, evidence=tuple(evidence), profile=f"tools/skills/model_profiles/{agent}.yaml")

    return AgentIdentity(agent="generic", confidence=0.3, evidence=("no specific agent evidence found",), profile="tools/skills/model_profiles/generic.yaml")


def propose_skill_from_observation(observation: SkillObservation) -> SkillProposal:
    """Create a deterministic proposal from one observation.

    This is intentionally simple and safe: it proposes text and metadata only;
    it does not write or apply skills.
    """

    skill = observation.suggested_skill or _slugify(observation.task or observation.issue)
    rules = (observation.proposed_rule,) if observation.proposed_rule else ()
    return SkillProposal(
        proposal_id=f"proposal-{observation.observation_id}",
        skill=skill,
        agent=observation.agent,
        source_observations=(observation.observation_id,),
        rationale=(
            f"Observed issue during {observation.task!r}: {observation.issue}. "
            f"Automatable={observation.automatable}; repeat_count={observation.repeat_count}."
        ),
        proposed_rules=rules,
    )


def factory_record_bytes(record: Mapping[str, Any]) -> bytes:
    """Canonical JSON bytes for observation/proposal hashing."""

    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _slugify(value: str) -> str:
    chars: list[str] = []
    prev_dash = False
    for ch in value.lower():
        if ch.isalnum():
            chars.append(ch)
            prev_dash = False
        elif not prev_dash:
            chars.append("-")
            prev_dash = True
    return "".join(chars).strip("-") or "skill-proposal"


def _require_mapping(data: Mapping[str, Any], name: str) -> None:
    if not isinstance(data, Mapping):
        raise SkillFactoryError(f"{name} must be a mapping")


def _required_str(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SkillFactoryError(f"{key} must be a non-empty string")
    return value


def _optional_str(value: Any, key: str) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise SkillFactoryError(f"{key} must be a string")
    return value


def _required_bool(data: Mapping[str, Any], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise SkillFactoryError(f"{key} must be a bool")
    return value


def _positive_int(value: Any, key: str) -> int:
    if not isinstance(value, int) or value < 1:
        raise SkillFactoryError(f"{key} must be a positive integer")
    return value


def _str_tuple(value: Any, key: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise SkillFactoryError(f"{key} must be a list of strings")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise SkillFactoryError(f"{key}[{index}] must be a string")
    return tuple(value)
