# SEAM Agent Compiler Roadmap

**Status:** Planned major workstream  
**Added:** 2026-05-06  
**Purpose:** Generate, benchmark, and optimize model-specific agent skills/instructions from SEAM's canonical repo protocol.

## Why this matters

SEAM's long-term direction is not one hand-written prompt per assistant. The goal is one canonical project protocol that can compile into the right operating instructions for Claude, Codex, GPT-5, Gemini, Cursor, Aider, Grok, GLM, and future harnesses.

The Agent Compiler turns repo truth into agent-specific behavior adapters:

```text
AGENTS.md + PROJECT_STATUS.md + REPO_LEDGER.md + HISTORY_INDEX.md + routing docs + history tools
        -> Skill IR
        -> model profile
        -> compiled agent adapter
        -> benchmarked usage
        -> optimized next adapter version
```

This keeps SEAM's actual protocol centralized while still respecting how different models and harnesses prefer to receive instructions.

## Core architecture

### H1: Skill / Agent Instruction Compiler

**What:** Build a compiler that reads structured SEAM skill specs and emits target-specific instruction artifacts.

Initial targets:

- Claude skills: `~/.claude/skills/<skill>/SKILL.md`
- Codex / OpenAI-style repo instructions: generated `AGENTS.md` sections or external instruction packs
- Gemini guide fragments: generated `GEMINI.md` sections
- Cursor rules: `.cursor/rules/*.mdc`
- Aider guidance: compact repo editing and test instructions
- Generic agent packs: plain Markdown / JSON instruction bundles

**SOP:**

1. Add `skills/source/*.yaml` as canonical skill specs.
2. Add a `SkillIR` schema for triggers, required reads, commands, safety rules, validation, and expected artifacts.
3. Add target renderers under `tools/skills/targets/`.
4. Generate artifacts into `skills/generated/<target>/` first.
5. Add an apply step only after generated output is diffed and verified.

**Gate:** A single `session-end` source spec can compile into Claude, Codex, Gemini, Cursor, Aider, and generic Markdown outputs without changing the source spec.

### H2: Model Profiles

**What:** Maintain model/harness profiles so the compiler can tailor the same protocol to each target's preferred instruction shape.

Example profile fields:

```yaml
model: claude
format: skill_md
verbosity: high
prefers_numbered_protocols: true
needs_strong_stop_rules: true
supports_tool_use: true
supports_repo_local_rules: false
```

```yaml
model: cursor
format: mdc_rules
verbosity: low
prefers_short_scoped_rules: true
ide_aware: true
supports_file_globs: true
```

```yaml
model: codex
format: repo_agent_instructions
verbosity: medium
prefers_exact_commands: true
emphasize_patch_discipline: true
emphasize_tests: true
```

**SOP:**

1. Add `tools/skills/model_profiles/*.yaml`.
2. Define each profile as a set of formatting, verbosity, verification, and safety preferences.
3. Never let a profile remove canonical safety or continuity requirements.
4. Allow profile-specific examples, command ordering, and context budget hints.

**Gate:** Compiled outputs for at least three targets are materially different in form but equivalent in protocol obligations.

### H3: Skill Benchmark Suite

**What:** Add benchmark families that test whether an agent using a compiled skill behaves correctly on SEAM tasks.

Benchmark dimensions:

- session-start correctness
- history/context loading discipline
- session-end continuity closeout
- roadmap update correctness
- repo navigation accuracy
- patch/test discipline
- secret/session-link avoidance
- token efficiency
- unnecessary clarification rate
- stale-file avoidance
- archive/active-path routing correctness

Scenario families:

```text
skill/session-end
skill/repo-navigator
skill/history-loader
skill/roadmap-updater
skill/test-hardener
skill/skill-sync
```

Metrics:

```json
{
  "protocol_compliance": 1.0,
  "required_files_read": 1.0,
  "forbidden_files_read": 0,
  "history_entry_valid": true,
  "snapshot_written": true,
  "continuity_verified": true,
  "tests_run": true,
  "secret_leak_count": 0,
  "unnecessary_context_tokens": 0,
  "user_corrections_needed": 0
}
```

**SOP:**

1. Add `benchmarks/fixtures/skills/` with task scenarios and expected behavior checklists.
2. Add a `skills` benchmark family to the benchmark runner.
3. Build harness adapters that can run the same scenario against different model/agent targets when automation is available.
4. Store results in normal benchmark bundles so existing benchmark diff/verify tooling can compare skill versions.
5. Treat skill regressions as release blockers for generated agent adapters.

**Gate:** `seam benchmark run skills` produces verified bundles for local/static checks, and harness-enabled runs can compare at least two target profiles.

### H4: Skill Optimizer / Improvement Loop

