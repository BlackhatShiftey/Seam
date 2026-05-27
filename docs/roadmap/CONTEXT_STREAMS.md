# SEAM Context Streams: Multi-Stream History Protocol

<!-- seam:item
id: roadmap:track:H
status: planned
status-since: 2026-05-15
status-by: history:165
supersedes: none
topics: roadmap, protocol, history, plan
priority: 0
phase: 1
-->

**Status:** Planned major workstream. Phase 1 locked. Phase 2 retrieval-feedback subset moved to now by HISTORY#243 because Track M produced enough outcome data to start.
**Extends:** `AGENTS.md`, `docs/DATA_ROUTING.md`, `tools/history/`.
**Related:** `docs/roadmap/SKILL_FACTORY.md` (the improvement-loop overlap is intentional; Phase 2 here feeds Skill Factory observations).

---

## 1. Origin

This document captures a multi-session design dialogue (closed at `HISTORY#165`, 2026-05-15) that audited SEAM's current history/index/routing protocol and concluded the single-stream `HISTORY.md` + `HISTORY_INDEX.md` pattern is the scaling ceiling for the system. The design preserved here is the agreed evolution path. Phase 1 will be implemented next. Phase 2 was originally deferred until ~4 weeks of Phase 1 operational data accumulated; HISTORY#243 narrows and starts the retrieval-feedback subset now because Track M already produced query/context/gold/outcome bundles and warm no-paid iteration data.

**Goal for future-me:** read this doc end-to-end and resume implementation cold without re-deriving the design.

---

## 2. Problem Statement

The current SEAM history protocol works extremely well at SEAM's current scale (164 entries, ~25K tokens, single canonical log). It breaks when:

- The roadmap grows beyond what a human can read at a glance, and "what's actually still active vs done" requires manual filtering.
- Experience (lessons, constraints, patterns, decisions discovered during work) accumulates inside HISTORY.md prose bodies — not structurally queryable, gets re-discovered, gets re-forgotten.
- External libraries / corpora the agent reads as part of its work have no first-class place in the index — they're either fully loaded (bloat) or fully ignored (loss).
- The single append-only `HISTORY.md` plus single derived `HISTORY_INDEX.md` is one stream. Adding more dimensions (roadmap, experience, libraries) by stuffing them into the same file collapses under its own weight.

The fix is **not** a new database, a new daemon, a new vector index, or a parallel context system. It is:

> Generalize the single-stream protocol into a **multi-stream protocol** where each growing dimension gets its own append-only log + derived index + (optional) materialized state file, joined by a single append-only `cross_index.md` for cross-stream temporal queries.

---

## 3. The Stream Model

A **stream** is an append-only event log for one dimension of repo state. Every stream uses the same file format, the same tooling (append, rebuild_index, roll_archive, verify), and the same event schema — parameterized only by `kind`.

The existing `HISTORY.md` + `HISTORY_INDEX.md` is one stream (the `history` stream). Phase 1 adds two more (`roadmap`, `experience`) and prepares the substrate for arbitrary `library/<name>` streams in Phase 4.

### 3.1 Stream Kinds

| Kind | Mandatory? | Purpose | Event examples |
|---|---|---|---|
| `history` | Yes (every repo) | Session events, repo state changes | session-event |
| `roadmap` | Opt-in (most repos) | Track status changes over time | status-change, item-added, item-retired |
| `experience` | Opt-in | Lessons, constraints, patterns, decisions | lesson-added, lesson-refined, lesson-superseded, lesson-promoted |
| `library/<corpus>` | Opt-in (per corpus) | Ingestion of external documents/code as queryable units | file-ingested, file-updated, file-removed, projection-rebuilt |
| `improvement` | Deferred to Phase 2 | Meta-stream: retrieval quality, outcome deltas, repeated hits, protocol drift | retrieval-signal, outcome-delta, repeated-hit, protocol-drift, propose-rule |

### 3.2 Directory Layout

