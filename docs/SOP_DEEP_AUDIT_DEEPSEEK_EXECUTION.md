# SOP — Deep Audit Remediation, DeepSeek Execution Pass

Issued: 2026-05-18 (post HISTORY#198)
Owner pattern: Claude authors and verifies; DeepSeek executes per-item fixes.
Supersedes scope: extends `docs/SOP_DEEP_AUDIT_REMEDIATION_BLUEPRINT.md` with
per-finding red-green specs. The blueprint guardrails still apply.

## How to use this SOP

For each item below DeepSeek must:

1. Read only the cited file ranges plus tests in `test_seam_all/test_seam.py`.
2. Write a failing test FIRST under the cited `tests/audit/` path (create the
   file if missing). Confirm it fails before any runtime edit.
3. Apply the smallest fix in the cited active file. Do not touch unrelated
   files. Do not edit `archive/`, `docs/archive/`, `build/`, `.venv/`,
   `test_seam/`, or `experimental/webui/`.
4. Re-run the failing test. Confirm green.
5. Run the full SEAM gate sequence (Section "Per-item gate" below).
6. Hand back to Claude with the exact commands used and their outputs.
   Do not commit. Claude reviews diff, runs secret scan, appends HISTORY entry,
   rebuilds index, writes snapshot, and gates.

If DeepSeek cannot reproduce a finding, STOP and hand back with the failing
repro command and its actual output. Do not skip-and-fix.

## Pre-flight (run once before starting)

```
git status --short
python -m pytest test_seam_all/test_seam.py -q
python -m tools.history.verify_integrity
python -m tools.history.verify_routing
python -m tools.history.verify_continuity
python -m tools.streams.verify_streams
```

All five must pass green before any edit. If pytest fails, STOP and hand back
to Claude with the failure — do not begin remediation on a broken baseline.

The working tree is currently dirty (16 modified, 1 deleted, 2 untracked from
HISTORY#198 follow-up). Confirm with Claude before staging that the existing
modifications are part of the intended remediation series.

## Per-item gate (after each fix)

```
python -m pytest test_seam_all/test_seam.py -q -k "<focused>"
python -m pytest test_seam_all/test_seam.py -q
python -m py_compile seam.py
python -m compileall -q seam_runtime experimental tools scripts installers
```

## Verification verdict on the auditor's claims

Read this before executing. Items adjusted from the auditor's wording.

| Auditor # | Status | Note |
|---|---|---|
| P0-1 auth disabled by default | CONFIRMED | `server.py:162,181` — `token = os.environ.get("SEAM_API_TOKEN")` is `None` by default; `if token:` skips auth |
| P0-2 PowerShell injection in installer | CONFIRMED, blast radius narrower than worded | `installer.py:317-323` — `updated` is f-string interpolated into single-quoted PowerShell. Injection requires attacker control of existing User PATH or install target argument; not a direct user-input vector, but still must be fixed |
| P0-3 non-atomic rollback in persist_ir | CONFIRMED | `runtime.py:84-99` — `delete_ir` then `persist_ir` are two separate transactions; vector failure mid-rollback loses data |
| P0-4 PgVector/ChromaDB orphaned on delete | PARTIALLY CONFIRMED | PgVector: real bug, no `delete_records`. **ChromaDB: no `ChromaSemanticAdapter` exists in `seam_runtime/`**; Chroma appears only as benchmark/comparator references. Treat as a PgVector-only fix |
| P0-5 append_event no locking | CONFIRMED | `tools/streams/streams_lib.py:228-247` — read-modify-write with no fcntl; `tools/history/new_entry.py:59-64` already uses fcntl.flock — copy that pattern |
| P0-6 cross-index delete-then-write | CONFIRMED | `tools/streams/rebuild_cross_index.py:71-82` — `unlink()` stale chunks, then `write_text()` new chunk and index. Not atomic |
| P1-7 rate limit by auth header | CONFIRMED | `server.py:97-101` — `_client_key` prefers authorization header over client.host |
| P1-8 MCP str(exc) leak | CONFIRMED | `mcp.py:188`, `mcp_protocol.py:88,133` (and `:60` parse-error path) all return `str(exc)` to the client |
| P1-9 search_ir loads whole scope | CONFIRMED | `runtime.py:101-105` — calls `load_ir(scope=scope)` without limit. HISTORY#198 added limit/offset to `load_ir`, but `search_ir` does not use it |
| P1-10 /context auto-persists pack | CONFIRMED | `runtime.py:140` — `pack_ir` unconditionally calls `self.store.persist_ir(IRBatch([pack_mirl]))` |
| P1-11 no FK REFERENCES | CONFIRMED | `storage.py:29-203` — `PRAGMA foreign_keys=ON` but every table is freestanding |
| P1-12 vector.py no pragmas | CONFIRMED | `vector.py:22-25` — `sqlite3.connect(self.path)` with no journal_mode / busy_timeout / foreign_keys |
| P1-13 destructive dedup on every init | CONFIRMED | `storage.py:193-195` — DELETE runs inside `_init_schema` on every constructor call |
| P1-14 SSRF via SEAM_EMBEDDING_BASE_URL | LOWER PRIORITY | Threat model requires attacker who already controls env var. Drop to P2 unless operator disagrees |
| P1-15 no token rotation | DESIGN, not bug | Document the operational procedure; do not invent SIGHUP behavior without operator sign-off |
| P1-16 no schema_version | CONFIRMED | Add table + version 1 stamp; do not write migration framework yet |
| P1-17 ~125 assertTrue | INFLATED | PROJECT_STATUS#198 records ~113 remaining. Audit count is slightly high. Keep as P3 per blueprint backlog |

Items not listed above (P2, P3, watch list) defer to the next cycle unless
operator promotes them.

---

## P0-1 — Mandatory auth or loopback-only warning

**Files**: `seam_runtime/server.py`
**Failing test**: `tests/audit/test_auth_default.py`

DeepSeek writes a test that calls `create_app()` with `SEAM_API_TOKEN` unset
and asserts one of:
- The factory raises `RuntimeError("SEAM_API_TOKEN required for non-loopback binds")` when invoked through `run_server(host="0.0.0.0")`, OR
- `create_app()` registers a warning logger record when tokenless and the
  app starts.

**Fix**: In `run_server` (`server.py:280`), after `_validate_server_safety`,
when `SEAM_API_TOKEN` is unset AND host is not loopback (`127.0.0.1`, `::1`,
`localhost`): refuse to start with `RuntimeError`. When tokenless on loopback:
emit a single `logging.warning(...)` line via the module logger. Do NOT
generate or persist a token; that requires operator policy decision.

**Out of scope**: rate limiter changes, CORS changes, schema changes.

**Verify command**: `python -m pytest test_seam_all/test_seam.py tests/audit/test_auth_default.py -q -k "auth_default"`

---

## P0-2 — PowerShell injection in installer

**Files**: `seam_runtime/installer.py:300-326`
**Failing test**: `tests/audit/test_installer_powershell.py`

Test crafts an `existing_user_path` that contains a single quote and asserts
the resulting `subprocess.run` argv places the PATH value as a parameter to
a parameterised PowerShell scriptblock, not as part of the command string.

**Fix**: Replace the f-string command with a parameterised script:

```python
subprocess.run(
    [
        "powershell",
        "-NoProfile",
        "-Command",
        "param($value) [Environment]::SetEnvironmentVariable('Path', $value, 'User')",
        "-value",
        updated,
    ],
    check=True,
)
```

Or equivalent: pass `updated` through `-Args` / read it from `stdin`. The
constraint is that `updated` MUST NOT be substituted into the PowerShell
script text.

**Out of scope**: changing `_ensure_posix_shell_profiles`, restructuring the
installer, or adding new PATH validators.

---

## P0-3 — Atomic rollback in persist_ir

**Files**: `seam_runtime/runtime.py:84-99`, possibly a new
`SQLiteStore.replace_ir(previous, normalized)` in `seam_runtime/storage.py`
**Failing test**: `tests/audit/test_persist_rollback.py`

Test injects a `VectorAdapter` whose `index_records` raises after the SQLite
write but also makes `SQLiteStore.persist_ir` (via monkeypatch) fail on the
second call. Assert: after the failure, `load_ir(ids=touched_ids)` returns
the pre-existing `previous` records intact, never an empty result.

**Fix**: Add `SQLiteStore.replace_ir(previous_batch, new_batch)` that opens a
single connection, runs DELETE for touched ids, then INSERT for previous
records, all inside one explicit `BEGIN ... COMMIT`. Call this from
`runtime.persist_ir` rollback path.

Pre-existing `previous` may be empty (first-time write). In that case the
rollback is a pure delete; still wrap in one transaction.

**Out of scope**: changing `delete_ir` signature, adding row-versioning,
introducing a savepoint scheme across the whole runtime.

---

## P0-4 — PgVector delete on record deletion

**Files**: `seam_runtime/vector_adapters.py` (add `delete_records`),
`seam_runtime/storage.py:419-434` (call adapter when configured),
`seam_runtime/runtime.py` (wire adapter into `delete_ir` callers)
**Failing test**: `tests/audit/test_pgvector_delete.py`

Test uses a stub `PgVectorAdapter` that records `delete_records` calls.
Persist a batch, then call `runtime.delete_ir([...])` (this method does not
exist yet on `SeamRuntime` — add a thin wrapper) and assert the adapter saw
the ids.

**Fix**:
1. Add `PgVectorAdapter.delete_records(self, ids: list[str]) -> None` that
   runs `delete from {table} where record_id = any(%s) and model_name = %s`.
2. Add `SQLiteVectorAdapter.delete_records` for parity (delegates to
   `SQLiteVectorIndex.delete_records`, which you also add).
3. Add `SeamRuntime.delete_ir(self, ids: list[str]) -> None` that calls
   `self.store.delete_ir(ids, include_vectors=True)` then
   `self.vector_adapter.delete_records(ids)`.

**Out of scope**: ChromaDB adapter (does not exist in runtime — see verdict
table). `document_status` / `machine_artifacts` cleanup (P2 item).

---

## P0-5 — File-locked append_event

**Files**: `tools/streams/streams_lib.py:228-247`
**Failing test**: `tools/streams/test_streams.py` (extend existing module)

Test forks/threads two concurrent `append_event` calls against a tmp stream
directory and asserts both events appear with distinct sequential ids in the
final log, with no body interleaving.

**Fix**: Wrap the read-modify-write in `fcntl.flock` (LOCK_EX) on a sibling
`<kind>/log.lock` file. Mirror the pattern in `tools/history/new_entry.py:59-64`.
Windows fallback: use `msvcrt.locking` if `fcntl` import fails (same dual-OS
pattern used elsewhere in the history writer).

**Out of scope**: changing log file format, changing `parse_events`, adding
distributed locking.

---

## P0-6 — Atomic cross-index rebuild

**Files**: `tools/streams/rebuild_cross_index.py:65-100+`, plus
`tools/streams/rebuild_index.py` (same pattern)
**Failing test**: `tools/streams/test_streams.py` (extend)

Test monkeypatches `Path.write_text` to raise after the unlink loop but
before the new chunk is written, then asserts the prior archive chunks
still exist (or were never removed) and the index file is unchanged.

**Fix**:
1. Write new archive chunks to `*.cross.md.tmp` first.
2. Write the new index body to `cross_index.md.tmp`.
3. After all writes succeed: `os.replace(tmp, target)` for each, then unlink
   any stale `*.cross.md` files that are not in the new chunk set.

**Out of scope**: changing the archive chunk schema, changing event ordering,
changing total_events counting.

---

## P1-7 — Rate limit by client IP, not auth header

**Files**: `seam_runtime/server.py:97-101`
**Failing test**: `tests/audit/test_rate_limit_key.py`

Test issues N requests with rotating `Authorization` headers from the same
client IP and asserts the rate limiter throttles after the configured
threshold.

**Fix**: `_client_key` returns the client host first, falling back to a fixed
string "local" only when no client info is present. Drop the authorization
fallback entirely. Add a comment that X-Forwarded-For is intentionally NOT
honoured here — trusted proxy support is a separate item.

**Out of scope**: trusted proxy / X-Forwarded-For, multi-worker rate limiter
coordination (separate REPO_LEDGER policy item).

---

## P1-8 — Generic error responses in MCP

**Files**: `seam_runtime/mcp.py:188`, `seam_runtime/mcp_protocol.py:60,88,133`
**Failing test**: `tests/audit/test_mcp_error_redaction.py`

Test makes the runtime raise an exception whose `str()` contains
`"postgres://user:pw@host"` (a DSN containing a credential). Assert the response body does NOT contain
the credential and DOES contain a stable generic message like `"Internal error"`.

**Fix**: Replace each `str(exc)` in the cited locations with `"Internal error"`
(or the existing `JSONRPC_INTERNAL_ERROR` message at that callsite). Log the
full traceback through `logging.getLogger(__name__).exception(...)` so
operators still get the detail server-side.

Keep `mcp_protocol.py:60` (parse-error path) returning the exception message
ONLY if the message is constructed by our own code; if it's from json parser,
substitute "Parse error: invalid JSON".

**Out of scope**: changing JSON-RPC error codes, modifying tool result
schemas, adding new MCP tools.

---

## P1-9 — Vector-first search with bounded loads

**Files**: `seam_runtime/runtime.py:101-105`, `seam_runtime/storage.py`
**Failing test**: `tests/audit/test_search_bounded.py`

Test persists 1000 records, calls `search_ir(query, budget=5)`, and asserts
the SQLite query count (via `sqlite3.Connection.set_trace_callback`) is
bounded relative to budget — specifically that `load_ir` is called with an
`ids` list of length <= `max(budget * 3, 10)`, NOT a scope-wide load.

**Fix**: In `search_ir`:
1. Call vector adapter `search(query, limit=max(budget * 3, 10))` first.
2. Take the resulting record_ids.
3. Call `self.store.load_ir(ids=record_ids)` (this is the bounded path).
4. Pass that batch into `search_batch`.

When vector_scores are empty (no embeddings yet, e.g. for a brand-new DB):
fall back to `load_ir(scope=scope, limit=max(budget * 4, 50))` — bounded,
not unbounded. Add a comment.

**Out of scope**: changing `search_batch` signature, replacing the embedding
model, adding hybrid retrieval modes.

---

## P1-10 — Opt-in /context pack persistence

**Files**: `seam_runtime/runtime.py:131-141` (`pack_ir`), `seam_runtime/server.py:233-252` (`context` endpoint)
**Failing test**: `tests/audit/test_context_no_persist.py`

Test calls `/context` and asserts no new row appears in `pack_store` unless
the request payload contains `"persist": true`.

**Fix**: Add `persist: bool = False` parameter to `SeamRuntime.pack_ir`.
Only call `self.store.persist_ir([pack_mirl])` when `persist=True`. The
server `context` endpoint reads `payload.get("persist", False)` and passes
it through.

The `seam pack --mode exact` CLI path that depends on persisting must
continue to pass `persist=True`. Audit all callers of `pack_ir` before
flipping the default.

**Out of scope**: pack GC, retention policies, pack_store schema changes.

---

## P1-11 — Foreign key REFERENCES clauses

**Files**: `seam_runtime/storage.py:29-205`, plus a new
`tools/storage/migrate_v1_to_v2.py`
**Failing test**: `tests/audit/test_storage_fk.py`

Test creates a store, INSERTs an `ir_edges` row referencing a non-existent
record id, and asserts SQLite raises `IntegrityError`.

**Fix**:
1. Add a `schema_version` table (covers P1-16 as well). Stamp current
   databases as version 1.
2. Bump schema to version 2 with REFERENCES on:
   - `raw_spans.raw_id` → `raw_docs(id) ON DELETE CASCADE`
   - `ir_edges.src_id` → `ir_records(id) ON DELETE CASCADE`
   - `ir_edges.dst_id` → `ir_records(id) ON DELETE CASCADE`
   - `vector_index.record_id` → `ir_records(id) ON DELETE CASCADE`
   - `projection_index.record_id` → `ir_records(id) ON DELETE CASCADE`
3. Migration: copy data through new tables, swap, drop old. Do this only when
   `schema_version` reads 1. Skip on `:memory:` databases (test fixtures
   start fresh at v2).

This is the largest item in the SOP. **DeepSeek must STOP at the failing
test and hand back to Claude before writing the migration.** Claude will
review the migration plan before DeepSeek executes.

**Out of scope**: adding REFERENCES to `machine_artifacts`, `surface_artifacts`,
`benchmark_*`, `document_status` — those tables track artifacts whose source
records may be deleted intentionally; treat as P2.

---

## P1-12 — Pragmas in vector.py

**Files**: `seam_runtime/vector.py:22-25`
**Failing test**: `tests/audit/test_vector_pragmas.py`

Test opens a `SQLiteVectorIndex._connect()` and asserts `pragma journal_mode`
returns `wal` and `pragma busy_timeout` returns a non-zero value.

**Fix**: Mirror `storage.py:20-27` exactly. After `sqlite3.connect`, run
`pragma journal_mode=WAL` (skip on `:memory:`), `pragma busy_timeout=5000`,
`pragma foreign_keys=ON`. Add `pragma synchronous=NORMAL`.

**Out of scope**: vector index schema changes, embedding model changes.

---

## P1-13 — Move dedup out of _init_schema

**Files**: `seam_runtime/storage.py:193-197`
**Failing test**: `tests/audit/test_init_no_mutation.py`

Test seeds an `ir_edges` row, opens a new `SQLiteStore` against the same
path, then asserts the row count is unchanged.

**Fix**:
1. Remove the `DELETE FROM ir_edges WHERE id NOT IN (...)` statement from
   `_init_schema`.
2. The `create unique index if not exists idx_ir_edges_unique` will fail
   on databases that still have duplicates. Resolve this through a one-time
   `SQLiteStore.dedupe_edges()` method (idempotent) that operators call
   explicitly, OR gate the dedup behind `schema_version` reading <2 (combined
   with the P1-11 migration).

Prefer the schema_version gate — it lets the dedup run once during the v1→v2
migration and never again.

**Out of scope**: changing edge model, changing edge constraints beyond the
existing unique index.

---

## P1-16 — Schema version table

Covered as part of P1-11. Do NOT do this as a standalone item; it gives
nothing without the migration framework that P1-11 introduces.

---

## Claude-side review checklist (per item)

After DeepSeek hands back, Claude must:

1. `git diff --stat` — confirm only the cited files were touched.
2. `git diff -- <file>` — sanity check the diff matches the spec above.
3. Secret/session-link scan:
   ```
   git diff -- . ':!docs/archive' ':!archive/code' \
     | rg -n "sk-[A-Za-z0-9_-]+|ghp_[A-Za-z0-9_]+|BEGIN (RSA |OPENSSH |EC |)PRIVATE KEY|session|share\.openai|chatgpt\.com/share|claude\.ai/share|gemini\.google\.com/share" || true
   ```
4. Run the full SEAM gate sequence:
   ```
   python -m pytest test_seam_all/test_seam.py -q
   python -m py_compile seam.py
   python -m compileall -q seam_runtime experimental tools scripts installers
   python -m tools.history.verify_integrity
   python -m tools.history.verify_routing
   python -m tools.history.verify_continuity
   python -m tools.streams.verify_streams
   ```
5. Append one HISTORY entry per item completed (or one entry per merged
   batch, if Claude judges items are coupled).
6. Rebuild index, write snapshot, run gates again.
7. Stage and commit only when all gates pass. Use the canonical pre-commit
   hook; do NOT bypass with `--no-verify`.

## Order of execution

Recommended sequence (minimises rework):

1. P1-12 (vector pragmas) — tiny, isolated, unblocks concurrency tests
2. P0-5 (append_event lock) — tiny, isolated, unblocks multi-agent tests
3. P0-6 (atomic cross-index) — isolated to stream tooling
4. P1-7 (rate limit key) — single file, single function
5. P1-8 (MCP error redaction) — touches 3 lines across 2 files
6. P0-2 (PowerShell argv) — single function
7. P1-10 (opt-in /context persist) — small surface, needs caller audit
8. P0-1 (auth on non-loopback) — adds startup validator
9. P0-3 (atomic rollback) — adds `replace_ir`; medium scope
10. P0-4 (PgVector delete) — medium scope, three files
11. P1-9 (vector-first search) — medium scope, depends on adapter parity from P0-4
12. P1-11 + P1-13 + P1-16 (FK migration) — biggest item, last; needs Claude review of migration plan before execution

Do not batch unrelated items into one HISTORY entry. The temporal chain is
load-bearing for this project — keep entries scoped.

## Stop conditions

DeepSeek must STOP and hand back to Claude if:

- A failing test passes before the fix is applied (the bug is not what the
  audit described — escalate for re-verification).
- The full pytest suite has a regression unrelated to the fix.
- Any SEAM gate fails (`verify_integrity`, `verify_routing`,
  `verify_continuity`, `verify_streams`).
- A diff hunk touches a file not listed in this SOP.
- Any committed text contains a secret pattern, session URL, share URL,
  bearer token, or `.env` value.

End of SOP.
