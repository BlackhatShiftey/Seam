# SOP — WebUI Batch Hardening + Quick-Wins, DeepSeek Execution Pass

Issued: 2026-05-19 (post HISTORY#207)
Owner pattern: Claude authors and verifies; DeepSeek executes all items in
sequence in a single session; Claude reviews the full diff at handback,
appends HISTORY entries, commits per item.

Scope: hardens the four uncommitted WebUI-wiring endpoints (`/tree`,
`/benchmark`, `/sys-metrics`, `record_kinds` stats contract) plus three
small audit quick-wins (`write_log` fsync, `.cursor/` gitignore,
`TestCountFact` pytest-collection warning).

Supersedes scope: extends `docs/SOP_DEEP_AUDIT_REMEDIATION_BLUEPRINT.md`
with per-item red-green specs. The blueprint guardrails still apply.

## How to use this SOP

For each item below DeepSeek must:

1. Read only the cited file ranges plus `test_seam_all/test_seam.py` plus
   `tests/audit/__init__.py`.
2. Write a failing test FIRST under the cited `tests/audit/` path (create the
   file if missing). Confirm the test fails before any runtime edit.
3. Apply the smallest fix in the cited active file(s). Do not touch
   unrelated files. Do not edit `archive/`, `docs/archive/`, `build/`,
   `.venv/`, `test_seam/`, or `experimental/webui/`.
4. Re-run the failing test. Confirm green.
5. Run the per-item gate (Section "Per-item gate" below).
6. Move to the next item. Do NOT commit. Do NOT push.

After ALL items complete: emit one ITEM_SUCCESS block per item, in
execution order, in one final paste. Then STOP. Claude reviews the full
diff and commits per item.

If a stop condition fires for any item (claim_could_not_reproduce,
regression, scope_limit_hit, secret_found, missing_file), STOP at that
item — do not attempt the remaining items. Emit the appropriate report
block for the stopped item plus ITEM_SUCCESS blocks for any items that
completed before it.

## Pre-flight (run once before starting)

```
git status --short                                  # expect exactly 4 dirty files
git branch --show-current                           # expect main
python -m pytest test_seam_all/test_seam.py -q
python -m tools.history.verify_integrity
python -m tools.history.verify_routing
python -m tools.history.verify_continuity
python -m tools.streams.verify_streams
```

Expected starting state at the time this SOP was written:
- Branch: `main`
- Dirty files: `experimental/webui/public/dashboard.html`,
  `experimental/webui/public/seam-api.js`, `seam_runtime/server.py`,
  `seam_runtime/storage.py`. Do NOT revert these — they are the in-flight
  WebUI wiring batch this SOP hardens.
- pytest test_seam_all: 180 passed (full project: 359 passed)
- All four gates: OK

If pytest fails or any gate is red, STOP and emit MISSING_FILE or
CLAIM_COULD_NOT_REPRODUCE — do not begin remediation on a broken baseline.

## Per-item gate (after each fix, before moving on)

```
python -m pytest tests/audit/<focused_test_file> -q
python -m pytest test_seam_all/test_seam.py -q
python -m py_compile seam.py
python -m compileall -q seam_runtime experimental tools scripts installers
```

The full SEAM verify chain (`verify_integrity`, `verify_continuity`,
`verify_routing`, `verify_streams`) is Claude's responsibility at handback;
DeepSeek does not need to rerun them unless an item edits `tools/streams/`
or `tools/history/` (item H1 does — rerun `verify_streams` after).

## Order of execution

1. **W1** — `/tree` endpoint safety (path traversal + DoS)
2. **W2** — `/benchmark` endpoint policy + suite validation
3. **W3** — `/sys-metrics` honest errors + platform check
4. **W4** — `record_kinds` symbol-keyed stats contract
5. **H1** — `write_log` durability via fsync
6. **H5** — `.cursor/` added to `.gitignore`
7. **M8** — `TestCountFact` rename to silence pytest collection warning

---

## W1 — `/tree` endpoint safety

**Files**: `seam_runtime/server.py`
**Failing test**: `tests/audit/test_tree_endpoint_safety.py`

Test asserts (using FastAPI `TestClient`):
- `GET /tree?path=/etc` returns 400 with detail mentioning "outside root"
- `GET /tree?path=../..` returns 400 with detail mentioning "outside root"
- `GET /tree?path=does-not-exist` returns 404
- `GET /tree?path=.` returns 200 and:
  - response includes keys `root`, `path`, `tree`, `truncated`, `entries_seen`, `max_depth`, `max_entries`
  - every entry's `id` is a relative path (no leading `/`) under the root
  - `path` field equals `"."`
- With env `SEAM_API_TREE_MAX_DEPTH=1`, no grandchild entries appear in
  the response (folders include empty `children: []` rather than recursing)
- With env `SEAM_API_TREE_MAX_ENTRIES=2`, `truncated == True` and
  `entries_seen >= 2`
- `GET /tree` (default `path`) with a deliberately unreadable subdirectory
  in the tree does NOT raise — that subdirectory's `children` is reported as
  `[]` and an `error` key is included on that folder node with the exception
  class name. (Use `tmp_path` chmod 000 fixture or skip with reason on
  platforms that don't support that.)

**Fix**:
- Add module-level helpers at the top of `seam_runtime/server.py` (after
  the `_env_truthy` helper, before `create_app`):
  - `_tree_root() -> Path` — reads `SEAM_API_TREE_ROOT` env, defaults to
    `Path.cwd()`. Resolves and returns.
  - `_tree_max_depth() -> int` — reads `SEAM_API_TREE_MAX_DEPTH`, defaults
    to 4, clamped to `[0, 16]`.
  - `_tree_max_entries() -> int` — reads `SEAM_API_TREE_MAX_ENTRIES`,
    defaults to 2000, clamped to `[1, 100000]`.
  - `_resolve_tree_path(root: Path, requested: str) -> Path` — joins
    `root / requested`, calls `.resolve()`, raises `ValueError` if the
    result is not `is_relative_to(root)` (use `Path.is_relative_to` —
    available 3.9+).
  - `_walk_tree(start, root, *, depth, max_depth, max_entries, counter, truncated, skip_dirs) -> list[dict]`
    — iterative or recursive walk, increments `counter[0]`, sets
    `truncated[0] = True` when the cap is hit, returns sorted folder-first
    list of nodes. Skip names in
    `{"__pycache__", "node_modules", "build", "dist", ".venv", "venv"}`
    (note: do NOT blanket-skip dotfiles — allow `.seam` as the existing
    code did, but skip other dotfiles by default).
    On per-entry `PermissionError`/`OSError`: emit the folder node with
    `children=[]` and `error=type(exc).__name__`; do not raise.
- Rewrite the `tree` handler in `create_app` to:
  - call `_tree_root()`, `_resolve_tree_path(root, path)`,
    `_tree_max_depth()`, `_tree_max_entries()`
  - return `HTTPException(400, "outside root")` on ValueError
  - return `HTTPException(404, "path not found")` if `start` doesn't exist
  - return `HTTPException(400, "path is not a directory")` if not a dir
  - return the documented response shape with `entries_seen`, `truncated`,
    `max_depth`, `max_entries`

Entries' `id` field MUST be the path's `relative_to(root).as_posix()` — never absolute.

**Out of scope**: WebUI dashboard.html consumer updates (Claude does
those). Pagination beyond truncation flag. Symlink-following changes —
keep the existing `follow_symlinks=False` semantics.

**Verify**: `python -m pytest tests/audit/test_tree_endpoint_safety.py -q`

---

## W2 — `/benchmark` endpoint policy + suite validation

**Files**: `seam_runtime/server.py`
**Failing test**: `tests/audit/test_benchmark_endpoint_safety.py`

Test asserts:
- `POST /benchmark {"suite":"all"}` with auth returns 200 (smoke; expect
  the response to be a dict — do NOT block on benchmark content; the suite
  list at module level `BENCHMARK_SUITES` is the validation source)
- `POST /benchmark {"suite":"../etc"}` returns 422 (or 400) with detail
  mentioning "invalid suite"
- `POST /benchmark {"suite":"all","holdout":true}` returns 403 with detail
  mentioning `SEAM_API_ALLOW_BENCHMARK_HOLDOUT`
- `POST /benchmark {"suite":"all","holdout":true}` with env
  `SEAM_API_ALLOW_BENCHMARK_HOLDOUT=1` and the existing
  `SEAM_API_CONFIRM_HOLDOUT=1` returns 200 (mirrors CLI's
  `--confirm-holdout`; if the CLI flag uses a different env var, follow
  the existing CLI's convention — read `seam_runtime/cli.py`'s holdout
  handling and reuse the exact env name)

**Fix**:
- Validate `suite` against `seam_runtime.benchmarks.BENCHMARK_SUITES`
  (allow `"all"` plus members of that tuple). Reject everything else with
  HTTPException(400, "invalid suite").
- When `payload.get("holdout")` is truthy:
  - require `os.environ.get("SEAM_API_ALLOW_BENCHMARK_HOLDOUT") == "1"`
  - if missing, raise HTTPException(403, "holdout requires
    SEAM_API_ALLOW_BENCHMARK_HOLDOUT=1; see REPO_LEDGER Benchmark
    Publication Policy")
- (Defer async-queue / worker-block protection — note in
  `additional_observations`.)

**Out of scope**: Async/job queue. Rate limit per-endpoint scaling.
Benchmark suite implementation changes.

**Verify**: `python -m pytest tests/audit/test_benchmark_endpoint_safety.py -q`

---

## W3 — `/sys-metrics` honest errors + platform check

**Files**: `seam_runtime/server.py`
**Failing test**: `tests/audit/test_sys_metrics_honesty.py`

Test asserts:
- Response shape: top-level keys `cpu`, `mem`, `disk`, `gpu`, `net`.
  Each value is an object: `{"value": float|null, "source":
  "live"|"unavailable"|"unsupported", "error": str|null}`
- On the current host (Linux test environment): `cpu.source == "live"` and
  `cpu.value` is a float in `[0, 100]`; same for `mem` and `disk`
- `gpu` and `net` MUST report `source == "unsupported"` and `value is
  None` (not implemented yet — do NOT return fake numbers)
- When `sys.platform` is patched to `"win32"`, every metric returns
  `source == "unsupported"` and `value is None`
- When `/proc/stat` open is patched to raise `PermissionError`, `cpu`
  returns `source == "unavailable"`, `value is None`, `error ==
  "PermissionError"` (other metrics unaffected)
- `disk.source == "live"`'s underlying statvfs call targets the SEAM data
  directory's filesystem, not `/`. (Test by setting `runtime.store.path`
  to a tmp path and verifying the response reports that path's
  filesystem capacity. If the test cannot reliably verify the actual
  device, at least assert the handler reads `runtime.store.path` —
  check via a logging spy or by passing a tmp path that doesn't exist
  yet, in which case `source == "unavailable"`.)

**Fix**:
- Replace the current `sys_metrics` handler with a version that builds a
  per-metric object via helper functions:
  - `_metric_value(value: float) -> dict` returns `{"value": round(value,1), "source": "live", "error": None}`
  - `_metric_unavailable(exc) -> dict` returns `{"value": None, "source": "unavailable", "error": type(exc).__name__}`
  - `_metric_unsupported() -> dict` returns `{"value": None, "source": "unsupported", "error": None}`
- Platform gate: if `not sys.platform.startswith("linux")`, return all
  five metrics as unsupported.
- CPU: read `/proc/stat`, compute idle/total delta against the
  `nonlocal _last_cpu_times` closure (keep existing pattern). On any
  `OSError`, return unavailable with the exception class name.
- Memory: read `/proc/meminfo`, parse `MemTotal` and `MemAvailable`;
  return live or unavailable.
- Disk: derive `data_dir = Path(runtime.store.path).expanduser().resolve().parent`;
  call `os.statvfs(str(data_dir))`. Return live or unavailable. If
  `data_dir` doesn't exist, return unavailable with `FileNotFoundError`.
- GPU and NET: always return `_metric_unsupported()` (no fake numbers).
- Remove all bare `except Exception: <fake number>` paths.

**Out of scope**: GPU implementation. Net implementation. Multi-disk
reporting. Windows/macOS implementations (those just return "unsupported"
for now and that is honest).

**Verify**: `python -m pytest tests/audit/test_sys_metrics_honesty.py -q`

---

## W4 — `record_kinds` symbol-keyed stats contract

**Files**: `seam_runtime/mirl.py`, `seam_runtime/storage.py`
**Failing test**: `tests/audit/test_stats_record_kinds_keys.py`

Background: `storage.get_stats()` now returns `record_kinds` keyed by
`RecordKind.value` (`"CLM"`, `"ENT"`, ...) but the dashboard reads
single-char MIRL tags (`"#"`, `"@"`, ...). The single-char palette is
canonical (see `experimental/webui/public/dashboard.html:2346` tagColors).

Canonical mapping (extracted from dashboard + REPO_LEDGER usage):
- `ENT` → `@`
- `CLM` → `#`
- `EVT` → `!`
- `REL` → `>`
- `STA` → `~`
- `PROV` → `^`
- `RAW` → `%`
- `SYM` → `=`
- `SPAN` → `§`  (no dashboard color; included for completeness)
- `PACK` → `◇` (no dashboard color; included for completeness)

Test asserts:
- `from seam_runtime.mirl import SYMBOL_FOR_KIND, RecordKind` succeeds
- `SYMBOL_FOR_KIND` has an entry for EVERY member of `RecordKind`
- The mapping matches the canonical table above
- After persisting a small batch with one ENT, one CLM, and one STA:
  `store.get_stats()["record_kinds"] == {"@": 1, "#": 1, "~": 1}`
  (only kinds with records present; do not pre-fill zeros)

**Fix**:
- In `seam_runtime/mirl.py`, after the `RecordKind` enum definition, add:
  ```python
  SYMBOL_FOR_KIND: dict[RecordKind, str] = {
      RecordKind.ENT: "@",
      RecordKind.CLM: "#",
      RecordKind.EVT: "!",
      RecordKind.REL: ">",
      RecordKind.STA: "~",
      RecordKind.PROV: "^",
      RecordKind.RAW: "%",
      RecordKind.SYM: "=",
      RecordKind.SPAN: "§",
      RecordKind.PACK: "◇",
  }
  assert set(SYMBOL_FOR_KIND.keys()) == set(RecordKind), "SYMBOL_FOR_KIND must cover every RecordKind"
  ```
- In `seam_runtime/storage.py` `get_stats`, replace the line that builds
  `record_kinds` with a translation through `SYMBOL_FOR_KIND`:
  ```python
  from .mirl import SYMBOL_FOR_KIND, RecordKind
  ...
  record_kinds: dict[str, int] = {}
  for row in kinds_rows:
      try:
          kind_enum = RecordKind(row["kind"])
      except ValueError:
          continue  # ignore unknown kinds without raising
      symbol = SYMBOL_FOR_KIND.get(kind_enum)
      if symbol is None:
          continue
      record_kinds[symbol] = row["c"]
  ```
- Keep the rest of `get_stats` unchanged. Do NOT remove existing keys.

**Out of scope**: dashboard.html updates (Claude does). Adding new
RecordKind members. Changing the canonical symbol palette.

**Verify**: `python -m pytest tests/audit/test_stats_record_kinds_keys.py -q`

---

## H1 — `write_log` durability via fsync

**Files**: `tools/streams/streams_lib.py`
**Failing test**: `tests/audit/test_streams_fsync.py`

Test asserts:
- After `streams_lib.write_log(kind, data)`, the bytes are flushed to disk
  beyond the OS page cache. Direct verification is hard in CPython; use a
  proxy: spy on `os.fsync` via `unittest.mock.patch` and assert it was
  called exactly once with the file descriptor of the written log file,
  AND that the parent directory was also fsync'd (POSIX durability
  pattern: fsync the file + fsync the dir).

**Fix**:
- Replace `write_log`'s body. The new pattern:
  ```python
  def write_log(kind: str, data: bytes) -> None:
      p = log_path(kind)
      p.parent.mkdir(parents=True, exist_ok=True)
      fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
      try:
          os.write(fd, data)
          os.fsync(fd)
      finally:
          os.close(fd)
      # Best-effort parent-dir fsync (POSIX; Windows raises — swallow there)
      try:
          dir_fd = os.open(str(p.parent), os.O_RDONLY)
          try:
              os.fsync(dir_fd)
          finally:
              os.close(dir_fd)
      except OSError:
          pass
  ```
- Do NOT change the `append_event` lock pattern. fsync sits inside the
  existing lock, so durability is reached before the lock is released.

**Out of scope**: `read_log` changes. `append_event` changes. fsync on
history root files (separate item next cycle).

**Verify**: 
```
python -m pytest tests/audit/test_streams_fsync.py -q
python -m tools.streams.verify_streams
```

Both must pass.

---

## H5 — `.cursor/` added to `.gitignore`

**Files**: `.gitignore`
**Failing test**: `tests/audit/test_gitignore_agent_dirs.py`

Test asserts:
- Parsing `.gitignore` line-by-line, the patterns include exact-match
  entries for `.cursor/` (under the "Local editor and agent config"
  section, alongside `.vscode/` and `.gemini/`).

**Fix**:
- Open `.gitignore`, find the comment block `# Local editor and agent
  config`, append `.cursor/` after `.vscode/` (alphabetical order: `.cursor/`,
  `.gemini/`, `.opencode/...`, `.vscode/` — preserve existing order; add
  `.cursor/` before `.gemini/` if alphabetical, otherwise just add after
  `.vscode/`). Match the existing style (trailing slash, no leading dot
  escaping).

**Out of scope**: Other agent dirs. Pre-commit hook scope-block list
update (separate concern).

**Verify**: `python -m pytest tests/audit/test_gitignore_agent_dirs.py -q`

---

## M8 — `TestCountFact` rename to silence pytest collection warning

**Files**: `tools/history/test_count_audit.py`, plus every file that
imports the symbol (DeepSeek MUST grep first and confirm scope).
**Failing test**: existing `tools/history/test_history_tools.py` if it
references the symbol — otherwise no new test needed; this is a quality
fix verified by absence of warning.

Test (light): `tests/audit/test_no_test_class_warning.py` asserts
`pytest --collect-only -q tools/history/test_count_audit.py` exits 0
AND stdout/stderr contain neither the substring `PytestCollectionWarning`
nor `cannot collect test class`.

**Fix**:
- Grep: `grep -rn "TestCountFact" .` (excluding `archive/`, `build/`, `.venv/`)
- In `tools/history/test_count_audit.py`, rename the dataclass
  `TestCountFact` → `CountFactRecord`. Update every reference found in
  the grep, including type annotations and string literals. Do NOT change
  behavior.

**Out of scope**: Other pytest warnings. Renaming other dataclasses.

**Verify**: 
```
python -m pytest tests/audit/test_no_test_class_warning.py -q
python -m pytest --collect-only -q tools/history/test_count_audit.py
python -m pytest test_seam_all/test_seam.py tools/history/test_history_tools.py -q
```

The middle command must NOT print `PytestCollectionWarning`. The full
test suite must remain green.

---

## After all items complete

Emit ITEM_SUCCESS blocks for W1, W2, W3, W4, H1, H5, M8 in execution
order in a single paste. Then STOP. Do NOT stage. Do NOT commit. Do NOT
push. Claude reviews the full diff, applies the WebUI consumer updates,
appends HISTORY entries, rebuilds the index, writes a snapshot, runs the
four verify gates, and commits per item.

If at any point a stop condition fires, emit ITEM_SUCCESS blocks for
completed items + the appropriate stop block for the failed item, then
STOP — do not attempt the remaining items.
