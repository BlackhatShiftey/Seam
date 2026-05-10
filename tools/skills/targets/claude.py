"""Claude / OpenCode SKILL.md renderer.

Produces a markdown file with a YAML frontmatter block and structured body
sections. Output is byte-stable for fixed (SkillIR, profile, provenance)
inputs — callers are responsible for whatever runtime-varying provenance
they pass in.

The frontmatter is hand-formatted (not via yaml.dump) to keep ordering and
quoting deterministic across PyYAML versions.
"""

from __future__ import annotations

from typing import Any, Mapping

from seam_runtime.skills import SkillIR


# ----- Public entry point -----


def render(
    ir: SkillIR,
    profile: Mapping[str, Any],
    provenance: Mapping[str, str],
) -> str:
    """Render a SkillIR to a Claude/OpenCode SKILL.md string.

    `provenance` is a flat string-to-string mapping written verbatim into the
    frontmatter under `provenance:`. Sort order is deterministic.
    """

    if profile.get("target") != "claude":
        raise ValueError(
            f"claude renderer requires profile.target == 'claude'; "
            f"got {profile.get('target')!r}"
        )

    sections = profile.get("section_titles", {}) or {}

    parts: list[str] = []
    parts.append(_render_frontmatter(ir, profile, provenance))
    parts.append(f"# {ir.title}\n")

    if ir.purpose.strip():
        parts.append(_section(sections.get("purpose", "Purpose"), ir.purpose))

    parts.append(_render_model_target(ir, profile, sections))
    parts.append(_render_triggers(ir, profile, sections))
    parts.extend(_render_named_rules(ir))
    parts.append(_render_startup_check(ir, sections))

    if ir.safety_rules:
        parts.append(
            _section(
                sections.get("safety_rules", "Safety Rules"),
                _bulleted(ir.safety_rules),
            )
        )

    if ir.workflow:
        parts.append(_render_workflow(ir, sections))

    if ir.output_format.strip():
        parts.append(
            _section(
                sections.get("output_format", "Output Format"),
                _fenced(ir.output_format, lang="text"),
            )
        )

    if ir.validation_prompts:
        parts.append(
            _section(
                sections.get("validation_prompts", "Validation Prompts"),
                _numbered(ir.validation_prompts),
            )
        )

    if ir.failure_conditions:
        lead = sections.get(
            "failure_conditions_lead", "The skill fails if it:"
        )
        parts.append(f"{lead}\n\n" + _bulleted(ir.failure_conditions) + "\n")

    return "\n".join(part.rstrip() + "\n" for part in parts if part)


# ----- Section renderers -----


def _render_frontmatter(
    ir: SkillIR,
    profile: Mapping[str, Any],
    provenance: Mapping[str, str],
) -> str:
    name_template = profile.get("installed_name_template", "{skill}")
    installed_name = name_template.format(skill=ir.name)

    lines = ["---"]
    lines.append(f"name: {installed_name}")
    lines.extend(_yaml_string_field("description", ir.description))
    lines.append("metadata:")
    lines.append(f"  short-description: {_yaml_inline(ir.short_description)}")

    if provenance:
        lines.append("provenance:")
        for key in sorted(provenance):
            lines.append(f"  {key}: {_yaml_inline(provenance[key])}")

    lines.append("---")
    return "\n".join(lines) + "\n"


def _render_model_target(
    ir: SkillIR,
    profile: Mapping[str, Any],
    sections: Mapping[str, str],
) -> str:
    if not ir.model_target.description and not ir.model_target.preferences:
        return ""
    body_parts: list[str] = []
    if ir.model_target.description.strip():
        body_parts.append(ir.model_target.description.strip())
    if ir.model_target.preferences:
        intro = profile.get("preferences_intro", "Recommended preferences:")
        body_parts.append(intro + "\n\n" + _bulleted(ir.model_target.preferences))
    return _section(
        sections.get("model_target", "Model Target"),
        "\n\n".join(body_parts),
    )


def _render_triggers(
    ir: SkillIR,
    profile: Mapping[str, Any],
    sections: Mapping[str, str],
) -> str:
    if not ir.triggers.use_when and not ir.triggers.do_not_use_when:
        return ""
    body_parts: list[str] = []
    if ir.triggers.use_when:
        intro = profile.get("triggers_use_intro", "Use this skill when:")
        body_parts.append(intro + "\n\n" + _bulleted(ir.triggers.use_when))
    if ir.triggers.do_not_use_when:
        intro = profile.get("triggers_avoid_intro", "Do not use this skill for:")
        body_parts.append(intro + "\n\n" + _bulleted(ir.triggers.do_not_use_when))
    return _section(sections.get("triggers", "When To Use"), "\n\n".join(body_parts))


def _render_named_rules(ir: SkillIR) -> list[str]:
    return [_section(rule.title, rule.body) for rule in ir.non_negotiable_rules]


def _render_startup_check(
    ir: SkillIR, sections: Mapping[str, str]
) -> str:
    sc = ir.startup_check
    if not (
        sc.inspect_commands
        or sc.required_reads
        or sc.bounded_reads
        or sc.notes.strip()
    ):
        return ""
    body_parts: list[str] = []
    if sc.inspect_commands:
        body_parts.append(_fenced("\n".join(sc.inspect_commands), lang="bash"))
    if sc.required_reads:
        body_parts.append(
            "Required reads (in order):\n\n" + _numbered(sc.required_reads)
        )
    if sc.bounded_reads:
        body_parts.append(
            "Bounded context loaders:\n\n" + _fenced("\n".join(sc.bounded_reads), lang="bash")
        )
    if sc.notes.strip():
        body_parts.append(sc.notes.strip())
    return _section(
        sections.get("startup_check", "Startup Check"), "\n\n".join(body_parts)
    )


def _render_workflow(ir: SkillIR, sections: Mapping[str, str]) -> str:
    title = sections.get("workflow", "Workflow")
    blocks: list[str] = [f"## {title}\n"]
    for step in ir.workflow:
        blocks.append(f"### {step.number}. {step.title}\n")
        blocks.append(step.body.rstrip() + "\n")
    return "\n".join(blocks)


# ----- Primitives -----


def _section(title: str, body: str) -> str:
    body = body.rstrip()
    if not body:
        return ""
    return f"## {title}\n\n{body}\n"


def _bulleted(items) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbered(items) -> str:
    return "\n".join(f"{i + 1}. {item}" for i, item in enumerate(items))


def _fenced(body: str, *, lang: str = "") -> str:
    body = body.rstrip()
    return f"```{lang}\n{body}\n```"


def _yaml_string_field(key: str, value: str) -> list[str]:
    """Emit a YAML scalar field, using literal-block style for multiline."""
    value = value.rstrip()
    if not value:
        return [f"{key}: ''"]
    if "\n" in value:
        out = [f"{key}: |"]
        for line in value.splitlines():
            if line:
                out.append(f"  {line}")
            else:
                out.append("")
        return out
    return [f"{key}: {_yaml_inline(value)}"]


def _yaml_inline(value: str) -> str:
    """Inline scalar with conservative quoting.

    Quotes if the value contains characters that PyYAML would interpret
    specially. Otherwise emits the value unquoted for readability.
    """
    if value == "":
        return "''"
    needs_quote = any(c in value for c in ":#&*!|>'\"%@`,[]{}")
    if needs_quote or value[0] in "?-" or value.strip() != value:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value
