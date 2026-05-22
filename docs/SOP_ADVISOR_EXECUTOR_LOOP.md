# SOP — Advisor / Executor Loop for DeepSeek

Issued: 2026-05-22
Owner pattern: Advisor owns strategy, review, final approval, commits, and
history closeout. DeepSeek via `claude-ds` executes bounded implementation
packets and escalates uncertainty instead of inventing architecture.

## Purpose

This SOP defines the operating loop for using a higher-reasoning Advisor
(Codex now, true Claude Opus when available) with a cheaper executor
(`claude-ds`, DeepSeek through an Anthropic-compatible endpoint). The goal is
to keep expensive reasoning concentrated in planning, review, and correction
while letting DeepSeek perform scoped code writing, tests, and command
execution.

The loop is intentionally manual first. Do not add autonomous model-to-model
calls until the packet protocol is proven on real SEAM work.

## Roles

### Advisor

Advisor may be Codex or true Claude Opus. `claude-ds` using an Anthropic-style
endpoint is not true Opus even when its wrapper maps Opus model aliases to a
DeepSeek model.

Advisor owns:

- architecture and task decomposition
- SOP and blueprint authoring
- file-scope decisions
- context injection when DeepSeek lacks the right repo facts
- review of every DeepSeek diff
- final pass/fail judgment
- commits, history entries, snapshots, and pushes unless an SOP says otherwise

### Executor

Executor is DeepSeek via `claude-ds`.

Executor owns:

- writing code within the packet's allowed files
- writing deterministic tests requested by the packet
- running exactly the packet's verification commands
- returning structured evidence
- escalating blockers before expanding scope

Executor does not own:

- architecture changes
- scope expansion
- cross-agent protocol changes
- history closeout unless Advisor explicitly delegates it
- commits or pushes unless Advisor explicitly delegates them

## Control Loop

1. Advisor writes an `ADVISOR_TASK_PACKET`.
2. DeepSeek executes the packet on a clean branch or worktree.
3. DeepSeek returns `EXECUTOR_HANDOFF`.
4. Advisor independently reviews the diff and reruns verification.
5. Advisor either commits, sends `ADVISOR_CORRECTION_PACKET`, or takes over.
6. If DeepSeek made a reusable mistake, Advisor appends a card to
   `docs/ledgers/agents/deepseek.md` and folds the rule into future prompts.

## Packet Format

```text
ADVISOR_TASK_PACKET
task_id: <stable id>
advisor: <codex|opus>
executor: claude-ds
goal: <one sentence>
branch: <branch name or "use current branch">
allowed_files:
- <path>
forbidden_files:
- HISTORY.md
- HISTORY_INDEX.md
- PROJECT_STATUS.md
- REPO_LEDGER.md
- ROADMAP.md
- .seam/**
- archive/**
- docs/archive/**
- build/**
- .venv/**
- test_seam/**
required_reads:
- PROJECT_STATUS.md
- REPO_LEDGER.md
- HISTORY_INDEX.md
- docs/CODE_LAYOUT.md
- docs/DATA_ROUTING.md
- docs/ledgers/agents/deepseek.md
implementation_steps:
1. <specific step>
tests:
- <exact command>
stop_if:
- architecture decision needed
- allowed file scope is insufficient
- pre-existing test failure appears
- command output contradicts the packet
- secrets, credentials, private session links, or datasets would be touched
handoff_required:
- files_changed
- tests_run
- command_outputs_summary
- unresolved_questions
- diff_scope_statement
```

## Executor Escalation Format

DeepSeek must stop and return this block instead of guessing:

```text
ADVISOR_ESCALATION
task_id: <same id>
blocked_on: <specific blocker>
evidence:
- <command or file ref>
decision_needed: <exact question>
attempted:
- <what was tried, if anything>
current_diff:
- <files changed or "none">
recommended_next_step: <executor recommendation, optional>
```

## Advisor Response Formats

Use this when DeepSeek should continue:

```text
ADVISOR_PLAN
task_id: <same id>
decision: <what to do>
context:
- <missing repo fact or constraint>
allowed_files:
- <path>
steps:
1. <ordered instruction>
tests:
- <exact command>
stop_if:
- <condition>
```

Use this when the Advisor should take over:

```text
ADVISOR_TAKEOVER
task_id: <same id>
reason: <why executor should stop>
advisor_action: <review|fix|commit|rewrite plan|abandon>
executor_next_action: wait
```

## Handoff Format

```text
EXECUTOR_HANDOFF
task_id: <same id>
branch: <branch>
files_changed:
- <path>
tests_run:
- command: <exact command>
  result: <pass|fail|not_run>
  evidence: <short summary>
scope_check: <only allowed files changed|scope drift detected>
secrets_check: <no candidate secrets found|blocked>
unresolved_questions:
- <question or "none">
commit_recommendation: <commit|do_not_commit>
```

## Review Rules

Advisor must not trust the handoff by assertion. Before commit, Advisor runs:

```bash
git diff --name-only
git diff --check
.venv/bin/python -m tools.history.verify_integrity
.venv/bin/python -m tools.history.verify_routing
.venv/bin/python -m tools.history.verify_continuity
.venv/bin/python -m tools.streams.verify_streams
```

Advisor then runs the packet-specific tests. If DeepSeek touched files outside
the packet's allowed scope, Advisor rejects the handoff or trims the diff
manually with explicit operator approval.

## Improvement Loop

When Advisor catches a repeatable DeepSeek failure mode:

1. Add a new card to `docs/ledgers/agents/deepseek.md`.
2. Add the rule to the next DeepSeek prompt's hard constraints.
3. Cite the card in the review or correction packet.
4. Record the protocol update in `HISTORY.md` during closeout.

This is the teaching loop: DeepSeek's next cold-start prompt carries the new
rule, and Advisor keeps the executor from relearning the same mistake by trial
and error.

## When Not To Use This Loop

Do not use DeepSeek as executor for:

- tasks involving live secrets or credential rotation
- irreversible git operations
- license or legal policy changes
- broad architecture changes without an Advisor-authored plan
- final release tagging or publication claims

Use Advisor-only execution for those tasks.
