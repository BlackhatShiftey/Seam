# SEAM Skills Compiler — Implementation Plan

**Status:** Phase 0 (decisions only)
**Track:** H (Agent Compiler)
**Extends:** `docs/roadmap/AGENT_COMPILER.md` Phase 4A (H1, H2, H5)
**Brief:** `docs/roadmap/SKILLS_COMPILER_BRIEF.md`

This plan records the four blocking decisions for the Skills Compiler workstream
and the per-phase ledger. No code is introduced by this document.

## Decision 1 — Canonical source vs compile target

**Choice:** the 9 existing files under `.opencode/skills/` are **compile
targets**, not canonical source. Their intent will be lifted into structured
specs at `skills/source/*.yaml` as each is needed. Existing files become the
audit baseline against which generated outputs are compared.

**Reasoning:**

- The `AGENT_COMPILER.md` H1 SOP step 1 already names `skills/source/*.yaml`
  as the canonical spec location. Treating `.opencode/skills/` as source would
  contradict the existing spec.
- All 9 files are OpenCode-shaped (markdown + frontmatter under
  `.opencode/skills/<name>/SKILL.md`). That is one harness's preferred shape.
  Using them as canonical would couple the source format to one harness and
  defeat the multi-target rendering goal.
- They were hand-written. There is no current generator they round-trip
  through. Treating them as source would freeze that hand-written state
  permanently.

**Per-skill classification and phase assignment:**

| Existing skill                    | Future canonical source                          | Phase  |
|-----------------------------------|--------------------------------------------------|--------|
| `seam-session-closeout`           | `skills/source/session-end.yaml`                 | 1      |
| `seam-repo-navigator`             | `skills/source/repo-navigator.yaml`              | post-6 |
| `seam-architect`                  | `skills/source/architect.yaml`                   | post-6 |
| `seam-implementation-planner`     | `skills/source/implementation-planner.yaml`      | post-6 |
| `seam-implementation-executor`    | `skills/source/implementation-executor.yaml`     | post-6 |
| `seam-test-hardener`              | `skills/source/test-hardener.yaml`               | post-6 |
| `seam-roadmap-ledger-updater`     | `skills/source/roadmap-ledger-updater.yaml`      | post-6 |
| `seam-skill-sync-auditor`         | `skills/source/skill-sync-auditor.yaml`          | post-6 |
| `seam-github-publisher`           | `skills/source/github-publisher.yaml`            | post-6 |

Only `session-end` is in scope for Phases 1–7. The other 8 source specs are
written after the Skills Compiler is proven on `session-end` end-to-end. This
is intentional: the first source spec is the load-bearing one; the rest are
rote application once the pattern is verified.

## Decision 2 — Output locations

**Choice:** mixed. Output destination is declared per target profile.

| Target  | Generated path (pre-apply)                                | Installed path (post-apply)                  | Tracked in repo? |
|---------|-----------------------------------------------------------|----------------------------------------------|------------------|
| Claude (OpenCode) | `skills/generated/claude/<skill>/SKILL.md`     | `.opencode/skills/seam-<skill>/SKILL.md`     | Yes (both)       |
| Cursor  | `skills/generated/cursor/<skill>/<skill>.mdc`             | `.cursor/rules/seam-<skill>.mdc`             | Operator-local   |
| Claude Code (`~/.claude/skills/`) | (same as OpenCode generated) | `~/.claude/skills/seam-<skill>/SKILL.md`     | Operator-local   |
| Generic markdown | `skills/generated/generic/<skill>/<skill>.md`      | (operator-controlled)                        | Generated only   |

`.opencode/skills/` is already tracked in this repo (the 9 existing files), so
its installed path is repo-tracked. Other harnesses' installed locations are
operator-local and may not exist on every machine. The `apply` command in
Phase 6 must read the target's profile to know where to write and whether to
write at all.

**Reasoning:**

- `.opencode/skills/` is already part of the repo's source-of-truth state and
  is read by OpenCode-based agents working inside the repo. Keeping it
  repo-tracked preserves multi-agent continuity.
- `~/.claude/skills/` and `.cursor/rules/` are per-machine operator state.
  Forcing them into the repo would commit operator-specific paths and break
  on other machines.
- Generated artifacts under `skills/generated/` are repo-tracked so reviewers
  can diff what the compiler produces without running it.

## Decision 3 — Provenance v1 scope

**Choice:** plain SHA-256 over a fixed field set. No signing, no Merkle, no
external attestation in v1.

