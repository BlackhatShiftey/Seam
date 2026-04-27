"""Verify the SEAM history routing taxonomy."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from tools.history.history_lib import HISTORY_PATH, REPO_ROOT, parse_entries, read_history_bytes

MANIFEST_PATH = Path(__file__).with_name("routing_manifest.json")
ROUTE_ID_RE = re.compile(r"^[a-z0-9]+(?:/[a-z0-9][a-z0-9-]*)*$")
VALID_STATUSES = {"active", "moved", "retired"}
REQUIRED_ROUTE_FIELDS = {
    "id",
    "parent",
    "status",
    "description",
    "match_topics",
    "match_refs",
    "ledger",
    "introduced",
    "supersedes",
    "moved_to",
    "retired_reason",
}


def load_manifest(path: Path = MANIFEST_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _entry_ids(history_path: Path = HISTORY_PATH) -> set[int]:
    data = read_history_bytes(history_path)
    entries = parse_entries(data) if data else []
    return {entry.id for entry in entries}


def _parse_entry_id(raw: Any) -> int | None:
    if raw in (None, "none", ""):
        return None
    try:
        return int(str(raw).lstrip("#"))
    except ValueError:
        return None


def _has_cycle(route_id: str, parents: dict[str, str | None]) -> bool:
    seen: set[str] = set()
    current: str | None = route_id
    while current:
        if current in seen:
            return True
        seen.add(current)
        current = parents.get(current)
    return False


def verify_routing(
    manifest_path: Path = MANIFEST_PATH,
    *,
    repo_root: Path = REPO_ROOT,
    history_path: Path = HISTORY_PATH,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        manifest = load_manifest(manifest_path)
    except (OSError, json.JSONDecodeError) as e:
        return False, [f"manifest load failed: {e}"]

    if manifest.get("schema") != "seam-history-routing/v1":
        errors.append("manifest schema must be seam-history-routing/v1")

    routes = manifest.get("routes")
    if not isinstance(routes, list) or not routes:
        errors.append("manifest routes must be a non-empty list")
        return False, errors

    ids: set[str] = set()
    parents: dict[str, str | None] = {}
    history_ids = _entry_ids(history_path)

    for idx, route in enumerate(routes):
        if not isinstance(route, dict):
            errors.append(f"route[{idx}] must be object")
            continue
        missing = REQUIRED_ROUTE_FIELDS - set(route)
        if missing:
            errors.append(f"route[{idx}] missing fields: {', '.join(sorted(missing))}")
            continue

        route_id = route["id"]
        if not isinstance(route_id, str) or not ROUTE_ID_RE.match(route_id):
            errors.append(f"route[{idx}] has invalid id {route_id!r}")
            continue
        if route_id in ids:
            errors.append(f"duplicate route id {route_id}")
        ids.add(route_id)
        parents[route_id] = route["parent"]

        status = route["status"]
        if status not in VALID_STATUSES:
            errors.append(f"route {route_id} has invalid status {status!r}")

        if route["parent"] is not None:
            parent = route["parent"]
            if not isinstance(parent, str) or not ROUTE_ID_RE.match(parent):
                errors.append(f"route {route_id} has invalid parent {parent!r}")
            elif not route_id.startswith(parent + "/"):
                errors.append(f"route {route_id} parent {parent} does not match path hierarchy")

        if status == "moved" and not route["moved_to"]:
            errors.append(f"route {route_id} status=moved requires moved_to")
        if status == "retired" and not route["retired_reason"]:
            errors.append(f"route {route_id} status=retired requires retired_reason")
        if status == "active" and (route["moved_to"] or route["retired_reason"]):
            errors.append(f"route {route_id} is active but has moved_to/retired_reason")

        for field in ("match_topics", "match_refs"):
            if not isinstance(route[field], list):
                errors.append(f"route {route_id} field {field} must be a list")

        ledger = route["ledger"]
        if ledger is not None and not (repo_root / ledger).exists():
            errors.append(f"route {route_id} ledger path does not exist: {ledger}")

        for field in ("introduced", "supersedes"):
            parsed = _parse_entry_id(route[field])
            if parsed is None:
                if route[field] not in ("none", None):
                    errors.append(f"route {route_id} field {field} has invalid entry id {route[field]!r}")
                continue
            if parsed not in history_ids:
                errors.append(f"route {route_id} field {field} references missing HISTORY#{parsed:03d}")

    for route_id, parent in parents.items():
        if parent is not None and parent not in ids:
            errors.append(f"route {route_id} parent missing: {parent}")
        if _has_cycle(route_id, parents):
            errors.append(f"route {route_id} has parent cycle")

    for route in routes:
        moved_to = route.get("moved_to") if isinstance(route, dict) else None
        if moved_to and moved_to not in ids:
            errors.append(f"route {route.get('id')} moved_to missing: {moved_to}")

    return len(errors) == 0, errors


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify history routing taxonomy.")
    p.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    p.add_argument("--history", type=Path, default=HISTORY_PATH)
    p.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    ok, errors = verify_routing(args.manifest, repo_root=args.repo_root, history_path=args.history)
    if args.json:
        print(json.dumps({"ok": ok, "errors": errors}, indent=2))
    elif ok:
        print("Routing OK")
    else:
        print("Routing FAILED:")
        for err in errors:
            print(f"  - {err}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
