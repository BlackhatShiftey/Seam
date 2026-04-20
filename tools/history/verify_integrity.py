"""Verify every HISTORY.md entry hash matches HISTORY_INDEX.md."""
from __future__ import annotations

import sys
from pathlib import Path

from tools.history.history_lib import parse_entries, read_history_bytes


def parse_index_hashes(index_text: str) -> dict[int, str]:
    """Extract id -> hash_short from the entries table.

    Supports compact index table format by looking up columns from the header row.
    """
    mapping: dict[int, str] = {}
    in_entries = False
    header: list[str] | None = None

    for line in index_text.splitlines():
        if line.startswith("## entries"):
            in_entries = True
            continue
        if in_entries and line.startswith("## "):
            break
        if not in_entries:
            continue
        if not line.startswith("|"):
            continue

        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        if all(c.startswith("-") for c in cells):
            continue

        lower = [c.lower() for c in cells]
        if "id" in lower and "hash" in " ".join(lower):
            header = lower
            continue
        if header is None:
            continue

        try:
            id_col = header.index("id")
        except ValueError:
            continue

        hash_col = None
        for i, col in enumerate(header):
            if "hash" in col:
                hash_col = i
                break
        if hash_col is None:
            continue
        if len(cells) <= max(id_col, hash_col):
            continue

        try:
            entry_id = int(cells[id_col])
        except ValueError:
            continue

        mapping[entry_id] = cells[hash_col].rstrip(".")

    return mapping


def verify(history_path: Path, index_path: Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    data = read_history_bytes(history_path)
    if not data:
        if index_path.exists() and "total_entries: 0" in index_path.read_text(encoding="utf-8"):
            return True, []
        errors.append("HISTORY.md is empty but INDEX is not")
        return False, errors

    try:
        entries = parse_entries(data)
    except ValueError as e:
        errors.append(f"Parse error: {e}")
        return False, errors

    if not index_path.exists():
        errors.append("HISTORY_INDEX.md does not exist")
        return False, errors

    index_hashes = parse_index_hashes(index_path.read_text(encoding="utf-8"))
    if len(entries) != len(index_hashes):
        errors.append(
            f"Entry count mismatch: HISTORY has {len(entries)}, INDEX has {len(index_hashes)}"
        )

    for e in entries:
        idx_hash = index_hashes.get(e.id)
        if idx_hash is None:
            errors.append(f"Entry #{e.id:03d} missing from INDEX")
            continue
        if not e.hash_short.startswith(idx_hash):
            errors.append(
                f"Entry #{e.id:03d}: INDEX hash {idx_hash!r} does not match computed {e.hash_short!r}"
            )

    return len(errors) == 0, errors


if __name__ == "__main__":
    from tools.history import history_lib

    ok, errors = verify(history_lib.HISTORY_PATH, history_lib.INDEX_PATH)
    if ok:
        print("Integrity OK")
        sys.exit(0)
    print("Integrity FAILED:")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)

