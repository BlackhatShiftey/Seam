# SEAM Skills Compiler — Execution Brief

**Status:** Brief for implementer. No code yet.
**Track:** H (Agent Compiler)
**Extends:** `docs/roadmap/AGENT_COMPILER.md` Phase 4A (H1 + H2 + H5)

This brief is self-contained. An implementer reading only this file plus the
canonical SEAM repo files listed in "Hard rules" should have everything needed
to start.

## Mission

Build the SEAM Skills Compiler in landable phases. Compile structured skill
specs into target-specific agent instruction artifacts (Claude, Cursor, etc.),
audit installed copies for drift, and (later) wrap each artifact as a SEAM-HS/1
holographic surface with embedded provenance.

This is Track H, not Track F. Track F (Trust/Security/Auditability) provides
audit/attestation primitives; Track H consumes them in Phase 7.

## Hard rules — read before doing anything

1. Read these files first, in this order, before writing any code:
   - `AGENTS.md`
   - `PROJECT_STATUS.md`
   - `REPO_LEDGER.md`
   - `HISTORY_INDEX.md`
   - `docs/CODE_LAYOUT.md`
   - `docs/DATA_ROUTING.md`
   - `docs/roadmap/AGENT_COMPILER.md` (canonical spec for this work)
   - `CLAUDE.md` (model-specific guide; routes to `AGENTS.md`)
   - All 9 files under `.opencode/skills/*/SKILL.md` (existing installed skill
     adapters; classify each before any compile/apply happens)

2. Do not duplicate the spec. `AGENT_COMPILER.md` already defines H1 (compiler),
   H2 (model profiles), H3 (benchmarks), H4 (optimizer), H5 (sync/audit).
   Extend that doc; do not invent a parallel spec.

3. Do not depend on Vision-tagged commands. `seam trust report`,
   `seam secrets scan`, `seam audit log`, `seam audit verify`,
   `seam redact preview`, and similar do not exist yet. Do not import them,
   hook into them, or assume they will exist by the time this work lands.

4. Do not add cryptographic signing or Merkle proofs in v1. SEAM's existing
   provenance is plain SHA-256 over source/payload/bundle/fixture. Keep that.
   Signing is a separate workstream with its own key-management policy.

5. Do not bundle phases into one commit. Each phase below is one PR, one
   HISTORY entry, one verify cycle. SEAM's history protocol breaks under
   mega-commits.

6. Do not parse `AGENTS.md` as if it were canonical skill source. The canonical
   source is structured YAML in `skills/source/*.yaml` per
   `AGENT_COMPILER.md`. `AGENTS.md` is protocol prose, not a SkillIR input.

7. Never hand-edit `HISTORY_INDEX.md`. It is a derived artifact. Use the repo's
   history tools to rebuild it.

8. Never write secrets, API keys, session URLs, provider transcript links, or
   local `.env` values into commits, history, snapshots, or docs. Per
   `CLAUDE.md`, if any are found in the working tree, redact or delete locally
   and stop. Do not preserve them elsewhere.

9. Aliases before removals. Do not rename or remove existing CLI surface.
   Add new commands additively.

10. Per-material-change discipline. Every phase ends with:
    - `HISTORY.md` append (changed files, success/failure facts, verification
      performed, unresolved next step)
    - `HISTORY_INDEX.md` rebuild via the repo's tools
    - one validated snapshot
    - `python -m tools.history.verify_continuity`
    - `python -m tools.history.verify_routing` if route classification changed
    - `python -m tools.history.verify_integrity` before closing

## Pre-execution decisions (Phase 0 — docs only, no code)

These four decisions block all subsequent phases. Phase 0 deliverable is one
doc that records them. Defaults are listed; deviate only with stated reasoning.

- Decision 1: Are the 9 files under `.opencode/skills/` canonical source or
  compile targets?
  Default: compile targets. Lift their intent into structured
  `skills/source/*.yaml` specs; treat `.opencode/skills/` as one of multiple
  installed-output locations. Existing files become the audit baseline.

