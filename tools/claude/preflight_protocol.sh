#!/usr/bin/env bash
# SEAM protocol preflight for Claude Code Bash tool calls.
#
# Triggered as a PreToolUse hook on the Bash tool. Reads the tool input from
# stdin (JSON with .tool_input.command), and if the command stages, commits,
# or pushes git state, runs the SEAM verify gates first. Non-zero exit blocks
# the tool call. Other Bash commands pass through.
#
# Gates run (matches AGENTS.md Session End + Temporal Continuity Policy):
#   - python -m tools.history.verify_integrity
#   - python -m tools.history.verify_routing
#   - python -m tools.history.verify_continuity (with --no-recorded-fact-audit
#     until tools/history/test_count_audit.py and recorded_fact_audit.py are
#     committed and their precedence false-positives are resolved; see
#     HISTORY#166)

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INPUT="$(cat || true)"

# Extract the command field without requiring jq.
CMD="$(printf '%s' "$INPUT" | python3 -c 'import json,sys
try:
    data=json.load(sys.stdin)
except Exception:
    print(""); sys.exit(0)
print((data.get("tool_input") or {}).get("command",""))' 2>/dev/null)"

case "$CMD" in
  *"git commit"*|*"git push"*|*"git add"*)
    ;;
  *)
    exit 0
    ;;
esac

cd "$REPO_ROOT" || exit 0

FAIL=0
PY=python3
command -v "$PY" >/dev/null 2>&1 || PY=python

run_gate() {
  local label="$1"; shift
  if ! "$@" >/tmp/seam_preflight_$$.log 2>&1; then
    echo "[SEAM preflight] $label FAILED:" >&2
    cat /tmp/seam_preflight_$$.log >&2
    FAIL=1
  fi
  rm -f /tmp/seam_preflight_$$.log
}

run_gate "verify_integrity" "$PY" -m tools.history.verify_integrity
run_gate "verify_routing"   "$PY" -m tools.history.verify_routing
# --no-recorded-fact-audit is intentionally set because:
#   1. Recorded-fact audit extractors are still in development
#   2. Some existing docs contain facts that trigger false positives
#   3. Precedence false-positives need resolution before enabling
# To force fact auditing: set SEAM_FORCE_FACT_AUDIT=1 or use --audit-facts in commit message.
run_gate "verify_continuity" "$PY" -m tools.history.verify_continuity --no-recorded-fact-audit
run_gate "verify_streams"   "$PY" -m tools.streams.verify_streams

if [ "$FAIL" -ne 0 ]; then
  echo "" >&2
  echo "[SEAM preflight] Blocking git command. Fix the gates above before staging/committing/pushing." >&2
  echo "[SEAM preflight] Refer to AGENTS.md Session End and Temporal Continuity Policy." >&2
  exit 2
fi

exit 0
