"""Cursor .mdc rule renderer for SEAM skills."""

from __future__ import annotations

from typing import Any, Mapping

from seam_runtime.skills import SkillIR
from tools.skills.targets.generic import render as render_generic


def render(ir: SkillIR, profile: Mapping[str, Any], provenance: Mapping[str, str]) -> str:
    if profile.get("target") != "cursor":
        raise ValueError(
            f"cursor renderer requires profile.target == 'cursor'; got {profile.get('target')!r}"
        )
    globs = profile.get("globs", ["**/*"])
    always_apply = str(profile.get("always_apply", False)).lower()
    body = render_generic(ir, {**dict(profile), "target": "generic"}, provenance)
    frontmatter = ["---", f"description: {ir.short_description}", f"globs: {globs}", f"alwaysApply: {always_apply}", "---", ""]
    return "\n".join(frontmatter) + body
