# SEAM Trust, Security, and Auditability Roadmap Addendum

**Status:** Proposed roadmap addendum
**Created:** 2026-05-09
**Intended target:** Fold into `ROADMAP.md` before the browser dashboard is declared complete.

## Purpose

This addendum records the roadmap shift for SEAM. The REST API should remain wired and usable, and the WebUI should remain functional, but the dashboard should be framed as a visualization layer for auditability, security posture, trust status, and capability state.

The dashboard is not the source of trust. The runtime, CLI, contracts, audit ledger, validation reports, provenance, and benchmark bundles produce trust evidence. The dashboard visualizes that evidence.

## Roadmap Reconciliation

When the root roadmap is reconciled, this addendum should become **Track F — Trust, Security, Lineage, and Data-Engineer Credibility**. The current documentation-focused Track F should move to **Track G — SEAM Manual, Wiki, SOPs, and Error Playbooks**.

The WebUI can stay API-wired and usable, but dashboard completion should depend on the Track F substrate. The dashboard should not be considered complete until it can display audit status, capability decisions, benchmark integrity, redaction warnings, provenance, lineage, validation reports, and trust-report results.

## Track F — Trust, Security, Lineage, and Data-Engineer Credibility

### F0: Threat Model and Trust Boundaries

Add `docs/security/THREAT_MODEL.md`. Define the boundaries for CLI, REST, WebUI, SQLite, holographic surfaces, agent tools, model calls, imports, exports, backups, and snapshots. Gate completion on every protected operation mapping to a documented trust boundary.

### F1: Capability and Permission Model

Require sensitive operations to declare capabilities before exposure through CLI, REST, WebUI, MCP, or agent tools.

Initial capabilities include `read_memory`, `write_memory`, `delete_memory`, `export_memory`, `read_surface`, `write_surface`, `repair_surface`, `run_benchmark`, `seal_benchmark`, `verify_benchmark`, `read_files`, `write_files`, `network_access`, `model_call`, `shell_exec`, `secrets_read`, and `admin_config`.

Gate completion on unscoped sensitive operations failing closed.

### F2: Tamper-Evident Audit Ledger

Add a hash-chained, append-only audit ledger for write, delete, export, import, benchmark, config, redaction, agent tool, and protected REST operations.

Planned commands:

```bash
seam audit log
seam audit verify
seam audit export
seam audit explain <event_id>
```

Minimum event fields should include event ID, previous hash, event hash, actor, capability, target, decision, timestamp, trace ID, and reason.

Gate completion on `seam audit verify` detecting altered or missing audit events.

### F3: Secrets Scanning and Redaction

Add documentation and runtime checks so sensitive values are not accidentally ingested, packed, exported, benchmarked, logged, or rendered in dashboard state.

Planned commands:

```bash
seam secrets scan
seam redact preview
seam redact apply
seam export --redact
```

Add `docs/security/SECRETS.md` and `docs/security/REDACTION_MODEL.md`. Gate completion on trust tests proving redaction protections across ingest, pack, export, benchmark, logs, and dashboard views.

### F4: Optional Encrypted SQLite Store

Prepare optional encryption-at-rest support while keeping SQLite canonical.

Planned commands:

```bash
seam init --encrypted
seam db encrypt
seam db rekey
seam db verify-encryption
```

Gate completion on encrypted backup and restore preserving hashes and audit continuity.

### F5: Versioned Contracts

Publish contracts for canonical records, context packs, provenance, surfaces, and audit events.

Target docs:

```text
docs/contracts/MIRL_RECORD_CONTRACT.md
docs/contracts/PACK_CONTRACT.md
docs/contracts/PROVENANCE_CONTRACT.md
docs/contracts/SURFACE_CONTRACT.md
docs/contracts/AUDIT_EVENT_CONTRACT.md
```

Gate completion on contract checks being included in the unified trust report.

### F6: Unified Trust Report

Add one command that proves SEAM's trust state.

Planned command:

```bash
seam trust report --security --json
```

The report should include SQLite canonical status, lossless roundtrip status, surface verification status, audit-chain verification status, redaction policy status, capability policy status, REST protection status, agent-tool capability status, benchmark-bundle verification status, SBOM status, release-attestation status, and overall security gate status.

Gate completion on the dashboard consuming the same runtime report instead of duplicating trust logic.

### F7: Operation Validation Reports

Allow major operations to emit machine-readable validation reports.

Example patterns:

```bash
seam compile input.md --report compile.report.json
seam search "query" --report retrieve.report.json
seam context "query" --report pack.report.json
seam surface verify file.seam.png --report surface.report.json
```

Reports should include contract status, provenance completeness, candidate counts, hashes, trace IDs, and audit event IDs.

### F8: OpenLineage Export

Add standard lineage export for data-engineering workflows.

Planned command:

```bash
seam lineage export --format openlineage
```

Include SEAM facets for provenance, redaction, permissions, audit, surface hash, contracts, and benchmark integrity.

### F9: OpenTelemetry Correlation

Add trace IDs across compile, persist, surface, search, context, pack, benchmark, export, delete, restore, agent tool, and REST flows. Keep telemetry separate from the audit ledger, but correlate both using `trace_id`.

### F10: Supply-Chain Proof

Publish machine-verifiable release evidence.

Planned commands:

```bash
seam sbom generate
seam release attest
seam release verify
```

Gate release claims on SBOM availability, signed artifacts, and release provenance.

### F11: Security Test Suite and Trust Corpus

Add a security and trust test family covering malformed input, corrupted artifacts, permission checks, redaction checks, benchmark verification, audit verification, import/export behavior, and protected API behavior.

Planned commands:

```bash
seam security test
seam security gate
```

Gate completion on no silent corruption and no unscoped sensitive operation.

### F12: Incident Response and Vulnerability Disclosure

Add `SECURITY.md`, `docs/security/INCIDENT_RESPONSE.md`, and `docs/security/VULNERABILITY_DISCLOSURE.md`. Define reporting, triage, patching, release, disclosure, and operator recovery steps.

### F13: Verified Benchmark Bundles

Make benchmarks tamper-evident, signed, audit-linked, reproducible where possible, and independently verifiable.

Planned commands:

```bash
seam bench run --seal
seam bench verify benchmark.seam-bundle
seam bench verify --rerun benchmark.seam-bundle
seam bench diff old.seam-bundle new.seam-bundle
seam bench attest benchmark.seam-bundle
seam bench inspect benchmark.seam-bundle
seam bench publish-transparency benchmark.seam-bundle
```

Benchmark Integrity Levels:

```text
BIL-0: Raw score only
BIL-1: Result hash
BIL-2: Result plus input manifest
BIL-3: Signed benchmark bundle
BIL-4: Signed bundle plus audit hash chain
BIL-5: Signed bundle plus audit chain plus external transparency log
BIL-6: BIL-5 plus independent reproducible rerun
```

Gate completion on dashboard benchmark claims showing integrity level, signer, input hashes, audit linkage, reproducibility status, and verification result.

## Dashboard Reframe

The dashboard should be described as the SEAM auditability visualization layer.

It should visualize trust report status, capability registry status, audit verification, REST endpoint protection, agent tool capability checks, redaction warnings, provenance, lineage, surface hash verification, benchmark integrity levels, benchmark-bundle verification, export/delete/import history, validation reports, and security gate status.

## Definition of Done

Track F is not done until `seam trust report --security --json` passes on a clean local install, sensitive operations are capability-scoped, audit logs are hash-chain verified, benchmark bundles can be sealed and verified, redaction protections cover runtime and dashboard surfaces, and every new command is documented in the SEAM Manual.
