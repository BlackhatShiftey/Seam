# DeepSeek Corrections Ledger

Durable cold-start guidance for DeepSeek when executing SEAM SOPs.

Every DeepSeek-facing prompt lists this file in the protocol read order so
each fresh DeepSeek session learns from prior cycles' mistakes. Add a new
card whenever Claude catches DeepSeek doing something wrong. Each card
states the mistake, the root cause, the durable rule, and the detection
command Claude uses to catch repeats.

This ledger is append-only in spirit. Cards may be reworded for clarity
but must not be silently dropped — supersede with a new card when a rule
evolves.

---

## C1 — Orphaned `refs:` in HISTORY entries

**Mistake**: DeepSeek listed file paths in a HISTORY entry's `refs:` field
without staging the files. `verify_continuity` does not validate that
ref-file paths exist in the working tree or in git.

**Root cause**: Cold-start DeepSeek has no recollection of which files it
actually wrote vs. which it intended to write. The verify gate doesn't
catch the gap.

**Rule**: Before emitting any HISTORY entry text or any block that names
files in `refs:`, run `git ls-files <path>` for every path. If `ls-files`
returns nothing AND the file is not already tracked, do not name it in
`refs:`. Either stage it (out of scope for DeepSeek — surface it as
SCOPE_LIMIT_HIT) or omit it.

**Detection command Claude runs**:
```
for f in $(awk '/^refs:/,/^[a-z]+:/' HISTORY.md | tail -n +1 | head -1 | tr ',' '\n'); do
  git ls-files --error-unmatch "$f" 2>/dev/null || echo "MISSING: $f"
done
```

---

## C2 — Pre-existing red TDD ignored

**Mistake**: DeepSeek started an SOP without scanning the working tree for
operator-authored failing tests. SOPs ran cleanly per-item but the
pre-existing red tests remained red at handback.

**Root cause**: SOP "pre-flight" sections list verify gates and pytest,
but if pytest is ALREADY failing on operator-authored TDD, DeepSeek
shouldn't begin remediation until those tests are either folded into the
SOP or explicitly declared out-of-scope.

**Rule**: If the pre-flight `python -m pytest test_seam_all/test_seam.py
-q` reports any non-passing test that DeepSeek did NOT author in the
current session, STOP and emit MISSING_FILE-equivalent or
SCOPE_LIMIT_HIT with reason `pre_existing_red_tdd` and detail naming the
failing tests. Wait for Claude to either declare them out-of-scope or
fold them into the SOP.

**Detection command Claude runs**:
```
git diff --stat HEAD -- test_seam_all/ tests/
python -m pytest test_seam_all/test_seam.py -q 2>&1 | grep -E "FAIL|ERROR"
```

---

## C3 — `write_snapshot --entries` misuse

**Mistake**: DeepSeek invoked `python -m tools.history.write_snapshot
--entries 5` expecting "the latest 5 entries." The flag is a
comma-separated list of explicit IDs, so `--entries 5` produced a
snapshot containing only entry #5.

**Root cause**: The flag name reads like a count to a cold-start reader.
The tool's `--help` explains the actual semantics but DeepSeek didn't
consult it.

**Rule**: Before invoking any `tools/history/*` or `tools/streams/*`
command with arguments, run `python -m <module> --help` and read the
exact argument semantics. `--entries` ALWAYS takes a comma-separated ID
list; for "the latest N entries" use `--latest N` if the tool supports
it, otherwise build the comma-separated list explicitly with the latest
N IDs.

**Detection command Claude runs**:
```
python -m tools.history.write_snapshot --help | grep -A1 entries
```

---

## C4 — Editing files outside the item's `Files:` line

**Mistake**: DeepSeek made "while I'm here" edits to files not listed in
the item's `Files:` line — formatter passes, comment cleanups, type-hint
modernizations.

**Root cause**: Most lint/formatter agents reward broad cleanups. SEAM's
sync-relay protocol explicitly forbids them because each commit is
reviewed individually and unrelated changes pollute the diff.

**Rule**: For each item, the only files DeepSeek may modify are exactly
those listed in the item's `Files:` line PLUS any test file at the cited
`tests/audit/...` path. If DeepSeek sees an obvious adjacent issue, log
it in the ITEM_SUCCESS block's `additional_observations` field — do not
fix it.

**Detection command Claude runs**:
```
git diff --name-only | sort -u > /tmp/seam_changed.txt
# Compare to the union of Files: lines from the SOP items DeepSeek claims completed.
```

---

## C5 — Editing forbidden paths (history, snapshots, archive, webui)

**Mistake**: DeepSeek edited `HISTORY.md`, `HISTORY_INDEX.md`, files
under `.seam/`, files under `experimental/webui/`, or files under
`archive/` despite the SOP forbidding it.

**Root cause**: These paths look like normal repo files to a cold-start
agent. The SOP forbidden-path list must be read and respected as a hard
gate.

**Rule**: Never edit any of: `HISTORY.md`, `HISTORY_INDEX.md`,
`PROJECT_STATUS.md`, `REPO_LEDGER.md`, `ROADMAP.md`, anything under
`.seam/`, anything under `archive/`, anything under `docs/archive/`,
anything under `build/`, anything under `.venv/`, anything under
`test_seam/`, anything under `experimental/webui/`. If a fix requires
editing one of these, emit SCOPE_LIMIT_HIT with reason
`needs_history_edit` or `needs_experimental_webui_edit`.

**Detection command Claude runs**:
```
git diff --name-only | grep -E "^(HISTORY|HISTORY_INDEX|PROJECT_STATUS|REPO_LEDGER|ROADMAP)\.md|^\.seam/|^archive/|^docs/archive/|^build/|^test_seam/|^experimental/webui/" \
  && echo "FORBIDDEN-PATH EDITS DETECTED"
```

---

## How to add a new card

When Claude catches a new DeepSeek failure mode:

1. Pick the next card ID (`C6`, `C7`, ...).
2. Fill the four fields: Mistake / Root cause / Rule / Detection command.
3. Append the card at the bottom of this file.
4. Fold the rule into the next SOP's "Hard constraints" section so
   DeepSeek hits the rule before the verify gate.
5. Append a HISTORY entry citing this ledger update.
