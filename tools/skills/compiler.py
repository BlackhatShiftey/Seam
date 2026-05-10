"""Operator-side Skill Factory compiler core.

The first compiler slice is intentionally conservative: it renders generated
artifacts only. It does not apply, install, or overwrite agent skill files.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from seam_runtime.skills import SkillIR, sha256_of_bytes

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


SUPPORTED_TARGETS = ("aider", "claude", "codex", "cursor", "gemini", "generic")

PROFILE_PATHS = {
    target: f"tools/skills/model_profiles/{target}.yaml" for target in SUPPORTED_TARGETS
}

OUTPUT_TEMPLATES = {
    "aider": "skills/generated/aider/{skill}/{skill}.md",
    "claude": "skills/generated/claude/{skill}/SKILL.md",
    "codex": "skills/generated/codex/{skill}/{skill}.md",
    "cursor": "skills/generated/cursor/{skill}/{skill}.mdc",
    "gemini": "skills/generated/gemini/{skill}/{skill}.md",
    "generic": "skills/generated/generic/{skill}/{skill}.md",
}


@dataclass(frozen=True)
class CompiledSkill:
    skill: str
    target: str
    output_path: str
    content: str
    source_spec_sha256: str

    def to_dict(self, *, include_content: bool = False) -> dict[str, Any]:
        payload = asdict(self)
        if not include_content:
            payload.pop("content", None)
        return payload


def load_skill_source(path: str | Path) -> tuple[SkillIR, str]:
    raw = Path(path).read_bytes()
    if yaml is None:
        raise RuntimeError("PyYAML is required for skills source loading")
    data = yaml.safe_load(raw)
    return SkillIR.from_dict(data), sha256_of_bytes(raw)


def compile_skill(source_path: str | Path, target: str) -> CompiledSkill:
    if target not in SUPPORTED_TARGETS:
        raise ValueError(f"unsupported target {target!r}; supported: {', '.join(SUPPORTED_TARGETS)}")
    ir, source_sha = load_skill_source(source_path)
    content = render_skill(ir, target, source_sha)
    return CompiledSkill(
        skill=ir.name,
        target=target,
        output_path=OUTPUT_TEMPLATES[target].format(skill=ir.name),
        content=content,
        source_spec_sha256=source_sha,
    )


def compile_skill_for_targets(source_path: str | Path, targets: list[str] | tuple[str, ...]) -> list[CompiledSkill]:
    selected = SUPPORTED_TARGETS if "all" in targets else tuple(targets)
    return [compile_skill(source_path, target) for target in selected]


def write_compiled_skill(compiled: CompiledSkill, *, repo_root: str | Path = ".") -> Path:
    output = Path(repo_root) / compiled.output_path
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(compiled.content, encoding="utf-8")
    return output


def render_skill(ir: SkillIR, target: str, source_sha: str) -> str:
    heading = _target_heading(target, ir.title)
    sections = [
        heading,
        _section("Purpose", ir.purpose),
        _section("Target", f"target: {target}\nsource_spec_sha256: {source_sha}"),
        _section("Safety Rules", _bullets(ir.safety_rules)),
        _section("Workflow", _workflow(ir)),
        _section("Output Format", _fenced(ir.output_format)),
    ]
    body = "\n".join(part for part in sections if part)
    if target == "claude":
        return _claude_frontmatter(ir, source_sha) + body
    if target == "cursor":
        return "---\nalwaysApply: false\n---\n\n" + body
    return body


def _target_heading(target: str, title: str) -> str:
    labels = {
        "aider": "Aider SEAM Skill",
        "claude": "SEAM Skill",
        "codex": "Codex SEAM Skill",
        "cursor": "Cursor SEAM Rule",
        "gemini": "Gemini SEAM Skill Fragment",
        "generic": "Generic SEAM Skill",
    }
    return f"# {labels[target]} — {title}\n"


def _claude_frontmatter(ir: SkillIR, source_sha: str) -> str:
    return (
        "---\n"
        f"name: seam-{ir.name}\n"
        f"description: {ir.description}\n"
        "metadata:\n"
        f"  short-description: {ir.short_description}\n"
        "provenance:\n"
        f"  source_spec_sha256: {source_sha}\n"
        f"  target: claude\n"
        f"  skill: {ir.name}\n"
        "---\n\n"
    )


def _section(title: str, body: str) -> str:
    body = body.rstrip()
    return f"## {title}\n\n{body}\n" if body else ""


def _bullets(items: tuple[str, ...]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _workflow(ir: SkillIR) -> str:
    lines: list[str] = []
    for step in ir.workflow:
        number = step.get("number", "?")
        title = step.get("title", "Step")
        body = step.get("body", "")
        lines.append(f"### {number}. {title}\n\n{body}")
    return "\n\n".join(lines)


def _fenced(body: str) -> str:
    return f"```text\n{body.rstrip()}\n```" if body.strip() else ""
