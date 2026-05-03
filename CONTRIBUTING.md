# Contributing to SEAM

Thank you for considering a contribution to SEAM.

SEAM is source-available proprietary software, not open-source software unless a specific file explicitly says otherwise. Contributions are welcome for review, evaluation, documentation, testing, and project improvement, but all contributions must preserve the boundaries described in `LICENSE`, `NOTICE`, and `COMMERCIAL_LICENSE.md`.

## Read first

Before contributing, read:

1. `AGENTS.md` for the canonical repo protocol.
2. `PROJECT_STATUS.md` for current operating state.
3. `REPO_LEDGER.md` for stable repo decisions.
4. `docs/CODE_LAYOUT.md` for active vs archived paths.
5. `LICENSE`, `NOTICE`, and `COMMERCIAL_LICENSE.md` for permitted use.

Normal development should stay in active paths: `seam_runtime/`, `seam.py`, `experimental/`, `tools/`, `scripts/`, `installers/`, `docs/`, tests, and root status or policy files.

Do not copy stale code or prose from archived paths back into active paths without rewriting, verifying, and recording the reason.

## Contribution grant

By submitting a pull request, issue text, code, documentation, test, benchmark, design, or other contribution to SEAM, you agree that your contribution is governed by the contribution terms in `LICENSE`.

In plain language, you keep copyright you own in your contribution, but you grant the project owner broad rights to use, modify, distribute, sublicense, relicense, and commercially license that contribution as part of SEAM or related SEAM offerings.

Do not submit anything you do not have the right to contribute.

## Pull request expectations

A good PR should:

- explain what changed and why;
- keep active and archived paths separated;
- update `REPO_LEDGER.md` when changing stable repo policy, architecture, routing, runtime safety rules, durable workflows, or cross-agent protocol;
- update `PROJECT_STATUS.md` when changing current operating state or active focus;
- append one `HISTORY.md` entry for material changes;
- rebuild derived history, index, and snapshot artifacts when local tooling is available;
- run relevant tests or clearly state what was skipped and why; and
- avoid duplicating long continuity prose across multiple docs.

## Commercial-use boundary

Contributions do not grant commercial-use rights to contributors or third parties. Commercial, hosted, SaaS, API, managed-service, embedded, redistribution, resale, customer-deployment, or closed-source use still requires a separate written commercial license from the project owner.