```
.seam/
├── streams/
│   ├── history/
│   │   ├── log.md              ← derived mirror of root HISTORY.md in Phase 1 (canonicality flip deferred to a later phase)
│   │   ├── index.md            ← derived mirror of root HISTORY_INDEX.md in Phase 1
│   │   └── archive/
│   │       ├── 0001-1000.md    ← rolled chunk when log.md hits threshold (post-flip phases only)
│   │       └── chunk_index.md
│   ├── roadmap/
│   │   ├── log.md              ← append-only (new in Phase 1; no root counterpart)
│   │   ├── index.md            ← derived from log.md
│   │   └── archive/
│   ├── experience/
│   │   ├── log.md              ← append-only (new in Phase 1; no root counterpart)
│   │   ├── index.md            ← derived from log.md
│   │   └── archive/
│   └── library/
│       └── <corpus>/
│           ├── log.md
│           ├── index.md
│           ├── projections/    ← compact summaries per ingested unit (feeds projection_index)
│           └── archive/
├── routing_manifest.json       ← now covers all streams, not just history
├── cross_index.md              ← derived global timeline, regenerated from stream logs (new in Phase 1)
└── snapshots/                  ← unchanged: bounded handoff packs
```

**Phase 1 canonicality rule:** root `HISTORY.md` and `HISTORY_INDEX.md` remain the canonical history source. `.seam/streams/history/log.md` and `.seam/streams/history/index.md` exist only as derived mirrors, regenerated from the root files via a compatibility adapter. No symlinks (Windows / agent / sandbox edge cases). New streams (`roadmap`, `experience`) and the derived `cross_index.md` are authored fresh under `.seam/streams/`. The path canonicality flip for `history` is deferred to a later phase recorded in a separate HISTORY entry, only after every consumer (`build_context_pack`, `verify_*`, dashboards, MCP server, installers, snapshot writer, AGENTS.md guidance) is proven to read from either path.

Top-level human-authored files (`ROADMAP.md`, `docs/experience/...`) remain as **narrative views**. Streams contain the structural/temporal/precedence data.

---

## 4. Universal Event Schema

Every entry in every stream uses this format. Same delimiters, same field rules, same parser (generalized from `tools/history/history_lib.py`).

```
---BEGIN-<stream>-EVENT-#NNN---
id: <stream>:NNN
date: 2026-05-15T14:22:00Z          ← UTC, mandatory
agent: claude|codex|gemini|operator|...
kind: <event kind for this stream>  ← see taxonomy per stream
item: <optional entity id this event mutates, e.g. roadmap:track:G1>
event: <verb specific to kind>
from: <prior state, optional>
to: <new state, optional>
caused-by: <cross-stream ref, optional, e.g. history:165>
triggers: <cross-stream ref, optional>
supersedes: <same-stream id, or "none">
refs: <comma-separated file/symbol refs>
topics: <controlled vocab from AGENTS.md>
tokens: <int, estimated>
---
<body prose, 1-3 paragraphs max>
---END-<stream>-EVENT-#NNN---
```

**Cross-references** between streams use the syntax `<stream>:<NNN>` (e.g. `history:165`, `roadmap:042`). They are stable, immutable, and citable from any file. The optional `:sha8` suffix may be appended for integrity (e.g. `history:165:b3d6e2ef`).

**Topic vocabulary** stays bound to `AGENTS.md`'s controlled tag set. New tags require a vocab update commit, recorded in HISTORY.

---

## 5. Cross-Index Format

`.seam/cross_index.md` is the temporal join across all streams. **It is a derived artifact, not an append-only canonical log** — regenerated from per-stream `log.md` files by the same tooling that rebuilds per-stream indexes (mirroring how `HISTORY_INDEX.md` is derived from `HISTORY.md`). It is never edited by hand and never the source of truth for any event; if it goes missing, the rebuild command reproduces it deterministically from the stream logs.

```markdown
# Cross-Index

schema: seam-cross-index/v1
source: streams/*/log.md (derived; do not hand-edit)
hot_zone_max: 200
archive_pattern: archive/<lo>-<hi>.cross.md

## Hot Zone (latest 200 events, oldest first)

| utc | stream:id:hash | kind | event | topics | refs |
|---|---|---|---|---|---|
| 2026-05-15T14:22:00Z | history:165:a4b8d20f | session-event | done | roadmap,plan,protocol,history | docs/roadmap/CONTEXT_STREAMS.md |
| 2026-05-15T14:22:00Z | roadmap:001:7f2c91ab | status-change | now→planned | roadmap,plan | history:165 |

## Archive Pointers

| chunk | utc_range | event_count | streams | top_topics |
|---|---|---|---|---|
```

