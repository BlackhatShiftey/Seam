"""Gemini guide-fragment renderer for SEAM skills."""

from __future__ import annotations

from typing import Any, Mapping

from seam_runtime.skills import SkillIR
from tools.skills.targets.generic import render as render_generic


def render(ir: SkillIR, profile: Mapping[str, Any], provenance: Mapping[str, str]) -> str:
    if profile.get("target") != "gemini":
        raise ValueError(
            f"gemini renderer requires profile.target == 'gemini'; got {profile.get('target')!r}"
        )
    body = render_generic(ir, {**dict(profile), "target": "generic"}, provenance)
    preamble = (
        f"# Gemini SEAM Skill Fragment — {ir.title}\n\n"
        "Use this as a concise GEMINI.md fragment. Preserve all safety and verification requirements.\n"
        "Prefer compact, ordered actions and explicit stop conditions.\n\n"
    )
    return preamble + body.split("\n", 1)[1]
