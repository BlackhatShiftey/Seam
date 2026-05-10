# SEAM Skill Factory Roadmap

**Status:** Planned major workstream, superseding a static-only Agent Compiler interpretation.
**Extends:** `docs/roadmap/AGENT_COMPILER.md`

## Purpose

The SEAM Skill Factory is an adaptive agent-skill system. It does not merely render one source file into one target file. It identifies the active agent or harness, writes skills for that agent, records recurring failures and automation opportunities, proposes new skills or improvements, verifies them, and promotes them through an auditable review path.

Core principle:

> SEAM improves over time, and its agents should improve with it.

## Correct end state

```text
agent enters SEAM
  -> SEAM identifies the agent/harness
  -> SEAM loads or creates an agent profile
  -> SEAM observes issues, repeated failures, and automatable patterns
  -> SEAM proposes a new skill or improvement
  -> SEAM renders the skill for the identified agent
  -> SEAM verifies and benchmarks the candidate
  -> SEAM keeps notes about whether the skill helped
  -> SEAM promotes only reviewed, verified improvements
```

## Layers

### 1. Agent Identity Layer

Detect the current agent or harness using explicit operator input, environment markers, repo files, and available profile evidence. Unknown agents should map to `generic` with low confidence rather than fake certainty.

Initial targets:

- claude
- codex
- gemini
- cursor
- aider
- generic

### 2. Agent Profile Layer

Profiles describe output shape, verbosity, path templates, verification preferences, and harness constraints. Profiles must never remove canonical safety, verification, history, or continuity requirements.

### 3. Observation and Notes Layer

SEAM records repeated failures and automation opportunities as observations. These are notes, not automatic rewrites.

Example observation:

```json
{
  "observation_id": "obs_docs_index_001",
  "agent": "codex",
  "task": "documentation update",
  "issue": "Agent added a new docs file but forgot docs/README.md.",
  "automatable": true,
  "suggested_skill": "docs-index-sync",
  "repeat_count": 3,
  "proposed_rule": "When adding docs/*.md, check docs/README.md for index updates."
}
```

### 4. Proposal Layer

A proposal is a candidate skill or skill patch derived from observations. Proposals are reviewable artifacts. They do not mutate installed skills by themselves.

### 5. Rendering Layer

Render canonical skill intent into target-specific artifacts for Claude/OpenCode, Codex, Gemini, Cursor, Aider, or generic Markdown. Generated artifacts live under `skills/generated/<target>/...` before any apply/promotion step.

### 6. Verification Layer

Before promotion, a candidate must pass static checks, safety checks, optional benchmark scenarios, and drift checks against installed adapters. Future Track F work should connect this to audit logs, trust reports, and sealed benchmark bundles.

### 7. Promotion Layer

Promotion is explicit and gated. SEAM should show the diff, validation result, target, installed path, source spec hash, model profile hash, and any notes/observations linked to the change.

## Initial commands

Planned command surface:

```bash
seam agent identify
seam skills observe
seam skills notes
seam skills propose
seam skills compile --agent auto
seam skills compile --agent codex
seam skills diff
seam skills benchmark
seam skills audit
seam skills promote
```

The first safe implementation may expose equivalent operator tooling under `python -m tools.skills ...` before it is wired into the main `seam` CLI.

## Safety rules

- Do not silently rewrite installed skills.
- Do not weaken canonical safety, verification, history, routing, continuity, or secret-handling rules.
- Do not treat live observations as proof until verified.
- Do not promote a skill solely because it was generated.
- Do not mark a candidate as trusted without verification evidence.
- Keep generated artifacts separate from installed artifacts until an explicit apply/promote step.

## Relationship to Track F

Track F supplies the trust substrate: audit ledger, trust report, redaction, benchmark integrity, and supply-chain proof. The Skill Factory consumes those primitives when available, but it can start with local deterministic hashes, generated artifacts, and reviewable proposals.

## Definition of Done

The Skill Factory foundation is complete when SEAM can:

1. Identify the likely active agent or fall back to generic.
2. Render one canonical skill into all supported target formats.
3. Record an observation about a recurring issue.
4. Produce a deterministic skill proposal from the observation.
5. Keep generated artifacts separate from installed skills.
6. Verify that no candidate weakens canonical safety rules.
7. Preserve notes so future skill iterations can be compared and improved.
