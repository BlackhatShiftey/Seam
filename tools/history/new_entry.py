"""Append a new entry to HISTORY.md and regenerate HISTORY_INDEX.md.

Usage:
    python -m tools.history.new_entry \\
        --agent claude-sonnet-4-6 \\
        --status done \\
        --topics dashboard,tui \\
        --commits 8f2a6bb \\
        --refs ROADMAP.md#track-a0 \\
        --body "Entry body text..."

Or with body from stdin:
    echo "body text" | python -m tools.history.new_entry --agent ... --status ... --topics ...
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys

from tools.history.history_lib import (
    HISTORY_PATH,
    estimate_tokens,
    format_entry,
    next_entry_id,
    parse_entries,
    read_history_bytes,
)
from tools.history.rebuild_index import rebuild


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Append a history entry.")
    p.add_argument("--agent", required=True)
    p.add_argument("--status", required=True)
    p.add_argument("--topics", required=True, help="comma-separated tags")
    p.add_argument("--commits", default="none")
    p.add_argument("--refs", default="none")
    p.add_argument("--supersedes", default="none")
    p.add_argument("--date", default=None, help="ISO 8601; defaults to now UTC")
    p.add_argument("--body", default=None, help="body text; if omitted, read stdin")
    args = p.parse_args(argv)

    body = args.body if args.body is not None else sys.stdin.read()
    body = body.strip()
    if not body:
        print("ERROR: body is empty", file=sys.stderr)
        return 2

    date = args.date or _now_iso()
    topics = [t.strip() for t in args.topics.split(",") if t.strip()]
    tokens = estimate_tokens(body)

    existing = read_history_bytes()
    entries = parse_entries(existing) if existing else []
    new_id = next_entry_id(entries)

    # Normalize supersedes format: accept "042" or "#042" → store as "042"
    supersedes = args.supersedes
    if supersedes != "none":
        supersedes = supersedes.lstrip("#")
        try:
            int(supersedes)
        except ValueError:
            print(f"ERROR: --supersedes must be an entry id or 'none'", file=sys.stderr)
            return 2

    entry_text = format_entry(
        id=new_id,
        date=date,
        agent=args.agent,
        status=args.status,
        topics=topics,
        commits=args.commits,
        refs=args.refs,
        supersedes=supersedes,
        tokens=tokens,
        body=body,
    )

    # Append with a blank line separator if file is non-empty
    with open(HISTORY_PATH, "ab") as f:
        if existing and not existing.endswith(b"\n\n"):
            if existing.endswith(b"\n"):
                f.write(b"\n")
            else:
                f.write(b"\n\n")
        f.write(entry_text.encode("utf-8"))

    n = rebuild()
    print(f"Appended #{new_id:03d}. HISTORY.md now has {n} entries.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
