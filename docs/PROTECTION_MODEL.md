# SEAM Protection Model

This document explains how SEAM can remain useful for public review and non-commercial local evaluation while keeping commercial-only implementation details under separate access control.

`LICENSE`, `NOTICE`, and `COMMERCIAL_LICENSE.md` remain the controlling licensing boundary. This document is an operating model for repo structure and agent workflow.

## Goals

SEAM should:

- remain installable and usable for permitted local evaluation;
- keep the existing CLI, dashboard, REST, MCP, benchmark, and history workflows intact;
- preserve the repo bookkeeping protocol in `AGENTS.md`, `PROJECT_STATUS.md`, `REPO_LEDGER.md`, `HISTORY.md`, `HISTORY_INDEX.md`, and `docs/CODE_LAYOUT.md`;
- avoid adding startup context bloat for future agents;
- make commercial-use boundaries obvious to readers and contributors; and
- keep advanced commercial modules, private benchmark holdouts, enterprise connectors, hosted-service code, and unreleased methods outside the public source tree unless intentionally released.

## Public repository boundary

The public repository is the evaluation and contribution surface. It may include:

- the installable local runtime;
- CLI and operator workflows;
- public documentation;
- public regression tests and benchmark harnesses;
- public adapters and examples;
- public protocol docs; and
- policy files that explain licensing, contribution, security, and commercial-use boundaries.

Public visibility does not grant commercial, hosted, SaaS, embedded, redistribution, resale, customer-deployment, or closed-source product rights.

## Private/commercial boundary

Private or commercial repositories may hold:

- private benchmark holdouts;
- advanced compression or retrieval experiments before release;
- enterprise-only connectors;
- hosted-service deployment code;
- customer-specific integrations;
- confidential pitch material;
- unreleased architecture notes; and
- any implementation detail that should remain a trade secret or commercial-only module.

Moving future work into a private repository only protects future non-public code. It does not erase public access to code that has already been published.

## Agent workflow rule

Do not add this document to the mandatory startup read list unless the task specifically touches licensing, commercial boundaries, contribution policy, repo protection, or public/private separation.

For normal development, agents should continue using the existing startup flow:

1. `PROJECT_STATUS.md`
2. `REPO_LEDGER.md`
3. `HISTORY_INDEX.md`
4. `docs/CODE_LAYOUT.md`
5. targeted `HISTORY.md` entries only when needed

This keeps protection policy visible without forcing future agents to load long legal or policy files during normal runtime work.

## Runtime safety rule

Protection changes must not silently change runtime behavior. A protection-only change should avoid touching:

- `seam_runtime/`
- `seam.py`
- `pyproject.toml`
- installer behavior
- dashboard behavior
- API behavior
- benchmark execution behavior
- history tooling behavior
- active test semantics

If a future protection change needs to alter runtime behavior, it must be handled as an implementation change with tests, history entry, index rebuild, and continuity verification.

## Bookkeeping rule

Protection changes are stable repo policy changes. They should:

- update `REPO_LEDGER.md` with a compact pointer;
- append one `HISTORY.md` entry;
- rebuild `HISTORY_INDEX.md` when local tooling is available;
- write a snapshot when local tooling is available; and
- state skipped verification honestly when changes are made through a connector that cannot run local repo tooling.