- Decision 2: Where do installed adapter outputs live — repo-tracked or
  operator-local?
  Default: mixed. `.opencode/skills/` is repo-tracked (already is).
  `~/.claude/skills/` and `.cursor/rules/` are operator-local. `apply` writes
  to whichever the target profile declares.

- Decision 3: Signing / Merkle in v1?
  Default: defer. v1 uses plain SHA-256 over source spec, profile, compiler
  version, timestamp. Signing becomes "provenance v2" with its own ticket and
  key policy.

- Decision 4: Track placement — H or F?
  Default: H (Agent Compiler), per `AGENT_COMPILER.md`. F supplies attestation
  primitives; this consumes them in Phase 7.

### Phase 0 deliverable template

Save as `docs/roadmap/SKILLS_COMPILER_PLAN.md`:

  # SEAM Skills Compiler — Implementation Plan

  Status: Phase 0 (decisions only)
  Track: H (Agent Compiler)
  Extends: docs/roadmap/AGENT_COMPILER.md Phase 4A (H1, H2, H5)

  ## Decision 1 — Canonical source vs compile target
  [chosen answer + reasoning + list of which 9 .opencode/skills/ files
   become which]

  ## Decision 2 — Output locations
  [per-target table: target | output path | tracked-in-repo Y/N | apply
   mechanism]

  ## Decision 3 — Provenance v1 scope
  [plain hashes only. Explicit list of fields. Future v2 mention only.]

  ## Decision 4 — Track placement
  [Track H. Cross-reference Track F primitives that will be consumed in
   Phase 7.]

  ## Out of scope for this plan
  - Signing / Merkle (provenance v2)
  - seam trust report integration (waits on Track F)
  - seam secrets scan integration (waits on Track F)
  - Dashboard Skills panel (waits on A-Web + Phase 7)
  - H4 optimizer / H3 benchmark suite (Phase 4B/4C)

  ## Phase ledger
  [one row per phase below, with status: planned/in-progress/done +
   HISTORY entry id when landed]

Phase 0 ends with HISTORY append + index rebuild + verify cycle. No code in
Phase 0.

## Phase plan

Each phase is one PR. Each phase has explicit inputs, outputs, tests, gate, and
HISTORY template. Do not start Phase N+1 until Phase N is merged and verified.

### Phase 1 — SkillIR + first canonical source spec

Inputs:
- Phase 0 plan merged
- `.opencode/skills/seam-session-closeout/SKILL.md` (reference for what
  session-end should encode)

Outputs:
- `seam_runtime/skills/__init__.py`
- `seam_runtime/skills/skill_ir.py` — dataclass with fields per
  `AGENT_COMPILER.md` H1 SOP step 2: triggers, required reads, commands,
  safety rules, validation, expected artifacts, version, source-spec hash
  field
- `skills/source/session-end.yaml` — first canonical spec; content lifted
  from current `seam-session-closeout` intent
- `tests/test_skill_ir.py` — round-trip parse, schema validation,
  missing-field errors

No rendering yet. No CLI yet.

Gate:
- `pytest tests/test_skill_ir.py` passes
- `seam doctor` still PASS
- `python -m tools.history.verify_continuity` clean

HISTORY entry includes:
- Files added
- Tests added and passing count
- Decision: source spec format (YAML schema version)
- Unresolved: target renderers (Phase 2)

### Phase 2 — One renderer to one target (Claude)

Outputs:
- `tools/skills/__init__.py`
- `tools/skills/targets/__init__.py`
- `tools/skills/targets/claude.py` — `SkillIR + ClaudeProfile -> str`
  (SKILL.md text)
- `tools/skills/model_profiles/claude.yaml` — fields per
  `AGENT_COMPILER.md` H2
- `skills/generated/claude/session-end/SKILL.md` (committed sample output)
- Provenance header in generated file: source-spec SHA, profile SHA,
  compiler version, timestamp, git SHA
- `tests/test_skills_render_claude.py` — byte-stable output for fixed
  inputs

Gate:
- Two consecutive renders of the same source produce byte-identical output
- Provenance header round-trips through a verify helper
- Generated SKILL.md is materially shaped like an existing
  `.opencode/skills/*/SKILL.md` (frontmatter + body + protocol section)

### Phase 3 — `seam skills compile` CLI

