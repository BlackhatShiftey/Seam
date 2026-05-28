# QWEN.md

This model-specific guide is intentionally minimal.
Canonical protocol: `AGENTS.md`.
Current state snapshot: `PROJECT_STATUS.md`.
Historical continuity: `HISTORY_INDEX.md` and surgical reads from `HISTORY.md`.

Qwen must follow the SEAM temporal chain:
- Read `AGENTS.md`, `PROJECT_STATUS.md`, `REPO_LEDGER.md`, `HISTORY_INDEX.md`, and `docs/CODE_LAYOUT.md` before changing repo state.
- Read `docs/DATA_ROUTING.md` when the task touches history, ledgers, maintenance records, routing, context budget, or auditability.
- Use `python -m tools.history.build_context_pack --route <route>` for task-specific history instead of loading all of `HISTORY.md` when a route exists.
- After any repo state change, append a `HISTORY.md` entry with the exact files changed, success/failure facts, verification performed, and unresolved next step if any.
- Rebuild `HISTORY_INDEX.md`, verify integrity, write a snapshot, and run `python -m tools.history.verify_continuity`.
- Run `python -m tools.history.verify_routing` after changing route classifications, route ledgers, or route-aware context behavior.
- Update `REPO_LEDGER.md` when the change affects stable repo policy, architecture, active/archive routing, runtime safety rules, durable operator workflows, or multi-agent protocol.
- Update `PROJECT_STATUS.md` when the current operating state or active focus changes.
- Preserve temporal chaining with `supersedes`; never edit old history to hide a failed attempt or collapse the timeline.

Qwen-specific hard rules:
- Do not write Qwen session links, transcript links, API keys, passwords, tokens, or local `.env` values into commits, `HISTORY.md`, snapshots, handoffs, docs, or comments.
- Before stopping a session that touched runtime code, run `pytest --collect-only` and the relevant test slice; a session that leaves the working tree dirty without a HISTORY entry violates the cut-off-recovery rule in `AGENTS.md`.
- If a refactor renames or extracts symbols, update every reference in the same edit; do not leave undefined names in committed or worktree code. New tests that import symbols must compile alongside the implementation they target.
- Work in PRs against a feature branch; `main` is protected by the `Protect main` ruleset and direct pushes are refused.
