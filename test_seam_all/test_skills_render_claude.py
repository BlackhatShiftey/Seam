"""Tests for tools.skills.targets.claude renderer.

Covers byte-stability, frontmatter shape, section ordering, profile-driven
overrides, and parity between the renderer output and the committed sample
artifact at skills/generated/claude/session-end/SKILL.md.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from seam_runtime.skills import SCHEMA_VERSION, SkillIR  # noqa: E402

try:
    import yaml  # type: ignore  # noqa: F401

    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def _minimal_ir() -> SkillIR:
    return SkillIR.from_dict(
        {
            "schema_version": SCHEMA_VERSION,
            "name": "demo",
            "title": "Demo Skill",
            "description": "Short demo description.",
            "short_description": "Demo",
            "purpose": "Test the renderer.",
        }
    )


def _full_ir() -> SkillIR:
    return SkillIR.from_dict(
        {
            "schema_version": SCHEMA_VERSION,
            "name": "demo",
            "title": "Demo Skill",
            "description": "Short demo description.",
            "short_description": "Demo",
            "purpose": "Test the renderer end to end.",
            "model_target": {
                "description": "Any model.",
                "preferences": ["temperature: low"],
            },
            "triggers": {
                "use_when": ["trigger one"],
                "do_not_use_when": ["read-only requests"],
            },
            "non_negotiable_rules": [
                {"title": "A rule", "body": "Body of the rule."}
            ],
            "startup_check": {
                "inspect_commands": ["git status"],
                "required_reads": ["AGENTS.md"],
                "bounded_reads": ["python -m tools.history.build_context_pack"],
                "notes": "Targeted reads only.",
            },
            "safety_rules": ["No destructive ops."],
            "workflow": [
                {"number": 1, "title": "First step", "body": "Do the first thing."}
            ],
            "output_format": "Output template here.",
            "validation_prompts": ["Prompt one"],
            "failure_conditions": ["misses verification"],
        }
    )


def _claude_profile() -> dict:
    return {
        "profile_version": "1.0",
        "target": "claude",
        "format": "skill_md",
        "installed_name_template": "seam-{skill}",
        "section_titles": {
            "purpose": "Purpose",
            "model_target": "Model Target",
            "triggers": "When To Use",
            "startup_check": "Startup Check",
            "safety_rules": "Safety Rules",
            "workflow": "Workflow",
            "output_format": "Output Format",
            "validation_prompts": "Validation Prompts",
            "failure_conditions_lead": "The skill fails if it:",
        },
        "preferences_intro": "Recommended runtime preferences:",
        "triggers_use_intro": "Use this skill when:",
        "triggers_avoid_intro": "Do not use this skill for:",
    }


def _provenance_fixed() -> dict:
    return {
        "compiler_version": "0.1.0",
        "schema_version": SCHEMA_VERSION,
        "source_spec_sha256": "0" * 64,
        "model_profile_sha256": "1" * 64,
        "target": "claude",
        "skill": "demo",
    }


class TestClaudeRendererShape(unittest.TestCase):
    def test_renders_minimal_ir(self):
        from tools.skills.targets.claude import render

        out = render(_minimal_ir(), _claude_profile(), _provenance_fixed())
        self.assertTrue(out.startswith("---\n"))
        self.assertIn("name: seam-demo", out)
        self.assertIn("# Demo Skill", out)
        self.assertIn("## Purpose", out)

    def test_renders_full_ir_sections_in_order(self):
        from tools.skills.targets.claude import render

        out = render(_full_ir(), _claude_profile(), _provenance_fixed())
        positions = {
            section: out.find(section)
            for section in [
                "## Purpose",
                "## Model Target",
                "## When To Use",
                "## A rule",
                "## Startup Check",
                "## Safety Rules",
                "## Workflow",
                "## Output Format",
                "## Validation Prompts",
                "The skill fails if it:",
            ]
        }
        for section, pos in positions.items():
            self.assertGreater(pos, 0, f"section missing: {section}")
        ordered = sorted(positions, key=lambda s: positions[s])
        self.assertEqual(ordered, list(positions.keys()))

    def test_provenance_fields_appear_sorted(self):
        from tools.skills.targets.claude import render

        out = render(_minimal_ir(), _claude_profile(), _provenance_fixed())
        prov_block_start = out.find("provenance:")
        prov_block_end = out.find("---", prov_block_start)
        prov_block = out[prov_block_start:prov_block_end]
        keys_in_order = [
            line.split(":", 1)[0].strip()
            for line in prov_block.splitlines()
            if line.startswith("  ")
        ]
        self.assertEqual(keys_in_order, sorted(keys_in_order))

    def test_wrong_target_profile_rejected(self):
        from tools.skills.targets.claude import render

        bad = _claude_profile()
        bad["target"] = "cursor"
        with self.assertRaises(ValueError):
            render(_minimal_ir(), bad, _provenance_fixed())

    def test_workflow_steps_are_h3_with_numbering(self):
        from tools.skills.targets.claude import render

        out = render(_full_ir(), _claude_profile(), _provenance_fixed())
        self.assertIn("### 1. First step", out)


class TestClaudeRendererStability(unittest.TestCase):
    def test_byte_stable_across_two_invocations(self):
        from tools.skills.targets.claude import render

        ir = _full_ir()
        profile = _claude_profile()
        provenance = _provenance_fixed()
        out_a = render(ir, profile, provenance)
        out_b = render(ir, profile, provenance)
        self.assertEqual(out_a, out_b)

    def test_changing_provenance_changes_output(self):
        from tools.skills.targets.claude import render

        ir = _minimal_ir()
        profile = _claude_profile()
        prov_a = _provenance_fixed()
        prov_b = dict(prov_a)
        prov_b["source_spec_sha256"] = "f" * 64
        self.assertNotEqual(
            render(ir, profile, prov_a),
            render(ir, profile, prov_b),
        )


@unittest.skipUnless(HAS_YAML, "PyYAML not installed")
class TestSessionEndArtifactParity(unittest.TestCase):
    """The committed sample artifact must match a deterministic re-render
    of skills/source/session-end.yaml against the committed claude profile.
    """

    def test_committed_sample_matches_renderer_output(self):
        from tools.skills.profile_loader import load_profile
        from tools.skills.source_loader import load_skill
        from tools.skills.targets.claude import render

        repo = Path(__file__).resolve().parents[1]
        spec = repo / "skills" / "source" / "session-end.yaml"
        profile_path = repo / "tools" / "skills" / "model_profiles" / "claude.yaml"
        artifact_path = (
            repo / "skills" / "generated" / "claude" / "session-end" / "SKILL.md"
        )

        ir, source_sha, _ = load_skill(spec)
        profile_dict, profile_sha, _ = load_profile(profile_path)

        provenance = {
            "compiler_version": "0.1.0",
            "schema_version": ir.schema_version,
            "source_spec_sha256": source_sha,
            "model_profile_sha256": profile_sha,
            "target": "claude",
            "skill": ir.name,
        }

        rendered = render(ir, profile_dict, provenance)

        self.assertTrue(artifact_path.exists(), f"missing sample at {artifact_path}")
        committed = artifact_path.read_text(encoding="utf-8")
        self.assertEqual(
            rendered,
            committed,
            "Committed sample drifted from renderer output. "
            "Re-run tools/skills/regenerate_session_end.py or accept the new bytes.",
        )


if __name__ == "__main__":
    unittest.main()