The cross-index is **the** thing agents pull at session start for temporal context across streams. It stays small because it's one line per event. On rebuild, when the hot zone exceeds 200 events, the oldest 200 are emitted into `archive/<lo>-<hi>.cross.md` and the archive-pointer table is regenerated. Rebuild is the same hash-gated re-runnable command pattern history already uses; it is safe to run thousands of times per day.

---

## 6. Materialized State Files + Marker Convention

For streams where humans want a readable current-state view (`roadmap`, `experience`), an optional `state.md` is derived from `log.md` and contains structured items with marker blocks:

```markdown
### Track G1: Document-to-Machine-Language Compiler

<!-- seam:item
id: roadmap:track:G1
status: done
status-since: 2026-04-27
status-by: history:145
supersedes: none
topics: compile, mirl
priority: done
-->

Description prose here. Humans edit prose freely. The marker block is the structured contract — anything outside it is narrative.
```

**Reconcile model (open decision, see §11):**

Two options for keeping `state.md` / `ROADMAP.md` and `log.md` in sync — pick at implementation time:

1. **Logged-canonical**: `log.md` is canonical, `state.md` is regenerated from log on every change. Operator edits state via tools (`seam-protocol roadmap-status set <track> <status>`), which writes to log and regenerates state.
2. **Authored-canonical**: `state.md` (or `ROADMAP.md`) is canonical, operator edits prose + markers freely. A reconciler diffs against the last seen state and appends backfill events to `log.md`. Optionally fired by a git hook.

**Recommendation:** start with logged-canonical for `experience` (events are the natural authoring unit), authored-canonical for `roadmap` (humans write roadmap prose naturally). `history` is already logged-canonical and stays that way.

---

## 7. Authored vs Logged Streams

| Property | Logged-canonical | Authored-canonical |
|---|---|---|
| Source of truth | `log.md` | `state.md` (or top-level file like `ROADMAP.md`) |
| State.md role | Derived view, regenerated on log change | Canonical content |
| Operator workflow | Edit via tool, which appends to log | Edit file directly |
| Reconciler | Not needed | Diff-and-backfill events into log |
| Best for | history, experience, library | roadmap (where narrative authorship matters) |

Both models honor the same `cross_index.md` and the same event schema. The difference is only in which file the human edits.

---

## 8. Two-Tier Indexing & Archive Rolling

Goal: **no single file an agent must read at session start exceeds ~500 lines** regardless of how long the repo has lived.

### 8.1 Per-stream `index.md`

```markdown
# <Stream> Index

total_entries: <N>
total_tokens: <T>
latest_id: <N>
source: streams/<kind>/log.md
schema: seam-stream-index/v1
hot_zone_max: 200
archive_pattern: archive/<lo>-<hi>.md

## Hot Zone (last 200 entries, newest first)

| id | date | status | hash | topics | supersedes |
|---|---|---|---|---|---|

## Cold Zone (archive chunk summaries)

| chunk | id_range | date_range | event_count | top_topics | token_estimate |
|---|---|---|---|---|---|
```

### 8.2 Archive rolling

When `log.md` exceeds threshold (default: 1000 entries OR 100KB, whichever first), the oldest contiguous chunk rolls to `archive/<lo>-<hi>.md`. The new `log.md` retains the most recent entries. Cross-stream supersedes references stay valid because IDs don't change after archival.

### 8.3 Projection embeddings at scale

At very large scale (10K+ entries per stream, or library streams indexing whole repos), `projection_index` (already in `seam_runtime/storage.py:173-182`) gets populated with compact summary text per archived chunk. Vector search over projections lets agents find relevant chunks without scanning all archives.

---

## 9. Migration Plan (Zero-Loss, Non-Disruptive)

Phase 1 migration steps. The working SEAM invariant — root `HISTORY.md` + `HISTORY_INDEX.md` as canonical history — is preserved. Path canonicality flip for `history` is **explicitly out of scope for Phase 1** and is recorded as a separate later HISTORY entry only after every consumer is proven to read from either path.

