"""Tests for adaptive Skill Factory primitives."""

from __future__ import annotations

import unittest

from seam_runtime.skills import (
    SkillObservation,
    identify_agent,
    propose_skill_from_observation,
)


class TestAgentIdentity(unittest.TestCase):
    def test_explicit_agent_override_wins(self):
        ident = identify_agent({"SEAM_AGENT": "codex"}, {})
        self.assertEqual(ident.agent, "codex")
        self.assertEqual(ident.confidence, 1.0)
        self.assertIn("codex.yaml", ident.profile)

    def test_known_file_fallback(self):
        ident = identify_agent({}, {"AGENTS.md": True})
        self.assertEqual(ident.agent, "codex")
        self.assertGreaterEqual(ident.confidence, 0.7)

    def test_unknown_falls_back_to_generic(self):
        ident = identify_agent({}, {})
        self.assertEqual(ident.agent, "generic")
        self.assertLess(ident.confidence, 0.5)


class TestSkillObservation(unittest.TestCase):
    def test_observation_roundtrip_and_proposal(self):
        obs = SkillObservation.from_dict(
            {
                "observation_id": "obs_docs_index_001",
                "agent": "codex",
                "task": "documentation update",
                "issue": "Agent added docs but missed the docs index.",
                "automatable": True,
                "suggested_skill": "docs-index-sync",
                "evidence": ["new docs file", "docs/README.md unchanged"],
                "proposed_rule": "When adding docs, check the docs index.",
                "repeat_count": 3,
            }
        )
        self.assertEqual(obs.agent, "codex")
        self.assertEqual(obs.repeat_count, 3)
        proposal = propose_skill_from_observation(obs)
        self.assertEqual(proposal.skill, "docs-index-sync")
        self.assertEqual(proposal.agent, "codex")
        self.assertIn("obs_docs_index_001", proposal.source_observations)
        self.assertIn("check the docs index", proposal.proposed_rules[0])


if __name__ == "__main__":
    unittest.main()
