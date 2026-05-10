"""SEAM skill canonical representation.

This package defines the SkillIR — the structured canonical representation a
skill source spec compiles into. Renderers in tools/skills/targets/ consume
SkillIR instances to produce target-specific instruction artifacts (Claude
SKILL.md, Cursor .mdc, etc.).
"""

from __future__ import annotations

from .skill_ir import (
    SkillIR,
    ModelTarget,
    Triggers,
    NamedRule,
    StartupCheck,
    WorkflowStep,
    SCHEMA_VERSION,
    SKILL_IR_VERSION,
    canonical_bytes,
    sha256_of_bytes,
)

__all__ = [
    "SkillIR",
    "ModelTarget",
    "Triggers",
    "NamedRule",
    "StartupCheck",
    "WorkflowStep",
    "SCHEMA_VERSION",
    "SKILL_IR_VERSION",
    "canonical_bytes",
    "sha256_of_bytes",
]
