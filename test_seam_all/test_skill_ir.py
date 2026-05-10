"""Tests for seam_runtime.skills.skill_ir.

These tests cover the dataclass shape, from_dict validation, lossless
to_dict round-trip, and canonical hashing. They do not depend on PyYAML —
SkillIR loads from a plain dict, which keeps the runtime test path free of
optional dependencies.
"""

from __future__ import annotations

import json
import unittest

from seam_runtime.skills import (
    SCHEMA_VERSION,
    NamedRule,
    SkillIR,
    StartupCheck,
    Triggers,
    WorkflowStep,
    canonical_bytes,
    sha256_of_bytes,
)
from seam_runtime.skills.skill_ir import SkillIRError


def _minimal_dict() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "name": "demo-skill",
        "title": "Demo Skill",
        "description": "A short demo description.",
        "short_description": "Demo",
        "purpose": "Exercise the SkillIR shape end-to-end.",
    }


def _full_dict() -> dict:
    d = _minimal_dict()
    d.update(
        {
            "model_target": {
                "description": "Any capable model.",
                "preferences": ["temperature: low", "thinking: enabled"],
            },
            "triggers": {
                "use_when": ["a", "b"],
                "do_not_use_when": ["read-only requests"],
            },
            "non_negotiable_rules": [
                {"title": "Rule one", "body": "Body of rule one."}
            ],
            "startup_check": {
                "inspect_commands": ["git status"],
                "required_reads": ["AGENTS.md"],
                "bounded_reads": ["python -m tools.history.build_context_pack"],
                "notes": "Targeted reads only.",
            },
            "safety_rules": ["Do not delete unrelated work."],
            "workflow": [
                {"number": 1, "title": "Step one", "body": "Do the first thing."},
                {"number": 2, "title": "Step two", "body": "Do the second thing."},
            ],
            "output_format": "Output template.",
            "validation_prompts": ["Prompt A", "Prompt B"],
            "failure_conditions": ["misses verification"],
        }
    )
    return d


class TestSkillIRConstruction(unittest.TestCase):
    def test_minimal_required_fields(self):
        ir = SkillIR.from_dict(_minimal_dict())
        self.assertEqual(ir.name, "demo-skill")
        self.assertEqual(ir.schema_version, SCHEMA_VERSION)
        self.assertEqual(ir.model_target.description, "")
        self.assertEqual(ir.model_target.preferences, ())
        self.assertEqual(ir.triggers.use_when, ())
        self.assertEqual(ir.non_negotiable_rules, ())
        self.assertEqual(ir.workflow, ())

    def test_full_construction(self):
        ir = SkillIR.from_dict(_full_dict())
        self.assertEqual(ir.model_target.preferences, ("temperature: low", "thinking: enabled"))
        self.assertEqual(ir.triggers.use_when, ("a", "b"))
        self.assertEqual(len(ir.non_negotiable_rules), 1)
        self.assertIsInstance(ir.non_negotiable_rules[0], NamedRule)
        self.assertEqual(len(ir.workflow), 2)
        self.assertEqual(ir.workflow[0].number, 1)
        self.assertEqual(ir.workflow[1].title, "Step two")
        self.assertEqual(ir.failure_conditions, ("misses verification",))


class TestSkillIRValidation(unittest.TestCase):
    def test_missing_required_field_raises(self):
        d = _minimal_dict()
        d.pop("purpose")
        with self.assertRaises(SkillIRError) as cm:
            SkillIR.from_dict(d)
        self.assertIn("purpose", str(cm.exception))

    def test_empty_required_field_raises(self):
        d = _minimal_dict()
        d["name"] = ""
        with self.assertRaises(SkillIRError):
            SkillIR.from_dict(d)

    def test_wrong_schema_version_raises(self):
        d = _minimal_dict()
        d["schema_version"] = "9.9"
        with self.assertRaises(SkillIRError) as cm:
            SkillIR.from_dict(d)
        self.assertIn("schema_version", str(cm.exception))

    def test_non_string_in_str_list_raises(self):
        d = _minimal_dict()
        d["safety_rules"] = ["ok", 42]
        with self.assertRaises(SkillIRError) as cm:
            SkillIR.from_dict(d)
        self.assertIn("safety_rules", str(cm.exception))

    def test_workflow_step_requires_positive_number(self):
        d = _minimal_dict()
        d["workflow"] = [{"number": 0, "title": "x", "body": "y"}]
        with self.assertRaises(SkillIRError):
            SkillIR.from_dict(d)

    def test_named_rule_requires_title_and_body(self):
        d = _minimal_dict()
        d["non_negotiable_rules"] = [{"title": "", "body": "x"}]
        with self.assertRaises(SkillIRError):
            SkillIR.from_dict(d)

    def test_top_level_must_be_mapping(self):
        with self.assertRaises(SkillIRError):
            SkillIR.from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]


class TestSkillIRRoundTrip(unittest.TestCase):
    def test_to_dict_round_trip_minimal(self):
        ir = SkillIR.from_dict(_minimal_dict())
        again = SkillIR.from_dict(ir.to_dict())
        self.assertEqual(ir, again)

    def test_to_dict_round_trip_full(self):
        ir = SkillIR.from_dict(_full_dict())
        again = SkillIR.from_dict(ir.to_dict())
        self.assertEqual(ir, again)

    def test_canonical_bytes_are_deterministic(self):
        ir1 = SkillIR.from_dict(_full_dict())
        ir2 = SkillIR.from_dict(_full_dict())
        self.assertEqual(canonical_bytes(ir1), canonical_bytes(ir2))

    def test_canonical_hash_changes_with_content(self):
        d = _full_dict()
        ir_a = SkillIR.from_dict(d)
        d["purpose"] = "different purpose"
        ir_b = SkillIR.from_dict(d)
        self.assertNotEqual(
            sha256_of_bytes(canonical_bytes(ir_a)),
            sha256_of_bytes(canonical_bytes(ir_b)),
        )

    def test_canonical_bytes_are_valid_json(self):
        ir = SkillIR.from_dict(_full_dict())
        parsed = json.loads(canonical_bytes(ir).decode("utf-8"))
        self.assertEqual(parsed["name"], "demo-skill")
        self.assertEqual(parsed["workflow"][0]["title"], "Step one")


class TestSessionEndSourceSpec(unittest.TestCase):
    """The repo's first canonical source spec must parse cleanly."""

    def test_session_end_yaml_loads_into_skill_ir(self):
        try:
            import yaml  # type: ignore
        except ImportError:
            self.skipTest("PyYAML not installed; covered by tools/skills/source_loader path")

        from pathlib import Path

        spec_path = (
            Path(__file__).resolve().parents[1]
            / "skills"
            / "source"
            / "session-end.yaml"
        )
        with spec_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        ir = SkillIR.from_dict(data)
        self.assertEqual(ir.name, "session-end")
        self.assertEqual(ir.title, "SEAM Session Closeout")
        self.assertEqual(ir.schema_version, SCHEMA_VERSION)
        self.assertGreaterEqual(len(ir.workflow), 7)
        self.assertGreaterEqual(len(ir.safety_rules), 5)
        self.assertGreaterEqual(len(ir.failure_conditions), 5)


if __name__ == "__main__":
    unittest.main()
