"""Multi-target SEAM skills compiler.

This is the operator-side compiler core. It loads a canonical SkillIR source
spec and a target model profile, renders the target-specific artifact, and
returns enough metadata for audit, diff, or later promotion.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
import subprocess

from seam_runtime.skills import SKILL_IR_VERSION
from tools.skills.profile_loader import load_profile
from tools.skills.source_loader import load_skill
from tools.skills.targets import available_targets, get_renderer


COMPILER_VERSION = "0.2.0"


@dataclass(frozen=True)
class CompiledSkill:
    """Rendered skill artifact plus provenance metadata."""

    skill: str
    target: str
    output_path: str
    content: str
    provenance: dict[str, str]

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if not include_content:
            payload.pop("content", None)
        return payload


def compile_skill(
    source_path: str | Path,
    target: str,
    *,
    profile_path: str | Path | None = None,
    repo_root: str | Path = ".",
    include_runtime_provenance: bool = True,
) -> CompiledSkill:
    """Compile one canonical skill source to one target artifact."""

    if target not in available_targets():
        supported = ", ".join(available_targets())
        raise ValueError(f"unsupported target {target!r}; supported: {supported}")

    repo = Path(repo_root)
    source = Path(source_path)
    if not source.is_absolute():
        source = repo / source
    profile = Path(profile_path) if profile_path else repo / "tools" / "skills" / "model_profiles" / f"{target}.yaml"
    if not profile.is_absolute():
        profile = repo / profile

    ir, source_sha, _ = load_skill(source)
    profile_dict, profile_sha, _ = load_profile(profile)
    if profile_dict.get("target") != target:
        raise ValueError(
            f"profile target mismatch: expected {target!r}, got {profile_dict.get('target')!r}"
        )

    provenance = {
        "compiler_version": COMPILER_VERSION,
        "skill_ir_version": SKILL_IR_VERSION,
        "schema_version": ir.schema_version,
        "source_spec_sha256": source_sha,
        "model_profile_sha256": profile_sha,
        "target": target,
        "skill": ir.name,
    }
    if include_runtime_provenance:
        provenance["generated_at"] = datetime.now(timezone.utc).isoformat()
        provenance["git_sha"] = _git_sha(repo)

    renderer = get_renderer(target)
    content = renderer(ir, profile_dict, provenance)
    output_template = profile_dict.get("generated_path_template")
    if not isinstance(output_template, str) or not output_template.strip():
        raise ValueError(f"profile {profile} must define generated_path_template")
    output_path = output_template.format(skill=ir.name, target=target)
    return CompiledSkill(
        skill=ir.name,
        target=target,
        output_path=output_path,
        content=content,
        provenance=provenance,
    )


def compile_skill_for_targets(
    source_path: str | Path,
    targets: tuple[str, ...] | list[str],
    *,
    repo_root: str | Path = ".",
    include_runtime_provenance: bool = True,
) -> list[CompiledSkill]:
    """Compile one source skill for multiple targets."""

    return [
        compile_skill(
            source_path,
            target,
            repo_root=repo_root,
            include_runtime_provenance=include_runtime_provenance,
        )
        for target in targets
    ]


def write_compiled_skill(compiled: CompiledSkill, *, repo_root: str | Path = ".") -> Path:
    """Write a compiled artifact to its generated output path."""

    path = Path(repo_root) / compiled.output_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(compiled.content, encoding="utf-8")
    return path


def _git_sha(repo_root: Path) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return "unknown"
    return proc.stdout.strip() or "unknown"