1. **Create `.seam/streams/history/` as a derived mirror.** Do not move, rename, or symlink root files. A new compatibility adapter (`tools/streams/history_adapter.py`) reads root `HISTORY.md` + `HISTORY_INDEX.md` and exposes them through the generic stream interface. The adapter writes `.seam/streams/history/log.md` and `.seam/streams/history/index.md` as byte-equivalent derived mirrors so generic stream tooling can be exercised end-to-end without changing canonicality. Mirrors are regenerated on every rebuild and verified against root files.
2. **No path move, no symlinks, no pointer stubs in Phase 1.** Windows symlink behavior, agent sandboxes, and existing operator muscle memory all make path migration too risky for the first implementation. Existing consumers (`build_context_pack`, `verify_*`, dashboards, MCP server, installers, snapshot writer, AGENTS.md guidance) continue to read root files unchanged in Phase 1. A separate later HISTORY entry will flip canonicality from root to `.seam/streams/history/` only after every consumer is proven to read from either path and a coordinated cutover plan is captured.
3. **Bootstrap `.seam/streams/roadmap/`** (new stream, no root counterpart):
   - Empty `log.md`, empty `index.md`.
   - One-shot parser: walk current `ROADMAP.md`, extract `### Track X` headings + the existing marker blocks and "Status:" prose, emit synthetic backfill events `kind: status-change` for each item. Records `supersedes: none` for the bootstrap event of each track.
   - Generate initial roadmap `state.md` from the bootstrap events (mirrors ROADMAP.md item structure with marker blocks). Authored-canonical reconcile: `ROADMAP.md` remains operator-edited; reconciler diffs and backfills events.
4. **Bootstrap `.seam/streams/experience/`** (new stream, no root counterpart):
   - Empty `log.md`, empty `index.md`.
   - No backfill in Phase 1. Experience entries start fresh.
   - Create `docs/experience/` directory with subdirs `constraints/`, `patterns/`, `anti-patterns/`, `decisions/` (the 4 kinds) and a README explaining the schema.
5. **Generate derived `.seam/cross_index.md`** by walking the history adapter output chronologically + the roadmap bootstrap events. The cross-index is rebuildable from stream logs at any time; this initial generation is just the first rebuild, not an append-only commitment.
6. **Add `tools/streams/`** alongside `tools/history/` (do not delete or rename `tools/history/`):
   - `tools/streams/streams_lib.py` parameterized by stream kind, with `history_adapter` providing the history-stream view onto root files.
   - `tools/streams/append.py` (takes `--stream <kind>`; refuses `--stream history` in Phase 1 — history appends still go through `tools/history/new_entry.py`).
   - `tools/streams/rebuild_index.py` works on any stream; for `history`, it delegates to the adapter and regenerates the derived mirror.
   - `tools/streams/verify_streams.py` covers all streams + cross-index; for `history`, it re-runs existing root-file verifications and additionally checks that the derived mirror matches.
   - `tools/history/*` remains unchanged in Phase 1 — both interfaces work, root files stay canonical.
7. **Update `routing_manifest.json`** to schema v3: routes can target a stream by `match_streams: [history, roadmap]` (default: history only — backwards-compat). Schema version bump must be recorded; existing routes continue to work without modification.
8. **Update `AGENTS.md`** with a new "Context Loop" subsection describing the 3-phase loop (start / during / end) and pointing at the stream substrate. Session Start / Session End sections continue to reference root `HISTORY.md` + `HISTORY_INDEX.md` as canonical in Phase 1 and additionally mention the new roadmap / experience / cross-index reads.
9. **Update `PROJECT_STATUS.md`** to reflect the Phase 1 landing. `REPO_LEDGER.md` gets a Track H entry at H1 implementation landing (not at design capture, per the existing rule).
10. **Final commit**: record H1 implementation as a HISTORY entry, run all verify gates (`verify_integrity`, `verify_routing`, `verify_continuity`, new `verify_streams`), write snapshot. Confirm root files unchanged byte-for-byte across the migration commit; the only history-stream changes are the new derived mirror and the new generic tooling.

---

## 10. Phase 1 Scope (LOCKED)

Deliverable: the substrate. No retrieval/runtime behavior changes yet — just the protocol substrate that future phases build on.

**In scope:**
- `seam_protocol/` package skeleton (or `tools/streams/`, decide at impl time — see §11)
- Schemas: `event.schema.json`, `cross_index.schema.json`, `stream_index.schema.json`
- Generalized append + rebuild_index + roll_archive + verify per stream
- Cross-index append + rebuild + verify
- Migration script: move history, bootstrap roadmap + experience, generate cross_index
- Roadmap parser (one-shot, ROADMAP.md → roadmap stream)
- AGENTS.md "Context Loop" section
- verify_streams.py gate (called by `seam doctor`)
- HISTORY entry + index rebuild + snapshot + all verify gates green
- The scoped regression command in `docs/setup.md` passes without test-count
  audit discrepancies; add tests for the new tooling

