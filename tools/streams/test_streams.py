"""Smoke tests for the Context Streams substrate."""
from __future__ import annotations

import unittest
from pathlib import Path

from tools.history.history_lib import HISTORY_PATH, INDEX_PATH
from tools.streams.history_adapter import sync_history_mirror, verify_history_mirror
from tools.streams.rebuild_cross_index import ARCHIVE_DIR, collect_all_events, rebuild_cross_index
from tools.streams.rebuild_index import rebuild_index
from tools.streams.roadmap_parser import (
    ROADMAP_PATH,
    parse_roadmap_markers,
    items_to_events,
    render_state_md,
)
from tools.streams.streams_lib import (
    STREAMS_ROOT,
    CROSS_INDEX_PATH,
    format_event,
    parse_events,
)
from tools.streams.verify_streams import verify_all


class StreamsLibTests(unittest.TestCase):
    def test_format_then_parse_roundtrip(self) -> None:
        block = format_event(
            kind="roadmap",
            id=1,
            date="2026-05-15T00:00:00Z",
            agent="test",
            fields={
                "kind": "status-change",
                "item": "roadmap:track:X1",
                "event": "bootstrap",
                "from": "(initial)",
                "to": "now",
                "supersedes": "none",
                "refs": "ROADMAP.md:1",
                "topics": "roadmap, plan",
                "tokens": "10",
            },
            body="Test body.",
        )
        events = parse_events(block.encode("utf-8"), "roadmap")
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt.id, 1)
        self.assertEqual(evt.kind, "roadmap")
        self.assertEqual(evt.fields["item"], "roadmap:track:X1")
        self.assertEqual(evt.fields["to"], "now")
        self.assertEqual(evt.body, "Test body.")

    def test_history_kind_uses_entry_delim(self) -> None:
        block = format_event(
            kind="history",
            id=1,
            date="2026-05-15T00:00:00Z",
            agent="test",
            fields={"status": "done", "topics": "history", "supersedes": "none", "tokens": "5", "commits": "none", "refs": "none"},
            body="x",
            history_compat=True,
        )
        self.assertIn("---BEGIN-ENTRY-#001---", block)
        self.assertIn("---END-ENTRY-#001---", block)


class HistoryAdapterTests(unittest.TestCase):
    def test_mirror_matches_root_bytes(self) -> None:
        sync_history_mirror()
        log = STREAMS_ROOT / "history" / "log.md"
        idx = STREAMS_ROOT / "history" / "index.md"
        self.assertEqual(log.read_bytes(), HISTORY_PATH.read_bytes())
        self.assertEqual(idx.read_bytes(), INDEX_PATH.read_bytes())
        self.assertEqual(verify_history_mirror(), [])


class RoadmapParserTests(unittest.TestCase):
    def test_extracts_track_h_items(self) -> None:
        items = parse_roadmap_markers(ROADMAP_PATH.read_text(encoding="utf-8"))
        ids = {it.item_id for it in items}
        self.assertIn("roadmap:track:H1", ids)
        self.assertIn("roadmap:track:H2", ids)
        self.assertIn("roadmap:track:H3", ids)
        self.assertIn("roadmap:track:H4", ids)

    def test_extracts_tracks_i_j_k_l_items(self) -> None:
        items = parse_roadmap_markers(ROADMAP_PATH.read_text(encoding="utf-8"))
        ids = {it.item_id for it in items}
        self.assertIn("roadmap:track:I", ids)
        self.assertIn("roadmap:track:J", ids)
        self.assertIn("roadmap:track:K", ids)
        self.assertIn("roadmap:track:L", ids)

    def test_agent_compiler_is_not_labeled_as_track_h(self) -> None:
        text = ROADMAP_PATH.read_text(encoding="utf-8")
        self.assertNotIn("Track H: Agent / Skills Compiler", text)

    def test_events_have_sequential_ids_and_required_fields(self) -> None:
        items = parse_roadmap_markers(ROADMAP_PATH.read_text(encoding="utf-8"))
        events = items_to_events(items)
        self.assertEqual(len(events), len(items))
        for evt in events:
            self.assertIn("item", evt["fields"])
            self.assertIn("to", evt["fields"])

    def test_state_md_buckets_by_status(self) -> None:
        items = parse_roadmap_markers(ROADMAP_PATH.read_text(encoding="utf-8"))
        text = render_state_md(items)
        # At least one status bucket is rendered.
        self.assertTrue(any(h in text for h in ("## now", "## in-progress", "## planned", "## later", "## done")))
        self.assertIn("roadmap:track:H1", text)


class CrossIndexTests(unittest.TestCase):
    def test_cross_index_includes_both_streams(self) -> None:
        rebuild_index("history")
        rebuild_index("roadmap")
        rebuild_index("experience")
        rebuild_cross_index()
        items = collect_all_events()
        kinds = {it["ref"].split(":", 1)[0] for it in items}
        self.assertIn("history", kinds)
        self.assertIn("roadmap", kinds)
        self.assertTrue(CROSS_INDEX_PATH.exists())

    def test_rebuild_cross_index_removes_stale_archive_chunks(self) -> None:
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        stale = ARCHIVE_DIR / "9999-9999.cross.md"
        stale.write_text("# stale\n", encoding="utf-8")

        rebuild_cross_index()

        self.assertFalse(stale.exists())


class BuildContextPackTests(unittest.TestCase):
    def test_roadmap_pack_returns_latest_events(self) -> None:
        from tools.streams.build_context_pack import build_stream_pack
        result = build_stream_pack("roadmap", latest=3, budget=10_000)
        self.assertEqual(result["stream"], "roadmap")
        self.assertLessEqual(len(result["included_ids"]), 3)
        self.assertIn("BEGIN-ROADMAP-EVENT", result["pack"])

    def test_roadmap_pack_budget_skips_oldest(self) -> None:
        from tools.streams.build_context_pack import build_stream_pack
        result = build_stream_pack("roadmap", latest=10, budget=50)
        self.assertGreaterEqual(len(result["included_ids"]), 1)
        self.assertLessEqual(result["tokens_used"], 200)

    def test_history_delegation_via_module(self) -> None:
        import io, sys
        from contextlib import redirect_stdout
        from tools.streams import build_context_pack as wrapper
        buf = io.StringIO()
        with redirect_stdout(buf):
            wrapper.main(["--stream", "history", "--latest", "1", "--token-budget", "200"])
        out = buf.getvalue()
        # Output should contain a history entry block (legacy ENTRY delim).
        self.assertIn("BEGIN-ENTRY-#", out)


class VerifyStreamsTests(unittest.TestCase):
    def test_verify_returns_no_errors_after_seed(self) -> None:
        sync_history_mirror()
        rebuild_index("history")
        rebuild_index("roadmap")
        rebuild_index("experience")
        rebuild_cross_index()
        self.assertEqual(verify_all(), [])

    def test_verify_detects_stale_cross_index(self) -> None:
        sync_history_mirror()
        rebuild_index("history")
        rebuild_index("roadmap")
        rebuild_index("experience")
        rebuild_cross_index()
        original = CROSS_INDEX_PATH.read_text(encoding="utf-8")
        try:
            stale = original.replace("total_events:", "total_events: 0 # stale", 1)
            CROSS_INDEX_PATH.write_text(stale, encoding="utf-8")
            self.assertTrue(any("cross_index.md is stale" in err for err in verify_all()))
        finally:
            CROSS_INDEX_PATH.write_text(original, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
