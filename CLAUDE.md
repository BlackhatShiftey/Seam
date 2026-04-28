# CLAUDE.md

This model-specific guide is intentionally minimal.
Canonical protocol: `AGENTS.md`.
Current state snapshot: `PROJECT_STATUS.md`.
Historical continuity: `HISTORY_INDEX.md` and surgical reads from `HISTORY.md`.

Claude must follow the SEAM temporal chain:
- Read `AGENTS.md`, `PROJECT_STATUS.md`, `REPO_LEDGER.md`, `HISTORY_INDEX.md`, and `docs/CODE_LAYOUT.md` before changing repo state.
- Read `docs/DATA_ROUTING.md` when the task touches history, ledgers, maintenance records, routing, context budget, or auditability.
- Use `python -m tools.history.build_context_pack --route <route>` for task-specific history instead of loading all of `HISTORY.md` when a route exists.
- After any repo state change, append a `HISTORY.md` entry with the exact files changed, success/failure facts, verification performed, and unresolved next step if any.
- Rebuild `HISTORY_INDEX.md`, verify integrity, write a snapshot, and run `python -m tools.history.verify_continuity`.
- Run `python -m tools.history.verify_routing` after changing route classifications, route ledgers, or route-aware context behavior.
- Update `REPO_LEDGER.md` when the change affects stable repo policy, architecture, active/archive routing, runtime safety rules, durable operator workflows, or multi-agent protocol.
- Update `PROJECT_STATUS.md` when the current operating state or active focus changes.
- Preserve temporal chaining with `supersedes`; never edit old history to hide a failed attempt or collapse the timeline.

Claude-specific hard rule:
- Do not write Claude session links, share links, transcript links, provider URLs for private chats, API keys, passwords, tokens, or local `.env` values into commits, `HISTORY.md`, snapshots, handoffs, docs, or comments.
- If a secret, credential-bearing DSN, private key, or private session URL is found in the working tree, delete the local file or redact the value immediately. Do not preserve it elsewhere.
- When recording work, summarize the result and cite repo files only. If private session context matters, rewrite it as neutral operational state with no URL or credential.
- If a secret or private session URL is found in tracked history, stop and request explicit cleanup/rotation instructions instead of preserving or re-quoting it.