**Out of scope (deferred):**
- Generalized library walker (Phase 4)
- Retrieval changes to honor stream filters (Phase 3)
- Improvement stream (Phase 2)
- Vector embeddings of stream projections (Phase 4)

**Definition of done:**
1. Root `HISTORY.md` + `HISTORY_INDEX.md` unchanged byte-for-byte; history adapter produces `.seam/streams/history/log.md` + `index.md` as byte-equivalent derived mirrors; all existing supersedes/hashes still verify against the root files.
2. `seam doctor` returns PASS with all verify gates including new `verify_streams` (which checks every stream + cross-index + history-mirror byte-equivalence).
3. `python -m tools.streams.build_context_pack --stream history --latest 3` produces output equivalent to `python -m tools.history.build_context_pack --latest 3`. Both commands continue to work in Phase 1.
4. Roadmap stream contains backfilled status events for every Track in ROADMAP.md; `state.md` reconciles cleanly against ROADMAP.md.
5. Cross-index is regenerated from stream logs deterministically; deleting it and re-running rebuild produces the identical file.
6. The existing test suite passes unchanged; new test coverage for streams + adapter + cross-index rebuild ≥ 90%.

---

## 11. Open Decisions for Phase 1 Implementation

Decide at implementation kickoff, not in this doc:

1. **Package location**: `seam_protocol/` (pip-installable for templating into other repos) vs `tools/streams/` (in-repo only, simpler for v1). **Lean:** `tools/streams/` for Phase 1; promote to `seam_protocol/` in Phase 3 when templating becomes the goal.
2. **Reconcile model for roadmap**: logged-canonical vs authored-canonical (see §7). **Lean:** authored-canonical for roadmap to preserve operator narrative authorship.
3. **Archive threshold**: 1000 entries, 100KB, or both. **Lean:** "1000 entries OR 100KB whichever first" — works for both dense (library) and sparse (history) streams.
4. **Backwards-compat duration**: 30 days of `HISTORY.md` shim? Longer? **Lean:** 30 days, then remove shim in a follow-up HISTORY entry. Any external tooling has time to update.
5. **Topic vocabulary**: add `streams`, `cross-index`, `experience`, `library` to AGENTS.md controlled set, or stay strict and reuse `protocol`, `history`, `plan`? **Lean:** add the four new tags via an explicit vocab update commit during migration.
6. **State.md auto-regeneration trigger**: post-append hook, periodic batch, or on-demand? **Lean:** post-append for logged-canonical streams, on-demand reconcile for authored-canonical.

---

## 12. Phase 2 — Improvement Streams (START TRACK M SUBSET NOW)

**Trigger status:** Satisfied for the Track M retrieval-feedback subset by operator decision in HISTORY#243. The broader improvement-stream design remains guarded, but the immediate work can start from existing LoCoMo artifacts and current no-paid retrieval slices.

**Design (preserved here in full so resume is cold):**

A fifth stream — `streams/improvement/` — is a **meta-stream** that captures signals about SEAM's own performance and proposes (never autonomously applies) protocol refinements.

### 12.1 Event kinds

| Event kind | Trigger | Example body |
|---|---|---|
| `retrieval-signal` | A search returned record N; agent used / ignored it; outcome known | "history:145 retrieved for query 'pgvector setup', not cited in next 3 entries — score-down for that topic" |
| `outcome-delta` | A plan/forecast in stream X was followed by actual outcome Y; delta recorded | "roadmap:042 forecast done by 2026-05-01, actual done at 2026-05-08, +7d slip" |
| `repeated-hit` | Same constraint/pattern observed in experience stream N+ times | "constraint 'pgvector takes 3s to be query-ready' seen 4 times — propose promotion to L2 pattern" |
| `protocol-drift` | A rule from AGENTS.md / REPO_LEDGER.md violated N times across recent history | "secret-hygiene rule tripped 2x in 30 days — propose refinement" |
| `propose-rule` | A synthesized proposal ready for operator review | "promote constraint X to AGENTS.md rule under §Security" |

### 12.2 Trust gradient (structural)