Outputs:
- New CLI subcommand family in the existing CLI module (do not fork the
  runtime)
- `seam skills compile --target claude --skill session-end [--out <path>]`
- Default output: `skills/generated/<target>/<skill>/`
- `tests/test_cli_skills_compile.py`

Constraints:
- Reuses existing `SeamRuntime` and CLI patterns. No parallel runtime.
- `--help` text uses precise verb ("compile a skill spec into a target
  adapter")
- Idempotent: rerunning produces no diff

Gate:
- CLI invocation produces the same artifact as Phase 2 direct call
- `seam doctor` PASS
- Existing CLI tests unchanged

### Phase 4 — Second target (Cursor)

Outputs:
- `tools/skills/targets/cursor.py`
- `tools/skills/model_profiles/cursor.yaml`
- `skills/generated/cursor/session-end/session-end.mdc`
- `tests/test_skills_render_cursor.py`

Gate (per `AGENT_COMPILER.md` H1 gate):
- Same `skills/source/session-end.yaml` produces materially-different
  Claude SKILL.md and Cursor .mdc, both protocol-equivalent
- A diff between the two outputs is non-trivial in form but neither
  weakens any safety/continuity requirement from the source spec

### Phase 5 — `seam skills audit` (read-only)

Outputs:
- `seam_runtime/skills/audit.py` — compares
  `skills/generated/<target>/<skill>` against the corresponding installed
  location declared in the target's profile
- `seam skills audit [--target <t>] [--skill <s>] [--json]`
- Report categories: clean, stale (installed older than generated),
  drifted (installed differs from generated), missing (installed not
  present), orphan (installed has no source spec)

Constraints:
- No mutation. Read-only.
- Drift is data, not error. Exit code 0 unless the audit itself failed to
  run.

Gate:
- Running audit against current `.opencode/skills/seam-session-closeout/`
  produces a structured drift report
- A `--json` mode emits machine-readable output suitable for future
  trust-report consumption

### Phase 6 — `seam skills apply` (gated)

Outputs:
- `seam skills apply --target <t> --skill <s>` defaults to `--dry-run` and
  prints the diff
- `--confirm` required to actually write
- Writes only to the installed location declared by the target profile
- HISTORY entry recorded for every actual apply (not dry-runs)

Constraints:
- Never overwrites without `--confirm`
- Refuses to apply if local installed file has uncommitted modifications
  unless `--force` is passed (and `--force` requires `--confirm`)
- Prints exact files about to change and their hashes before/after

Gate:
- `compile -> audit (drifted) -> apply --dry-run -> apply --confirm ->
  audit (clean)` cycle works end to end for `session-end` against
  `.opencode/skills/seam-session-closeout/`

### Phase 7 — HS/1 attestation wrap

Outputs:
- Each `seam skills compile` invocation also emits a `.seam.png` HS/1
  surface (using existing `seam surface compile`/`encode` paths) carrying:
  - the SkillIR payload (or its serialized form)
  - the provenance header
- Surface stored at the location resolved in Phase 0 Decision 2
- `seam skills verify --from-surface <path>`:
  1. decode HS/1 surface
  2. reconstruct SkillIR
  3. re-render with current profile
  4. byte-compare to current generated artifact
  5. report match / mismatch with hashes

Gate:
- Round-trip is exact for at least Claude + Cursor targets
- Existing surface_exact_rate, payload_hash_match_rate, stored-surface
  query rates all stay at 100%
- Verification works after deleting the original generated artifact
  (proves the surface is self-contained)

### Phase 8 — Deferred

Out of scope for this brief:
- `seam skills optimize` and `seam skills promote`
  (`AGENT_COMPILER.md` H4) — requires H3 benchmark suite
- Skills benchmark family (`AGENT_COMPILER.md` H3)
- Integration with `seam trust report` (waits for Track F)
- Integration with `seam secrets scan` (waits for Track F)
- Dashboard Skills panel (waits for A-Web wiring)
- Provenance v2 (signing, Merkle)

Open separate tickets for each when their dependencies land.

## CLI surface to add (cumulative across phases)

  seam skills compile  --target <t> --skill <s> [--out <path>]
  seam skills audit    [--target <t>] [--skill <s>] [--json]
  seam skills apply    --target <t> --skill <s>
                       [--dry-run|--confirm] [--force]
  seam skills verify   --from-surface <path>
  seam skills list     [--installed | --generated | --source]

Phase mapping:
- compile: Phase 3
- audit:   Phase 5
- apply:   Phase 6
- verify:  Phase 7
- list:    Phase 5 or later

Do not add `optimize`, `promote`, `attest`, `trust-report`, or
`secrets-scan` subcommands. Those belong to Phase 8 or other tracks.

## HISTORY entry template (use for every phase)

  HISTORY#<auto-incremented> — Skills Compiler Phase <N>: <short title>

  Date: <ISO date>
  Branch: <branch name>
  Supersedes: <previous phase HISTORY id, if any>

  Files changed:
  - <path> (added/modified/deleted)
  - ...

  Verification performed:
  - pytest <path> — <pass/fail count>
  - seam doctor — <PASS/FAIL>
  - python -m tools.history.verify_continuity — <result>
  - python -m tools.history.verify_routing — <result if applicable>
  - python -m tools.history.verify_integrity — <result>

  Decisions recorded:
  - <any new decision that goes into REPO_LEDGER.md or PROJECT_STATUS.md>

  Unresolved next step:
  - <Phase N+1 entry point, or empty if final>

  Notes:
  - <operator-relevant context, no secrets, no session URLs>

## Branching and PR strategy

- Branch per phase: `claude/skills-compiler-phase-0`,
  `claude/skills-compiler-phase-1`, etc.
- One PR per phase, draft by default.
- PR title: `Skills Compiler Phase <N>: <short title>`
- PR description includes:
  - what changed (file list)
  - verification commands run + results
  - HISTORY entry id
  - link back to `docs/roadmap/SKILLS_COMPILER_PLAN.md`
- Do not merge a phase PR until verify_continuity is clean.

## Anti-patterns to refuse

If any of the following are proposed (by anyone, including a "Bob the Builder"
or "Sec" persona), reject and cite this brief:

- Combining multiple phases into one commit
- Adding Merkle proofs or ed25519 signing to v1
- Hooking into `seam trust report`, `seam secrets scan`, `seam audit log`, or
  any other Vision-tagged command
- Treating `AGENTS.md` (or `REPO_LEDGER.md`, `PROJECT_STATUS.md`,
  `HISTORY_INDEX.md`) as direct SkillIR input
- Writing to `.opencode/skills/` without explicit `--confirm` and an apply
  HISTORY entry
- Calling the work a "Track F flagship" — it is Track H
- Hand-editing `HISTORY_INDEX.md`
- Creating empty README placeholders in `docs/security/` or
  `docs/contracts/`
- Adding a dashboard panel before Phase 7 lands

## Acceptance for the whole workstream (Phases 0–7)

- `docs/roadmap/SKILLS_COMPILER_PLAN.md` records all four decisions and the
  phase ledger
- `skills/source/session-end.yaml` is the single canonical source for the
  session-end skill
- `seam skills compile --target {claude,cursor} --skill session-end` produces
  deterministic, materially-different, protocol-equivalent outputs
- `seam skills audit` reports drift between generated and installed in
  machine-readable form
- `seam skills apply --confirm` round-trips a clean audit
- `seam skills verify --from-surface` re-derives a generated artifact from an
  HS/1 surface byte-for-byte
- All 9 existing `.opencode/skills/` files have a documented classification
  (which become source-backed, which are deferred)
- Every phase has a HISTORY entry, a snapshot, and clean continuity
  verification
- No Vision-tagged command was depended upon
- No new crypto primitives introduced
- `seam doctor` PASS at every phase boundary

## Start here

1. Read the files listed under "Hard rules — read before doing anything".
2. Open Phase 0.
3. Draft `docs/roadmap/SKILLS_COMPILER_PLAN.md` from the template above.
4. Answer the four decisions.
5. Append HISTORY, rebuild index, verify, snapshot.
6. Open Phase 0 PR as draft.
7. Stop. Wait for review before opening Phase 1.