**What:** Use SEAM's benchmark system to evolve compiled skills safely until each model/harness reaches the best observed balance of compliance, brevity, and task success.

Safe optimization loop:

```text
compile skill candidate
    -> run skill benchmarks
    -> compare against previous best
    -> propose mutation
    -> diff generated output
    -> reject if safety/protocol weakened
    -> promote only if benchmark score improves
```

Allowed mutations:

- reorder steps
- shorten or expand examples
- add missing command hints
- tighten trigger descriptions
- add model-specific reminders
- reduce redundant prose
- add failure-mode guardrails

Forbidden mutations:

- removing secret/session-link safety rules
- removing history or snapshot requirements
- removing verification requirements
- weakening active/archive routing
- hiding failed verification
- rewriting canonical repo truth automatically

**SOP:**

1. Add skill version metadata to generated artifacts.
2. Record benchmark results per skill, target, model profile, scenario, and version.
3. Add `seam skills optimize --target <target> --skill <skill>` as a propose-only command first.
4. Add `seam skills promote` only after candidate output passes benchmarks and safety checks.
5. Store accepted changes as new generated versions, not silent overwrites.

**Gate:** A candidate skill version can be rejected or promoted based on benchmark diff results, with a clear reason recorded.

### H5: Skill Sync / Installed Adapter Audit

**What:** Audit local installed skills and agent-rule files against compiled outputs.

Commands:

```bash
seam skills audit
seam skills compile --target claude
seam skills compile --target cursor
seam skills compile --target all
seam skills apply --target claude
seam skills verify
seam skills optimize --target claude --skill session-end
seam skills promote --candidate <path>
```

**SOP:**

1. Generated skills are written to build/generated locations first.
2. Installed skills are only updated through an explicit apply/promote step.
3. Every generated file includes source spec hash, model profile hash, compiler version, and generated timestamp.
4. Audit reports stale, missing, locally modified, or unsafe installed skills.

**Gate:** The audit command can detect a stale local Claude skill and point to the generated replacement without overwriting it.

## Benchmark strategy: per-scenario first, per-model second

The skill benchmarks should be mostly scenario-based, with model/harness-specific adapters around them.

The core scenario should stay the same:

```text
Task: close out a repo-changing session
Expected: inspect changes, append history, rebuild index, write snapshot, verify continuity, avoid secrets
```

That scenario applies to Claude, GPT-5/Codex, Gemini, Grok, GLM, Cursor, and Aider.

What changes per model is the harness and scoring adapter:

- Claude may be tested through skill files and transcript behavior.
- Cursor may be tested through `.mdc` rule compliance and patch behavior.
- Codex/GPT-style agents may be tested through repo instructions, command use, and patch/test outcomes.
- Gemini may be tested through compact guide adherence.
- Aider may be tested through edit accuracy and test-command discipline.

So the benchmark matrix should be:

```text
scenario x target/harness x model profile x skill version
```

Not completely separate benchmark logic for every model. Reuse the same scenario definitions wherever possible, and only swap the runner/evaluator for model-specific behavior.

## Expected end state

Once an agent/harness profile has been tuned, it should be able to cold start a SEAM repo and behave consistently:

1. Read the right canonical files.
2. Load bounded history instead of all history.
3. Stay in active paths unless archive material is requested.
4. Make patches that fit the framework.
5. Run the right tests.
6. Update roadmap/status/ledger only when appropriate.
7. Append history, rebuild index, write snapshots, and verify continuity after repo changes.
8. Avoid secrets, credentials, and private session links.
9. Keep token usage bounded.
10. Produce equivalent outcomes across harnesses, even when instruction formats differ.

The goal is not byte-identical behavior across models. The goal is protocol-equivalent behavior: different agents may think and speak differently, but they should satisfy the same SEAM invariants and pass the same scenario benchmarks.

## Relationship to the existing roadmap

This track extends:

- Track D — Model Skills & Automation
- Track C — Benchmark Hardening
- Track E — Architecture & Scalability

It should become a dedicated major track after the functional visual memory work is stable, because it turns SEAM from a repo with agent instructions into a system that can generate and improve agent instructions.

## Priority recommendation

Add this after the current functional visual-memory priority, but before broad multi-agent integration work:

```text
Phase 4A — Agent Compiler Foundation
├── H1: Skill / Agent Instruction Compiler
├── H2: Model Profiles
├── H5: Skill Sync / Installed Adapter Audit

Phase 4B — Skill Benchmarks
├── H3: Skill Benchmark Suite
├── skill/session-end fixtures
├── skill/repo-navigator fixtures
└── skill/roadmap-updater fixtures

Phase 4C — Optimization Loop
├── H4: Skill Optimizer
├── benchmark-diff promotion gate
└── model-specific adapter tuning
```
