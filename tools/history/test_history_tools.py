"""Unit tests for history tools."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.history import history_lib
from tools.history.history_lib import (
    compute_entry_hash,
    estimate_tokens,
    format_entry,
    next_entry_id,
    parse_entries,
    resolve_supersedes_chain,
)
from tools.history.rebuild_index import build_index_text, rebuild
from tools.history.verify_integrity import parse_index_hashes, verify
from tools.history.write_snapshot import write_snapshot
from tools.history.load_snapshot import load_and_verify


class TempRepoBase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.history = self.root / "HISTORY.md"
        self.index = self.root / "HISTORY_INDEX.md"
        self.snaps = self.root / ".seam" / "snapshots"
        self.snaps.mkdir(parents=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_entries(self, entries: list[str]) -> None:
        # Write raw bytes with LF line endings — HISTORY.md is canonical LF
        self.history.write_bytes(("\n\n".join(entries) + "\n").encode("utf-8"))

    def patch_paths(self):
        # Patch module constants for both history_lib AND the tools that
        # from-imported those constants at import time.
        from tools.history import write_snapshot as ws
        from tools.history import load_snapshot as ls
        from tools.history import rebuild_index as ri
        return _MultiPatch(
            [
                (history_lib, "HISTORY_PATH", self.history),
                (history_lib, "INDEX_PATH", self.index),
                (history_lib, "SNAPSHOTS_DIR", self.snaps),
                (ws, "HISTORY_PATH", self.history),
                (ws, "INDEX_PATH", self.index),
                (ws, "SNAPSHOTS_DIR", self.snaps),
                (ls, "SNAPSHOTS_DIR", self.snaps),
                (ri, "HISTORY_PATH", self.history),
                (ri, "INDEX_PATH", self.index),
            ]
        )


class _MultiPatch:
    """Context manager that patches multiple module attributes at once."""
    def __init__(self, targets):
        self.targets = targets
        self._original: list = []

    def __enter__(self):
        for mod, name, value in self.targets:
            self._original.append((mod, name, getattr(mod, name)))
            setattr(mod, name, value)
        return self

    def __exit__(self, *a):
        for mod, name, value in reversed(self._original):
            setattr(mod, name, value)


def sample_entry(id: int, *, status: str = "done", supersedes: str = "none", topics: str = "meta") -> str:
    return format_entry(
        id=id,
        date="2026-04-18T12:00:00Z",
        agent="claude-sonnet-4-6",
        status=status,
        topics=topics.split(","),
        commits="none",
        refs="none",
        supersedes=supersedes,
        tokens=10,
        body=f"Body of entry {id}.",
    )


class TestFormatAndParse(unittest.TestCase):
    def test_format_roundtrip(self):
        text = sample_entry(1)
        entries = parse_entries(text.encode("utf-8"))
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].id, 1)
        self.assertEqual(entries[0].status, "done")
        self.assertEqual(entries[0].topics, ["meta"])

    def test_parse_three_entries(self):
        combined = "\n\n".join(sample_entry(i) for i in (1, 2, 3)) + "\n"
        entries = parse_entries(combined.encode("utf-8"))
        self.assertEqual([e.id for e in entries], [1, 2, 3])

    def test_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            format_entry(
                id=1, date="2026-04-18T12:00:00Z", agent="a", status="invalid",
                topics=["x"], commits="none", refs="none", supersedes="none",
                tokens=1, body="b",
            )

    def test_ids_must_increase(self):
        text = sample_entry(2) + "\n\n" + sample_entry(1)
        with self.assertRaises(ValueError):
            parse_entries(text.encode("utf-8"))

    def test_marker_mismatch_raises(self):
        bad = "---BEGIN-ENTRY-#001---\nid: 001\n---\nbody\n---END-ENTRY-#002---\n"
        with self.assertRaises(ValueError):
            parse_entries(bad.encode("utf-8"))

    def test_hash_is_deterministic(self):
        text = sample_entry(1)
        entries = parse_entries(text.encode("utf-8"))
        self.assertEqual(entries[0].hash, compute_entry_hash(entries[0].raw))
        self.assertEqual(len(entries[0].hash), 64)

    def test_estimate_tokens(self):
        self.assertEqual(estimate_tokens("one two three four five"), 6)

    def test_next_entry_id(self):
        self.assertEqual(next_entry_id([]), 1)
        text = sample_entry(5)
        entries = parse_entries(text.encode("utf-8"))
        self.assertEqual(next_entry_id(entries), 6)


class TestSupersedesChain(unittest.TestCase):
    def test_simple_chain(self):
        text = sample_entry(1, status="planned") + "\n\n" + sample_entry(2, status="done", supersedes="001")
        entries = parse_entries(text.encode("utf-8"))
        rollup = resolve_supersedes_chain(entries)
        self.assertEqual(rollup[1][0], [1, 2])
        self.assertEqual(rollup[1][1], "done")

    def test_no_supersedes(self):
        text = sample_entry(1) + "\n\n" + sample_entry(2)
        entries = parse_entries(text.encode("utf-8"))
        rollup = resolve_supersedes_chain(entries)
        self.assertEqual(rollup[1][1], "done")
        self.assertEqual(rollup[2][1], "done")


class TestRebuildIndexIdempotent(TempRepoBase):
    def test_rebuild_twice_identical(self):
        self.write_entries([sample_entry(1), sample_entry(2), sample_entry(3)])
        with self.patch_paths():
            rebuild(self.history, self.index)
            first = self.index.read_text(encoding="utf-8")
            rebuild(self.history, self.index)
            second = self.index.read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertIn("total_entries: 3", first)
        self.assertIn("latest_id: 003", first)

    def test_empty_history(self):
        self.history.write_text("", encoding="utf-8")
        with self.patch_paths():
            rebuild(self.history, self.index)
        text = self.index.read_text(encoding="utf-8")
        self.assertIn("total_entries: 0", text)


class TestVerifyIntegrity(TempRepoBase):
    def test_verify_ok(self):
        self.write_entries([sample_entry(1), sample_entry(2)])
        with self.patch_paths():
            rebuild(self.history, self.index)
            ok, errs = verify(self.history, self.index)
        self.assertTrue(ok, f"Errors: {errs}")

    def test_verify_detects_tampering(self):
        self.write_entries([sample_entry(1), sample_entry(2)])
        with self.patch_paths():
            rebuild(self.history, self.index)
        # Tamper: modify body content (not a marker line)
        raw = self.history.read_bytes()
        tampered = raw.replace(b"Body of entry 1.", b"Body of entry X.")
        self.assertNotEqual(raw, tampered)
        self.history.write_bytes(tampered)
        with self.patch_paths():
            ok, errs = verify(self.history, self.index)
        self.assertFalse(ok)
        self.assertTrue(any("#001" in e for e in errs))


class TestSnapshots(TempRepoBase):
    def test_write_and_load_roundtrip(self):
        self.write_entries([sample_entry(1), sample_entry(2), sample_entry(3)])
        with self.patch_paths():
            rebuild(self.history, self.index)
            snap_path = write_snapshot(
                agent="claude-test",
                entry_ids=[1, 2, 3],
                token_budget=9999,
                snapshots_dir=self.snaps,
            )
            ok, payload, errs = load_and_verify(snap_path)
        self.assertTrue(ok, f"Errors: {errs}")
        self.assertEqual(len(payload["selected_entries"]), 3)
        self.assertIn("Body of entry 1.", payload["pack"])
        self.assertIn("Body of entry 3.", payload["pack"])

    def test_tampered_history_invalidates_snapshot(self):
        self.write_entries([sample_entry(1), sample_entry(2)])
        with self.patch_paths():
            rebuild(self.history, self.index)
            snap_path = write_snapshot(
                agent="claude-test",
                entry_ids=[1, 2],
                token_budget=9999,
                snapshots_dir=self.snaps,
            )
        # Tamper: corrupt entry #1 body by one byte
        raw = self.history.read_bytes()
        self.history.write_bytes(raw.replace(b"Body of entry 1.", b"Body of entry 9."))
        with self.patch_paths():
            ok, payload, errs = load_and_verify(snap_path)
        self.assertFalse(ok)
        self.assertTrue(any("#001" in e for e in errs))

    def test_tampered_snapshot_itself_detected(self):
        self.write_entries([sample_entry(1)])
        with self.patch_paths():
            rebuild(self.history, self.index)
            snap_path = write_snapshot(
                agent="claude-test",
                entry_ids=[1],
                token_budget=9999,
                snapshots_dir=self.snaps,
            )
        # Tamper the JSON payload
        data = json.loads(snap_path.read_text(encoding="utf-8"))
        data["agent"] = "claude-imposter"
        snap_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        with self.patch_paths():
            ok, _, errs = load_and_verify(snap_path)
        self.assertFalse(ok)
        self.assertTrue(any("integrity_hash" in e for e in errs))


class TestSurgicalRead(TempRepoBase):
    def test_byte_range_matches_hash(self):
        self.write_entries([sample_entry(1), sample_entry(2), sample_entry(3)])
        with self.patch_paths():
            rebuild(self.history, self.index)
        from tools.history.history_lib import parse_entries, read_history_bytes
        data = read_history_bytes(self.history)
        entries = parse_entries(data)
        # Pull entry #2 by byte range and verify it hashes the same
        target = entries[1]
        slice_bytes = data[target.byte_start : target.byte_end + 1]
        self.assertEqual(compute_entry_hash(slice_bytes), target.hash)


if __name__ == "__main__":
    unittest.main()
