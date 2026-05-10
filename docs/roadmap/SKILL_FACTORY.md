# SEAM Skill Factory Roadmap

**Status:** Planned major workstream.
**Extends:** `docs/roadmap/AGENT_COMPILER.md`.

## Purpose

The SEAM Skill Factory turns the static Agent Compiler idea into an adaptive system. It identifies the active agent or harness, writes skills for that target, records recurring issues and automation opportunities, proposes new skills or improvements, verifies them, and promotes only reviewed candidates.

Core principle:

> SEAM improves over time, and its agents should improve with it.

## Correct Loop

```text
agent enters SEAM
  -> SEAM identifies the agent or harness
  -> SEAM loads an agent profile
  -> SEAM records recurring issues and automatable patterns
  -> SEAM proposes a skill or improvement
  -> SEAM renders the skill for the target agent
  -> SEAM verifies the candidate
  -> SEAM keeps notes about whether the skill helped
  -> SEAM promotes only reviewed improvements
```

## Layers

1. Agent Identity Layer — detect `claude`, `codex`, `gemini`, `cursor`, `aider`, or `generic`.
2. Agent Profile Layer — describe output shape, verbosity, path templates, and harness constraints.
3. Observation Layer — record repeated issues as structured notes.
4. Proposal Layer — create candidate skill changes from observations.
5. Rendering Layer — write target-specific skill artifacts.
6. Verification Layer — check candidates before promotion.
7. Promotion Layer — apply only through explicit review.

## Planned Commands

```bash
seam agent identify
seam skills observe
seam skills notes
seam skills propose
seam skills compile --agent auto
seam skills diff
seam skills benchmark
seam skills audit
seam skills promote
```

## Safety Rules

- Do not silently rewrite installed skills.
- Do not weaken canonical SEAM rules.
- Do not treat observations as proof until verified.
- Keep generated artifacts separate from installed artifacts until promotion.

## Definition of Done

The foundation is complete when SEAM can identify the likely agent, render one canonical skill into all supported target formats, record an observation, create a deterministic proposal from it, and preserve notes for future improvement.