**v1 provenance fields (embedded in every generated artifact and in the HS/1
surface in Phase 7):**

- `source_spec_sha256` — SHA-256 of `skills/source/<skill>.yaml` bytes
- `model_profile_sha256` — SHA-256 of the target profile YAML bytes
- `compiler_version` — semver string read from `seam_runtime/skills/__init__.py`
- `generated_at` — ISO-8601 UTC timestamp
- `git_sha` — `git rev-parse HEAD` at compile time, or `unknown` if not in a
  git checkout
- `target` — target name (e.g. `claude`, `cursor`)
- `skill` — skill name (e.g. `session-end`)

**Out of scope for v1, deferred to provenance v2:**

- ed25519 or PGP signing of generated artifacts
- Merkle trees over the manifest of generated skills
- External transparency log publication
- Hardware-backed key storage policy

Provenance v2 will be opened as a separate workstream under Track F once Track
F's foundational primitives (`seam audit log`, `seam audit verify`,
`seam redact preview`) exist. Until then v1 plain hashes are the only
provenance surface.

## Decision 4 — Track placement

**Choice:** Track H (Agent Compiler), per `AGENT_COMPILER.md`.

Track F (Trust, Security, Auditability, Lineage) provides primitives that the
Skills Compiler consumes:

- `seam audit log` (Track F) — Phase 7 will optionally emit an audit event per
  compile/apply when this command exists. Until it exists, the Skills Compiler
  records its own HISTORY entries and writes to `skills/generated/`; no
  dependency on Track F is introduced.
- HS/1 surfaces (already implemented, not Track F) — Phase 7 wraps generated
  artifacts as HS/1 surfaces using the existing `seam surface compile`
  pipeline. This is reuse, not a Track F dependency.
- `seam trust report` (Track F, Vision) — a future dashboard panel may surface
  Skills integrity scores under a trust report. The Skills Compiler does not
  call into this command in any phase covered by this plan.

The Skills Compiler must not be described as "the flagship deliverable of
Track F." It is Track H's first major deliverable. Track F's flagship is
whichever of its own foundational commands lands first.

## Out of scope for this plan

- Signing / Merkle (provenance v2)
- `seam trust report` integration (waits on Track F)
- `seam secrets scan` integration (waits on Track F)
- Dashboard Skills panel (waits on A-Web wiring + Phase 7)
- H4 optimizer / H3 benchmark suite (Phase 4B / 4C of `AGENT_COMPILER.md`)

## Phase ledger

| Phase | Title                                          | Status      | HISTORY entry | Branch                                  |
|-------|------------------------------------------------|-------------|---------------|-----------------------------------------|
| 0     | Decisions doc (this file)                      | in-progress | TBD           | claude/seam-trust-security-manual-8mhEL |
| 1     | SkillIR + first canonical source spec          | planned     | —             | (same)                                  |
| 2     | First renderer (Claude) + sample output        | planned     | —             | (same)                                  |
| 3     | `seam skills compile` CLI                      | planned     | —             | (same)                                  |
| 4     | Second renderer (Cursor)                       | planned     | —             | (same)                                  |
| 5     | `seam skills audit` (read-only)                | planned     | —             | (same)                                  |
| 6     | `seam skills apply` (gated)                    | planned     | —             | (same)                                  |
| 7     | HS/1 attestation wrap + `seam skills verify`   | planned     | —             | (same)                                  |
| 8+    | Optimizer, benchmark suite, Track F integration| deferred    | —             | (separate workstream)                   |

When each phase lands, update its row's status to `done` and fill in the
HISTORY entry id.

## Anti-patterns explicitly rejected by this plan

These are restated from the brief so they cannot be rediscovered as "new
ideas" mid-build:

- Combining multiple phases into one commit
- Adding Merkle proofs or ed25519 signing to v1
- Hooking into `seam trust report`, `seam secrets scan`, `seam audit log`, or
  any other Vision-tagged command
- Treating `AGENTS.md`, `REPO_LEDGER.md`, `PROJECT_STATUS.md`, or
  `HISTORY_INDEX.md` as direct SkillIR input
- Writing to `.opencode/skills/` without explicit `--confirm` and an apply
  HISTORY entry
- Calling the work a "Track F flagship"
- Hand-editing `HISTORY_INDEX.md`
- Creating empty README placeholders in `docs/security/` or `docs/contracts/`
- Adding a dashboard panel before Phase 7 lands