Experience entries earn promotion in stages, with each promotion recorded as an event:

- **L1 (hypothesis)**: 1 sighting. Lives only in `experience` stream; not surfaced in default retrieval.
- **L2 (pattern)**: 3+ sightings OR operator-flagged. Promoted via `experience:lesson-promoted` event; gets a `projection_index` row so it appears in compact memory search.
- **L3 (codified)**: operator-approved `propose-rule` proposal. Written into `AGENTS.md` or `REPO_LEDGER.md` as a rule. The codification event in `improvement` stream links to the HISTORY entry that performed the edit.

### 12.3 Auto-propose / manual-approve guardrail

**Hard rule: SEAM never writes to `AGENTS.md`, `REPO_LEDGER.md`, or `PROJECT_STATUS.md` autonomously.** Improvement-stream proposals are surfaced via `seam improvement review`, which displays pending `propose-rule` events. Operator runs `seam improvement accept <id>` or `seam improvement reject <id> --reason <text>`. Accepted proposals trigger a HISTORY entry that records the protocol edit; rejected proposals stay as audit trail with the rejection reason.

This is **the** safety mechanism. Without it, the improvement stream would self-corrupt the protocol over time.

### 12.4 Relationship to Skill Factory

The Skill Factory (`docs/roadmap/SKILL_FACTORY.md`) describes a similar observe → propose → verify → promote loop for skills. The improvement stream is the **data substrate** the Skill Factory observes from. Skill Factory observations become `retrieval-signal` and `repeated-hit` events; Skill Factory proposals become `propose-rule` events. The two workstreams converge in Phase 2.

### 12.5 Immediate Track M retrieval-feedback slice

Implement a narrow retrieval-event substrate before any autonomous learning or
weight tuning:

- persist query, scope, candidate ids, ranks, scores/reasons, context hash,
  gold answer, derived gold-hit ids, context_recall, judge score, answer,
  run id, timestamp, and stale-source flags;
- backfill existing LoCoMo bundles for diagnostic history, explicitly marking
  pre-HISTORY#240 and pre-HISTORY#242 records as stale;
- generate fresh no-paid labels from the current code path and split into
  dev/holdout before tuning scoring weights or training rerankers;
- write structured experience events for Track M attempts (`lever_tried`,
  baseline, result, conclusion);
- surface rule/ranking-policy proposals via `seam improvement review`.

Do not treat `unknown` with high context recall as negative retrieval feedback
without further classification; it may be an answerer failure.

### 12.6 Longer-horizon signals

Signals beyond Track M still depend on real usage. Likely candidates:

- Topic-route effectiveness (which routes return records that get cited vs ignored)
- Roadmap velocity (now → done time per track)
- Experience hit rate (which constraints fire most, which never fire after promotion)
- Context-pack token efficiency (token-budget vs entries-used ratio)

These broader signals still need 2-4 weeks of data before patterns become obvious. Don't pre-build event kinds for signals we can't yet measure.

---

## 13. Phase 3 — Retrieval Integration (LATER)

Once streams exist, retrieval needs to honor them:

- `seam memory search --stream <kind>` filters by source stream
- `build_context_pack --include history,roadmap,experience` selects multiple streams
- Default retrieval excludes `roadmap:status=done`, `experience:status=superseded`, `improvement:status=rejected` unless explicitly requested
- The existing `mix` retrieval mode learns to weight by stream-kind
- `cross_index.md` walking becomes available as a `--around <event_id>` flag

This is a runtime change, larger than Phase 1 substrate. Defer until Phase 1 is stable.

---

## 14. Phase 4 — Generalized Library Streams (LATER)

Once Phase 1-3 work for the canonical streams, generalize to arbitrary external corpora:

- `seam-protocol ingest <path> --ns library.<name>`: walks markdown by heading, source by AST symbols, creates MIRL records with `raw_spans` byte/line ranges, populates `document_status` + `projection_index` + library stream events.
- Re-runnable with hash gating (existing `vector.stale_records` + `document_status.source_hash`).
- **Not a daemon.** A hash-gated re-runnable command, optionally fired by a file watcher or git hook.
- Library namespaces (`ns=library.<name>`) keep external content separate from canonical `local.default` / repo namespaces.
- Vector projections of library content go through `projection_index` (compact summary embedded, not raw content).

---

