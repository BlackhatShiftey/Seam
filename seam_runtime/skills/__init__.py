"""SEAM Skill Factory runtime primitives."""

from __future__ import annotations

from .skill_ir import SkillIR, SkillIRError, canonical_bytes, sha256_of_bytes
from .factory import (
    AgentIdentity,
    SkillFactoryError,
    SkillObservation,
    SkillProposal,
    identify_agent,
    propose_skill_from_observation,
)

__all__ = [
    "SkillIR",
    "SkillIRError",
    "canonical_bytes",
    "sha256_of_bytes",
    "AgentIdentity",
    "SkillFactoryError",
    "SkillObservation",
    "SkillProposal",
    "identify_agent",
    "propose_skill_from_observation",
]
