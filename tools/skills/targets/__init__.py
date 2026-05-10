"""Per-harness skill renderers and target registry.

Each renderer module exposes a render(ir, profile, provenance) -> str function
that returns the rendered artifact body as a string. Compiler callers use this
registry instead of importing target modules directly so unsupported targets
fail with a clear error before any artifact is written.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Callable, Mapping

from seam_runtime.skills import SkillIR

RenderFunc = Callable[[SkillIR, Mapping[str, Any], Mapping[str, str]], str]

_TARGET_MODULES: dict[str, str] = {
    "aider": "tools.skills.targets.aider",
    "claude": "tools.skills.targets.claude",
    "codex": "tools.skills.targets.codex",
    "cursor": "tools.skills.targets.cursor",
    "gemini": "tools.skills.targets.gemini",
    "generic": "tools.skills.targets.generic",
}


def available_targets() -> tuple[str, ...]:
    """Return supported target names in deterministic order."""

    return tuple(sorted(_TARGET_MODULES))


def get_renderer(target: str) -> RenderFunc:
    """Return the renderer function for a target."""

    if target not in _TARGET_MODULES:
        supported = ", ".join(available_targets()) or "none"
        raise ValueError(f"unsupported skill target {target!r}; supported: {supported}")
    module = import_module(_TARGET_MODULES[target])
    return getattr(module, "render")


__all__ = ["RenderFunc", "available_targets", "get_renderer"]
