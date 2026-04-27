# AGENTS.md

Canonical multi-agent protocol for this repo. All models use the same rules.

## Session Start

Read in order:
1. `PROJECT_STATUS.md`
2. `REPO_LEDGER.md`
3. `HISTORY_INDEX.md`
4. `docs/CODE_LAYOUT.md`
5. `docs/DATA_ROUTING.md` when the task touches history, ledgers, maintenance records, routing, context budget, or auditability.

Then:
- Prefer latest valid snapshot in `.seam/snapshots/`.
- If snapshot verification fails, fall back to index-first reads.
- Use `python -m tools.history.build_context_pack` to load only the latest, route-relevant, topic-relevant, or supersedes-chain entries needed for the task.
- Never read all of `HISTORY.md`; pull only needed entries by indexed line/byte ranges.
- Treat `archive/code/`, `docs/archive/`, `build/`, `.venv/`, and generated/cache paths as inactive unless the user explicitly asks for historical or retired material.
- For normal code search, stay in active paths: `seam_runtime/`, `seam.py`, `experimental/`, `tools/`, `scripts/`, `installers/`, `docs/`, tests, and root status files.

## Session End

If state changed:
1. Append one entry to `HISTORY.md`.
2. Rebuild `HISTORY_INDEX.md`.
3. Write one snapshot JSON.
4. Run `python -m tools.history.verify_continuity`.

Use `tools/history/*` scripts for entry writes, index rebuild, integrity verification, and snapshot creation.

## Temporal Chain

- Every material change must preserve a clear chain from previous state to new state. Record what changed, why, verification performed, failures or partial work, and the next unresolved step when one exists.
- Use `supersedes` to link follow-up work to the latest relevant entry. Do not overwrite or rewrite older history entries to make the timeline look cleaner.
- Update `REPO_LEDGER.md` when a change affects stable repo policy, architecture, active/archive routing, runtime safety rules, durable operator workflows, or cross-agent protocol. Routine implementation details belong in `HISTORY.md` with pointer cards from docs when needed.
- Update `PROJECT_STATUS.md` when the current operating state or active focus changes. Do not leave status files stale after changing what future agents should believe.
- Use concise refs to changed files, tests, commands, and snapshots. Record failures as failures, skipped verification as skipped, and assumptions as assumptions.
- Keep context packs bounded. Prefer `build_context_pack --topics <tags> --latest <n> --token-budget <budget>` over broad history reads.
- Use route-aware packs for durable areas: `build_context_pack --route maintenance/docker`, `--route protocol/context`, or another route from `tools/history/routing_manifest.json`.

## Classification Routing

- `tools/history/routing_manifest.json` is the mutable classification map for logical branches such as `maintenance/docker` and `protocol/context`.
- Classifications may be added, moved, retired, or recreated, but route decisions must remain auditable through `HISTORY.md` and manifest lifecycle fields.
- Delete a classification from active use by marking it `retired` or `moved`; do not erase the only record of why the route existed.
- Store stable route facts under `docs/ledgers/` when they are useful for future search. Keep chronology in `HISTORY.md`.
- Run `python -m tools.history.verify_routing` after changing classifications, ledgers, or route-aware context behavior.

## Security Rules

- Never commit API keys, passwords, tokens, private keys, local `.env` values, provider session links, chat/share links, thread links, or local agent transcript links.
- Do not put Claude/Codex/ChatGPT session URLs or generated conversation links in commit messages, `HISTORY.md`, snapshots, handoffs, docs, or comments. Summarize the useful state and point to repo files instead.
- Use placeholders such as `<local-password>` only in examples; real values must live in ignored local files or the operator environment.
- If a secret, credential-bearing DSN, private key, or private session URL is found in the working tree, delete the local file or redact the value immediately. Do not preserve it in another file, history entry, snapshot, commit message, or chat response.
- Before staging, scan tracked and untracked candidate files for secret-shaped strings and provider session URLs. If a secret or private session URL was committed, stop and ask for history-rewrite/rotation handling instead of copying it into another artifact.

## Invariants

- `HISTORY.md` is append-only.
- `HISTORY_INDEX.md` is derived state.
- Snapshot integrity must be verified before use.
- Status updates never edit old entries; use `supersedes`.
- Use pointer cards across docs (`see HISTORY#NNN`), not duplicated prose.
- Active docs/code and archived docs/code must stay separated; do not copy stale archive prose or code back into active paths without rewriting and verifying it.

## Entry Schema

Required fields per entry:
`id`, `date`, `agent`, `status`, `topics`, `commits`, `refs`, `supersedes`, `tokens`, and body.

Valid status values:
`planned`, `in-progress`, `done`, `changed`, `deferred`, `abandoned`.

## Topic Vocabulary

Only use tags from this controlled set:

`compile, mirl, persist, verify, retrieval, search, rank, vector, sbert, chroma, pgvector, docker, lexical, compress, lx1, roundtrip, codec, benchmark, holdout, bundle, fixture, diff, gold-standard, dashboard, tui, textual, animation, graph, chat, installer, windows, linux, wsl2, pyproject, extras, command, doctor, demo, naming, alias, readme, ledger, roadmap, plan, status, history, session, handoff, snapshot, mcp, multi-agent, protocol, integrity, classification, audit`
