"""Rebuild the derived global .seam/cross_index.md from per-stream logs.

The cross-index is the temporal join across all streams. It is a derived
artifact (mirrors how HISTORY_INDEX.md is derived from HISTORY.md), never
hand-edited, and reproducible from the stream logs at any time. Two-tier:
the most recent 200 events are inlined as a hot zone; the rest roll into
archive chunks under .seam/cross_index_archive/.
"""
from __future__ import annotations

import os
from pathlib import Path

from tools.streams.streams_lib import (
    CROSS_INDEX_PATH,
    REPO_ROOT,
    list_stream_kinds,
    parse_events,
    read_log,
)

HOT_ZONE_MAX = 200
ARCHIVE_DIR = REPO_ROOT / ".seam" / "cross_index_archive"


def collect_all_events() -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for kind in list_stream_kinds() or ["history", "roadmap", "experience"]:
        data = read_log(kind)
        if not data:
            continue
        try:
            events = parse_events(data, kind)
        except ValueError:
            continue
        for evt in events:
            items.append({
                "utc": evt.date,
                "ref": f"{evt.kind}:{evt.id:03d}:{evt.hash_short[:8]}",
                "kind": evt.fields.get("kind", "session-event" if evt.kind == "history" else ""),
                "event": evt.fields.get("event", evt.fields.get("status", "")),
                "topics": evt.fields.get("topics", ""),
                "refs": evt.fields.get("refs", ""),
                "_sort": (evt.date, evt.kind, evt.id),
            })
    items.sort(key=lambda it: it["_sort"])
    return items


def render_table(rows: list[dict[str, object]]) -> str:
    lines = [
        "| utc | stream:id:hash | kind | event | topics | refs |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        topics = str(r["topics"])
        topics_disp = topics if len(topics) <= 60 else topics[:57] + "..."
        refs = str(r["refs"])
        refs_disp = refs if len(refs) <= 80 else refs[:77] + "..."
        lines.append(
            f"| {r['utc']} | {r['ref']} | {r['kind']} | {r['event']} | {topics_disp} | {refs_disp} |"
        )
    return "\n".join(lines)


def rebuild_cross_index() -> dict[str, object]:
    items = collect_all_events()
    total = len(items)
    hot = items[-HOT_ZONE_MAX:] if total > HOT_ZONE_MAX else items
    cold = items[:-HOT_ZONE_MAX] if total > HOT_ZONE_MAX else []

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_pointers: list[str] = []
    new_chunk_names: set[str] = set()
    tmp_pairs: list[tuple[Path, Path]] = []  # (tmp, target)

    # Phase 1 — write all new content to .tmp files first.
    if cold:
        chunk_path = ARCHIVE_DIR / f"0001-{len(cold):04d}.cross.md"
        new_chunk_names.add(chunk_path.name)
        tmp_path = chunk_path.with_name(chunk_path.name + ".tmp")
        tmp_path.write_text(
            "# Cross-Index Archive Chunk\n\n" + render_table(cold) + "\n",
            encoding="utf-8",
        )
        tmp_pairs.append((tmp_path, chunk_path))
        archive_pointers.append(
            f"| {chunk_path.name} | {cold[0]['utc']}..{cold[-1]['utc']} | {len(cold)} | (multi) | (multi) |"
        )

    header = [
        "# Cross-Index",
        "",
        "schema: seam-cross-index/v1",
        "source: streams/*/log.md (derived; do not hand-edit)",
        f"total_events: {total}",
        f"hot_zone_max: {HOT_ZONE_MAX}",
        "archive_pattern: cross_index_archive/<lo>-<hi>.cross.md",
        "",
        f"## Hot Zone (latest {len(hot)} events, oldest first)",
        "",
    ]
    body = render_table(list(reversed(hot)) if False else hot)
    archive_section = [
        "",
        "",
        "## Archive Pointers",
        "",
        "| chunk | utc_range | event_count | streams | top_topics |",
        "|---|---|---|---|---|",
    ]
    archive_section.extend(archive_pointers)

    text = "\n".join(header) + body + ("\n" + "\n".join(archive_section) if archive_pointers else "") + "\n"
    CROSS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    cross_tmp = CROSS_INDEX_PATH.with_name(CROSS_INDEX_PATH.name + ".tmp")
    cross_tmp.write_text(text, encoding="utf-8")
    tmp_pairs.append((cross_tmp, CROSS_INDEX_PATH))

    # Phase 2 — commit all .tmp files via atomic rename.
    for tmp, target in tmp_pairs:
        os.replace(tmp, target)

    # Phase 3 — clean up stale archive chunks not in the new set.
    for stale in ARCHIVE_DIR.glob("*.cross.md"):
        if stale.name not in new_chunk_names:
            stale.unlink()

    return {
        "total": total,
        "hot": len(hot),
        "cold": len(cold),
        "path": str(CROSS_INDEX_PATH),
    }


def main() -> int:
    result = rebuild_cross_index()
    print(f"cross-index rebuilt: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
