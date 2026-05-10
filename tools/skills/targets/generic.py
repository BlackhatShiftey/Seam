"""Generic Markdown/JSON-ish skill renderer.

The generic target is intentionally plain and stable. It is useful for review,
non-integrated agents, and as the lowest-common-denominator artifact when a
model-specific harness does not yet exist.
"""

from __future__ import annotations

from typing import Any, Mapping

from seam_runtime.skills import SkillIR


def render(ir: SkillIR, profile: Mapping[str, Any], provenance: Mapping[str, str]) -> str:
    if profile.get("target") != "generic":
        raise ValueError(
            f"generic renderer requires profile.target == 'generic'; got {profile.get('target')!r}"
        )

    parts: list[str] = [f"# {ir.title}\n"]
    parts.append(_section("Skill Identity", _lines([
        f"name: {ir.name}",
        f"description: {ir.description}",
        f"short_description: {ir.short_description}",
    ])))
    parts.append(_section("Provenance", _kv_block(provenance)))
    parts.append(_section("Purpose", ir.purpose))
    parts.append(_section("Model Target", _model_target(ir)))
    parts.append(_section("Triggers", _triggers(ir)))
    parts.extend(_section(rule.title, rule.body) for rule in ir.non_negotiable_rules)
    parts.append(_section("Startup Check", _startup(ir)))
    parts.append(_section("Safety Rules", _bullets(ir.safety_rules)))
    parts.append(_section("Workflow", _workflow(ir)))
    parts.append(_section("Output Format", _fenced(ir.output_format)))
    parts.append(_section("Validation Prompts", _numbered(ir.validation_prompts)))
    parts.append(_section("Failure Conditions", _bullets(ir.failure_conditions)))
    return "\n".join(part.rstrip() + "\n" for part in parts if part.strip())


def _section(title: str, body: str) -> str:
    body = body.rstrip()
    return f"## {title}\n\n{body}\n" if body else ""


def _lines(items: list[str]) -> str:
    return "\n".join(items)


def _kv_block(values: Mapping[str, str]) -> str:
    return "\n".join(f"{key}: {values[key]}" for key in sorted(values))


def _bullets(items) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbered(items) -> str:
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def _fenced(body: str) -> str:
    return f"```text\n{body.rstrip()}\n```" if body.strip() else ""


def _model_target(ir: SkillIR) -> str:
    chunks: list[str] = []
    if ir.model_target.description.strip():
        chunks.append(ir.model_target.description.strip())
    if ir.model_target.preferences:
        chunks.append("Preferences:\n" + _bullets(ir.model_target.preferences))
    return "\n\n".join(chunks)


def _triggers(ir: SkillIR) -> str:
    chunks: list[str] = []
    if ir.triggers.use_when:
        chunks.append("Use when:\n" + _bullets(ir.triggers.use_when))
    if ir.triggers.do_not_use_when:
        chunks.append("Do not use when:\n" + _bullets(ir.triggers.do_not_use_when))
    return "\n\n".join(chunks)


def _startup(ir: SkillIR) -> str:
    sc = ir.startup_check
    chunks: list[str] = []
    if sc.inspect_commands:
        chunks.append("Inspect commands:\n" + _fenced("\n".join(sc.inspect_commands)))
    if sc.required_reads:
        chunks.append("Required reads:\n" + _numbered(sc.required_reads))
    if sc.bounded_reads:
        chunks.append("Bounded reads:\n" + _fenced("\n".join(sc.bounded_reads)))
    if sc.notes.strip():
        chunks.append(sc.notes.strip())
    return "\n\n".join(chunks)


def _workflow(ir: SkillIR) -> str:
    return "\n\n".join(f"### {step.number}. {step.title}\n\n{step.body.rstrip()}" for step in ir.workflow)
