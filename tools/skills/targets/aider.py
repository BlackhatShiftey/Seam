"""Aider repo-editing guidance renderer for SEAM skills."""

from __future__ import annotations

from typing import Any, Mapping

from seam_runtime.skills import SkillIR
from tools.skills.targets.generic import render as render_generic


def render(ir: SkillIR, profile: Mapping[str, Any], provenance: Mapping[str, str]) -> str:
    if profile.get("target") != "aider":
        raise ValueError(
            f"aider renderer requires profile.target == 'aider'; got {profile.get('target')!r}"
        )
    body = render_generic(ir, {**dict(profile), "target": "generic"}, provenance)
    preamble = (
        f"# Aider SEAM Skill — {ir.title}\n\n"
        "Use this as compact repo-editing guidance for Aider sessions. "
        "Favor minimal diffs, exact files, explicit test commands, and truthful verification notes.\n\n"
    )
    return preamble + body.split("\n", 1)[1]
