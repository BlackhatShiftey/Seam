# SEAM Trust, Security, Lineage, and Auditability Roadmap

**Status:** Planned major track. Concept harvested from `roadmap-trust-security-manual` branch.
**Track:** K — Trust, Security, Lineage, and Data-Engineer Credibility.

Note: the source branch proposed this as "Track F". The root roadmap already uses Track F for "Docs, Setup Guides, and Error Playbooks", so this track is filed under the next available letter (K) to avoid renumbering existing tracks.

## Purpose

SEAM's runtime, CLI, contracts, audit ledger, validation reports, provenance, and benchmark bundles must produce trust evidence on demand. The dashboard is a visualization layer for that evidence; it is not the source of trust.

Track K supplies the primitives. Other tracks consume them:

- Track I (external memory benchmarks) consumes Benchmark Integrity Levels.
- Track H (Agent / Skills Compiler) consumes audit log and capability checks in its later phases.
- The dashboard consumes the unified trust report.

## Items

### F0 — Threat model and trust boundaries

Add `docs/security/THREAT_MODEL.md`. Define boundaries for CLI, REST, WebUI, SQLite, holographic surfaces, agent tools, model calls, imports, exports, backups, and snapshots. Gate completion on every protected operation mapping to a documented trust boundary.

### F1 — Capability and permission model

Require sensitive operations to declare a capability before exposure through CLI, REST, WebUI, MCP, or agent tools.

Initial capability set: `read_memory`, `write_memory`, `delete_memory`, `export_memory`, `read_surface`, `write_surface`, `repair_surface`, `run_benchmark`, `seal_benchmark`, `verify_benchmark`, `read_files`, `write_files`, `network_access`, `model_call`, `shell_exec`, `secrets_read`, `admin_config`.

Gate: unscoped sensitive operations fail closed.

### F2 — Tamper-evident audit ledger

Hash-chained, append-only ledger for write, delete, export, import, benchmark, config, redaction, agent-tool, and protected REST operations.

```bash
seam audit log
seam audit verify
seam audit export
seam audit explain <event_id>
```

Minimum event fields: event id, previous hash, event hash, actor, capability, target, decision, timestamp, trace id, reason.

Gate: `seam audit verify` detects altered or missing events.

### F3 — Secrets scanning and redaction

Runtime checks so sensitive values are not ingested, packed, exported, benchmarked, logged, or rendered in dashboard state.

```bash
seam secrets scan
seam redact preview
seam redact apply
seam export --redact
```

Companion docs: `docs/security/SECRETS.md`, `docs/security/REDACTION_MODEL.md`. Gate: trust tests prove redaction across ingest, pack, export, benchmark, logs, and dashboard.

### F4 — Optional encrypted SQLite store

Optional encryption-at-rest while SQLite remains canonical.

```bash
seam init --encrypted
seam db encrypt
seam db rekey
seam db verify-encryption
```

Gate: encrypted backup and restore preserve hashes and audit continuity.

### F5 — Versioned contracts

Publish contracts for canonical records, packs, provenance, surfaces, and audit events:

- `docs/contracts/MIRL_RECORD_CONTRACT.md`
- `docs/contracts/PACK_CONTRACT.md`
- `docs/contracts/PROVENANCE_CONTRACT.md`
- `docs/contracts/SURFACE_CONTRACT.md`
- `docs/contracts/AUDIT_EVENT_CONTRACT.md`

Gate: contract checks are included in the unified trust report.

### F6 — Unified trust report

One command proves SEAM's trust state.

```bash
seam trust report --security --json
```

Report includes: SQLite canonical status, lossless roundtrip, surface verification, audit-chain verification, redaction policy, capability policy, REST protection, agent-tool capability checks, benchmark-bundle verification, SBOM, release attestation, overall security gate.

Gate: the dashboard consumes this runtime report; it does not duplicate trust logic.

### F7 — Operation validation reports

Major operations emit machine-readable reports.

```bash
seam compile input.md --report compile.report.json
seam search "query" --report retrieve.report.json
seam context "query" --report pack.report.json
seam surface verify file.seam.png --report surface.report.json
```

Reports include contract status, provenance completeness, candidate counts, hashes, trace ids, audit event ids.

### F8 — OpenLineage export

Standard lineage export for data-engineering workflows.

```bash
seam lineage export --format openlineage
```

Includes SEAM facets for provenance, redaction, permissions, audit, surface hash, contracts, benchmark integrity.

### F9 — OpenTelemetry correlation

Trace ids across compile, persist, surface, search, context, pack, benchmark, export, delete, restore, agent tool, and REST flows. Telemetry stays separate from the audit ledger; both correlate via `trace_id`.

### F10 — Supply-chain proof

Machine-verifiable release evidence.

```bash
seam sbom generate
seam release attest
seam release verify
```

Gate: release claims require SBOM availability, signed artifacts, and release provenance.

### F11 — Security test suite and trust corpus

A security/trust test family covering malformed input, corrupted artifacts, permission checks, redaction checks, benchmark verification, audit verification, import/export, and protected API behavior.

```bash
seam security test
seam security gate
```

Gate: no silent corruption; no unscoped sensitive operation.

### F12 — Incident response and vulnerability disclosure

Add `SECURITY.md`, `docs/security/INCIDENT_RESPONSE.md`, `docs/security/VULNERABILITY_DISCLOSURE.md`. Define reporting, triage, patching, release, disclosure, and operator recovery steps.

### F13 — Verified benchmark bundles (Benchmark Integrity Levels)

Make benchmark bundles tamper-evident, signed, audit-linked, reproducible where possible, and independently verifiable.

```bash
seam bench run --seal
seam bench verify benchmark.seam-bundle
seam bench verify --rerun benchmark.seam-bundle
seam bench diff old.seam-bundle new.seam-bundle
seam bench attest benchmark.seam-bundle
seam bench inspect benchmark.seam-bundle
seam bench publish-transparency benchmark.seam-bundle
```

**Benchmark Integrity Levels:**

| Level | Meaning |
|-------|---------|
| BIL-0 | Raw score only |
| BIL-1 | Result hash |
| BIL-2 | Result plus input manifest |
| BIL-3 | Signed benchmark bundle |
| BIL-4 | Signed bundle plus audit hash chain |
| BIL-5 | Signed bundle plus audit chain plus external transparency log |
| BIL-6 | BIL-5 plus independent reproducible rerun |

Gate: dashboard benchmark claims show integrity level, signer, input hashes, audit linkage, reproducibility status, and verification result. Track I (external memory benchmarks) seals its bundles at the highest BIL level available.

## Dashboard reframe

The dashboard is the SEAM auditability visualization layer. It visualizes trust report status, capability registry status, audit verification, REST endpoint protection, agent-tool capability checks, redaction warnings, provenance, lineage, surface-hash verification, BIL levels, benchmark-bundle verification, export/delete/import history, validation reports, and security-gate status. It does not generate trust evidence itself.

## Definition of done

Track K is complete when `seam trust report --security --json` passes on a clean local install, sensitive operations are capability-scoped, audit logs are hash-chain verified, benchmark bundles can be sealed and verified, redaction protections cover runtime and dashboard surfaces, and every new command is documented in the operator manual.