## 15. Why This Is Not a Daemon

A background indexer writing to canonical SQLite would compete for write locks against:
- The Textual dashboard
- The MCP stdio server (running per agent session)
- The CLI (`seam memory ...`, `seam ingest ...`)
- The snapshot writer
- `verify_*` tools mid-run

It would also create write amplification on unchanged content and snapshot drift (history snapshots could capture mid-write states).

The correct primitive is **a content-hash-gated re-runnable command**, optionally fired by a file watcher or git hook. Safe to run thousands of times per day. No locks held longer than a single write. Cache-coherent because content hashes drive skip decisions.

This rule is non-negotiable across all phases.

---

## 16. Relationship to Existing SEAM Concepts

| Existing concept | Role in stream model |
|---|---|
| `HISTORY.md` | Remains canonical at repo root in Phase 1; surfaced as the `history` stream via compatibility adapter; `streams/history/log.md` is a byte-equivalent derived mirror. Path canonicality flip deferred to a separate later phase. |
| `HISTORY_INDEX.md` | Remains canonical at repo root in Phase 1; `streams/history/index.md` is a derived mirror. Same schema. |
| `routing_manifest.json` | Schema v3 adds `match_streams` field; routes can target one or many streams; existing routes continue to work unchanged |
| `tools/history/*` | Unchanged in Phase 1. New `tools/streams/*` adds generic stream tooling; for `history`, it delegates through the adapter to root files. Both interfaces coexist. |
| `ROADMAP.md` | Stays as operator-authored narrative; `state.md` derived view added under `streams/roadmap/` |
| `REPO_LEDGER.md` | Operator-authored; stable repo facts. Improvement stream may propose edits. |
| `PROJECT_STATUS.md` | Operator-authored; current operating state. Improvement stream may propose updates. |
| `.seam/snapshots/` | Unchanged. Snapshots remain bounded handoff packs. |
| `seam_runtime/storage.py:173-182` (`projection_index`) | Populated by stream projections (compact summaries per indexed unit). Already in schema. |
| `seam_runtime/vector.py` (`stale_records`, `source_hash`) | The idempotency primitive for library stream ingestion. |
| MIRL `CLM/STA/EVT/REL` records | Roadmap items, experience entries, library units all materialize as MIRL records under appropriate namespaces. |
| `agent_memory.compact_memory_index` / `full_memory_records` / `neighbor_timeline` | Already implement Layer 1 / Layer 3 / Layer 2 of progressive disclosure. No new code needed for these layers; just new sources feeding in. |

---

## 17. References

- **Design conversation:** closed at `HISTORY#165` (2026-05-15)
- **Audit foundation:** prior session classifier exploration in `HISTORY#155`, `HISTORY#150`, `HISTORY#143` (protocol/context route)
- **Stream model precedent:** existing `HISTORY.md` + `HISTORY_INDEX.md` + `routing_manifest.json` + `verify_continuity.py` — the multi-stream protocol is a generalization of this same pattern
- **Improvement loop precedent:** `docs/roadmap/SKILL_FACTORY.md`, `docs/roadmap/AGENT_COMPILER.md` — Phase 2 here feeds those workstreams
- **Why not a daemon:** §15 above; also `REPO_LEDGER.md` Runtime Service Safety Policy and Context Budget Policy
- **MIRL substrate:** `seam_runtime/storage.py`, `seam_runtime/agent_memory.py`, `seam_runtime/retrieval.py`, `seam_runtime/vector.py`
- **Context pack tool to generalize:** `tools/history/build_context_pack.py`
- **Routing manifest schema to extend:** `tools/history/routing_manifest.json`

---

## 18. Resume Checklist (for future-me)

When picking this up cold:

1. Re-read this doc top to bottom.
2. Read `HISTORY#165` (the design-capture entry).
3. Decide the §11 open questions (or accept the leans).
4. Run Phase 1 §10 deliverables in order; ship as one PR.
5. Operate on Phase 1 substrate for ~4 weeks; collect informal observations.
6. Return to this doc, re-read §12 (Phase 2 improvement streams), and design the event kinds from real data.
7. Build Phase 2 + Phase 3 + Phase 4 in that order, with verify gates each step.

If anything in this doc conflicts with what the repo currently does at resume time, **trust the repo and update this doc** — capture the divergence as a new HISTORY entry and note here why the design shifted.
