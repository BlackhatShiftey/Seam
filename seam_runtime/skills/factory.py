"""Adaptive Skill Factory primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


class SkillFactoryError(ValueError):
    """Raised when Skill Factory records are invalid."""


@dataclass(frozen=True)
class AgentIdentity:
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
        if not isinstance(data, Mapping):
            raise SkillFactoryError("SkillObservation must be a mapping")
        for key in ("observation_id", "agent", "task", "issue", "automatable"):
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
    environ = environ or {}
    files = files or {}
    if environ.get("SEAM_AGENT"):
        agent = environ["SEAM_AGENT"].strip().lower()
        return AgentIdentity(agent, 1.0, ("SEAM_AGENT override",), f"tools/skills/model_profiles/{agent}.yaml")
    env_checks = [
        ("claude", "CLAUDECODE"),
        ("codex", "CODEX_SANDBOX"),
        ("gemini", "GEMINI_CLI"),
        ("aider", "AIDER_MODEL"),
    ]
    for agent, key in env_checks:
        if environ.get(key):
            return AgentIdentity(agent, 0.9, (f"{key} present",), f"tools/skills/model_profiles/{agent}.yaml")
    file_checks = [
        ("cursor", ".cursor/rules"),
        ("codex", "AGENTS.md"),
        ("gemini", "GEMINI.md"),
        ("aider", ".aider.conf.yml"),
    ]
    for agent, path in file_checks:
        if files.get(path):
            return AgentIdentity(agent, 0.7, (f"{path} present",), f"tools/skills/model_profiles/{agent}.yaml")
    return AgentIdentity("generic", 0.3, ("no specific agent evidence found",), "tools/skills/model_profiles/generic.yaml")


def propose_skill_from_observation(observation: SkillObservation) -> SkillProposal:
    skill = observation.suggested_skill or _slugify(observation.task or observation.issue)
    rules = (observation.proposed_rule,) if observation.proposed_rule else ()
    return SkillProposal(
        proposal_id=f"proposal-{observation.observation_id}",
        skill=skill,
        agent=observation.agent,
        source_observations=(observation.observation_id,),
        rationale=f"Observed during {observation.task}: {observation.issue}. repeat_count={observation.repeat_count}.",
        proposed_rules=rules,
    )


def _slugify(value: str) -> str:
    out: list[str] = []
    dash = False
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
            dash = False
        elif not dash:
            out.append("-")
            dash = True
    return "".join(out).strip("-") or "skill-proposal"


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
