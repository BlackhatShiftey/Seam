"""SEAM skill canonical representation and adaptive Skill Factory primitives.

This package defines SkillIR plus the higher-level Skill Factory records used
to identify agents, capture recurring issues, propose skills, and improve
agent adapters over time.
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
from .factory import (
    AgentIdentity,
    SkillFactoryError,
    SkillObservation,
    SkillProposal,
    FACTORY_SCHEMA_VERSION,
    FACTORY_VERSION,
    factory_record_bytes,
    identify_agent,
    propose_skill_from_observation,
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
    "AgentIdentity",
    "SkillFactoryError",
    "SkillObservation",
    "SkillProposal",
    "FACTORY_SCHEMA_VERSION",
    "FACTORY_VERSION",
    "factory_record_bytes",
    "identify_agent",
    "propose_skill_from_observation",
]
