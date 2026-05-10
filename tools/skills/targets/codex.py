"""Codex/OpenAI-style repo-instruction renderer."""

from __future__ import annotations

from typing import Any, Mapping

from seam_runtime.skills import SkillIR
from tools.skills.targets.generic import render as render_generic


def render(ir: SkillIR, profile: Mapping[str, Any], provenance: Mapping[str, str]) -> str:
    if profile.get("target") != "codex":
        raise ValueError(
            f"codex renderer requires profile.target == 'codex'; got {profile.get('target')!r}"
        )
    body = render_generic(ir, {**dict(profile), "target": "generic"}, provenance)
    preamble = "\n".join(
        [
            f"# Codex Adapter — {ir.title}",
            "",
            "Use this adapter as repo-local operating guidance for Codex/OpenAI-style coding agents.",
            "Prioritize exact commands, patch discipline, test evidence, bounded context reads, and truthful failure reporting.",
            "Do not weaken any canonical SEAM safety, history, routing, or verification rule.",
            "",
        ]
    )
    return preamble + body.split("\n", 1)[1]
