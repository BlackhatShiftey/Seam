"""Tests for tools.history.retention — snapshot pruning logic."""

import datetime as _dt
import os
import tempfile
from pathlib import Path

from tools.history.retention import (
    _parse_snapshot_filename,
    compute_retention,
    run_retention,
)


def _make_index(dir: Path, latest_id: int = 1) -> Path:
    """Create a minimal fake HISTORY_INDEX.md."""
    content = f"""# History Index

total_entries: 1
latest_id: {latest_id}

## entries (newest first)

| id | date | status | hash | topics | supersedes |
|---|---|---|---|---|---|
| {latest_id:03d} | 2026-05-26 | done | abc123 | test | none |
"""
    p = dir / "HISTORY_INDEX.md"
    p.write_text(content)
    return p


def _list_snapshots_for_test(snapshots_dir: Path) -> list[dict]:
    from tools.history.retention import _list_snapshots
    return _list_snapshots(snapshots_dir)


def _make_snapshots_on_same_day(tmpdir: Path, date: str, count: int, *, hour_start: int = 0):
    """Create multiple snapshot files on the same calendar date."""
    for i in range(count):
        ts = _dt.datetime(
            int(date[:4]), int(date[4:6]), int(date[6:8]),
            hour_start + i, 0, 0, tzinfo=_dt.timezone.utc
        )
        date_str = ts.strftime("%Y%m%d")
        time_str = ts.strftime("%H%M%S")
        p = tmpdir / f"{date_str}-{time_str}-{i:06d}-agent.json"
        p.write_text("{}")
        os.utime(p, (ts.timestamp(), ts.timestamp()))


def test_parse_snapshot_filename_with_random():
    info = _parse_snapshot_filename("20260520-131937-315084-claude.json")
    assert info is not None
    assert info["date"] == "20260520"
    assert info["time"] == "131937"
    assert info["agent"] == "claude"


def test_parse_snapshot_filename_without_random():
    info = _parse_snapshot_filename("20260516-003011-claude-opus-4-7.json")
    assert info is not None
    assert info["date"] == "20260516"
    assert info["time"] == "003011"
    assert info["agent"] == "claude-opus-4-7"


def test_parse_snapshot_filename_invalid():
    assert _parse_snapshot_filename("not-a-snapshot.txt") is None
    assert _parse_snapshot_filename("20260520.json") is None


def test_retention_keeps_latest_n():
    """10 snapshots on one old day: keep=3 keeps only 3 (latest-per-day covers 1, latest-3 covers the same)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        _make_snapshots_on_same_day(tmpdir, "20260510", 10, hour_start=8)
        _make_index(tmpdir)

        keep_list, prune_list = compute_retention(
            _list_snapshots_for_test(tmpdir),
            keep=3,
            max_age_days=1,
            index_path=tmpdir / "HISTORY_INDEX.md",
        )

        assert len(keep_list) == 3
        assert len(prune_list) == 7


def test_retention_keeps_latest_per_day():
    """4 days x 3 snapshots each = 12 total. keep=1 + latest-per-day = 1 + 3 = 4 kept."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        for day_offset in range(4):
            day = 20 - day_offset
            _make_snapshots_on_same_day(tmpdir, f"202605{day:02d}", 3, hour_start=10)

        _make_index(tmpdir)

        keep_list, prune_list = compute_retention(
            _list_snapshots_for_test(tmpdir),
            keep=1,
            max_age_days=1,
            index_path=tmpdir / "HISTORY_INDEX.md",
        )

        assert len(keep_list) == 4
        assert len(prune_list) == 8


def test_retention_keeps_within_max_age():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        now = _dt.datetime.now(_dt.timezone.utc)

        for i in range(10):
            ts = now - _dt.timedelta(days=i)
            date_str = ts.strftime("%Y%m%d")
            time_str = ts.strftime("%H%M%S")
            p = tmpdir / f"{date_str}-{time_str}-{i:06d}-agent.json"
            p.write_text("{}")
            mtime = ts.timestamp()
            os.utime(p, (mtime, mtime))

        _make_index(tmpdir)

        keep_list, prune_list = compute_retention(
            _list_snapshots_for_test(tmpdir),
            keep=2,
            max_age_days=5,
            index_path=tmpdir / "HISTORY_INDEX.md",
        )

        for s in keep_list:
            age_days = (now.timestamp() - s["mtime"]) / 86400
            assert age_days <= 5 or s.get("keep_reason") in ("latest-2", "latest-per-day")


def test_run_retention_prune_deletes_files():
    """3 days x 3 snapshots = 9 total. keep=1 + latest-per-day(2 remaining days) = 3 kept, 6 pruned."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        for day_offset in range(3):
            day = 20 - day_offset
            _make_snapshots_on_same_day(tmpdir, f"202605{day:02d}", 3, hour_start=10)

        _make_index(tmpdir)

        result = run_retention(
            snapshots_dir=tmpdir,
            index_path=tmpdir / "HISTORY_INDEX.md",
            keep=1,
            max_age_days=1,
            prune=True,
        )

        assert result["pruned"] == 6
        assert result["kept"] == 3
        remaining = list(tmpdir.glob("*.json"))
        assert len(remaining) == 3


def test_run_retention_dry_run_does_not_delete():
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        for day_offset in range(3):
            day = 20 - day_offset
            _make_snapshots_on_same_day(tmpdir, f"202605{day:02d}", 3, hour_start=10)

        _make_index(tmpdir)

        result = run_retention(
            snapshots_dir=tmpdir,
            index_path=tmpdir / "HISTORY_INDEX.md",
            keep=1,
            max_age_days=1,
            prune=False,
        )

        assert result["pruned"] == 6
        remaining = list(tmpdir.glob("*.json"))
        assert len(remaining) == 9


def test_human_size():
    from tools.history.retention import _human_size
    assert _human_size(500) == "500 B"
    assert _human_size(1500) == "1.5 KB"
    assert _human_size(1_500_000) == "1.4 MB"


def test_multiple_snapshots_same_day_keeps_only_latest():
    """5 snapshots on one old day, keep=1: only the newest survives."""
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        base = _dt.datetime(2026, 5, 20, 12, 0, 0, tzinfo=_dt.timezone.utc)

        for i in range(5):
            ts = base + _dt.timedelta(hours=i)
            date_str = ts.strftime("%Y%m%d")
            time_str = ts.strftime("%H%M%S")
            p = tmpdir / f"{date_str}-{time_str}-{i:06d}-agent.json"
            p.write_text("{}")
            mtime = ts.timestamp()
            os.utime(p, (mtime, mtime))

        _make_index(tmpdir)

        keep_list, prune_list = compute_retention(
            _list_snapshots_for_test(tmpdir),
            keep=1,
            max_age_days=1,
            index_path=tmpdir / "HISTORY_INDEX.md",
        )

        assert len(keep_list) == 1
        assert len(prune_list) == 4
        assert keep_list[0]["time"] == "160000"
