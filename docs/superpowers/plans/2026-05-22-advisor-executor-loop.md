# Advisor Executor Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable SEAM protocol where Codex or true Opus acts as Advisor and `claude-ds`/DeepSeek acts as bounded code executor.

**Architecture:** Keep the loop text-only and auditable first: a canonical SOP defines authority boundaries, a DeepSeek prompt makes the executor behavior paste-ready, and the existing DeepSeek corrections ledger records the new escalation rule. Do not automate model-to-model calls yet.

**Tech Stack:** Markdown SOPs and prompts, SEAM history/stream verification tools.

---

### Task 1: Add Advisor-Executor Protocol Docs

**Files:**
- Create: `docs/SOP_ADVISOR_EXECUTOR_LOOP.md`
- Create: `docs/prompts/DEEPSEEK_ADVISED_EXECUTOR_PROMPT.md`
- Modify: `docs/ledgers/agents/deepseek.md`
- Modify: `REPO_LEDGER.md`

- [x] **Step 1: Create the SOP**

Write `docs/SOP_ADVISOR_EXECUTOR_LOOP.md` with these sections:
- Purpose
- Roles and authority
- Packet formats
- Escalation rules
- Review and commit rules
- Improvement loop
- Paste-ready packet templates

- [x] **Step 2: Create the DeepSeek prompt**

Write `docs/prompts/DEEPSEEK_ADVISED_EXECUTOR_PROMPT.md` as a reusable prompt for `claude-ds`, explicitly naming the Advisor as final say and requiring DeepSeek to stop on uncertainty.

- [x] **Step 3: Add DeepSeek ledger card C6**

Append a new card to `docs/ledgers/agents/deepseek.md` requiring DeepSeek to escalate architecture, scope, missing context, and failing pre-existing tests instead of inventing strategy.

- [x] **Step 4: Add stable ledger pointer**

Add one stable `REPO_LEDGER.md` bullet under Temporal Continuity Policy noting that advised DeepSeek execution is governed by `docs/SOP_ADVISOR_EXECUTOR_LOOP.md`.

- [x] **Step 5: Verify docs**

Run:

```bash
git diff --check
rg -n "TODO|TBD|sk-|hf_|claude\\.ai|chat\\.openai" docs/SOP_ADVISOR_EXECUTOR_LOOP.md docs/prompts/DEEPSEEK_ADVISED_EXECUTOR_PROMPT.md docs/ledgers/agents/deepseek.md REPO_LEDGER.md
```

Expected: `git diff --check` exits 0. The `rg` command may match explanatory text only; it must not reveal secret values or private session URLs.

### Task 2: SEAM Closeout

**Files:**
- Modify: `HISTORY.md`
- Modify: `HISTORY_INDEX.md`
- Modify: `.seam/streams/history/log.md`
- Modify: `.seam/streams/history/index.md`
- Modify: `.seam/cross_index.md`
- Modify: `.seam/cross_index_archive/*`
- Create: `.seam/snapshots/*.json`

- [ ] **Step 1: Append history**

Use the repo history tooling or an append-only entry to record the protocol docs, verification, and the pre-existing unrelated dirty test file if still present.

- [ ] **Step 2: Rebuild derived state**

Run:

```bash
.venv/bin/python -m tools.history.rebuild_index
.venv/bin/python -m tools.streams.history_adapter
.venv/bin/python -m tools.streams.rebuild_cross_index
.venv/bin/python -m tools.history.write_snapshot --agent codex --latest 2 --token-budget 2600
```

- [ ] **Step 3: Verify continuity**

Run:

```bash
.venv/bin/python -m tools.history.verify_integrity
.venv/bin/python -m tools.history.verify_routing
.venv/bin/python -m tools.history.verify_continuity
.venv/bin/python -m tools.streams.verify_streams
```

Expected: all commands exit 0.
