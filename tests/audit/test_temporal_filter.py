"""Tests for temporal-token detection and filtering."""

from seam_runtime.temporal import detect_temporal_tokens, parse_iso


def test_detect_temporal_tokens_month_year():
    tokens = detect_temporal_tokens("What did Alice say about Japan in April 2023?")
    assert len(tokens) >= 1, f"Expected at least one temporal token, got {tokens}"
    assert any("April 2023" in t for t in tokens), f"Expected 'April 2023' match, got {tokens}"


def test_detect_temporal_tokens_iso_date():
    tokens = detect_temporal_tokens("What happened on 2024-01-15?")
    assert len(tokens) >= 1, f"Expected at least one temporal token, got {tokens}"
    assert any("2024-01-15" in t for t in tokens), f"Expected '2024-01-15' match, got {tokens}"


def test_detect_temporal_tokens_none():
    tokens = detect_temporal_tokens("What is Alice's favorite color?")
    assert tokens == [], f"Expected no temporal tokens, got {tokens}"


def test_parse_iso_valid():
    dt = parse_iso("2024-01-15")
    assert dt is not None
    assert dt.month == 1
    assert dt.day == 15


def test_parse_iso_none():
    assert parse_iso(None) is None
    assert parse_iso("") is None


def test_temporal_window_ranks_in_window_higher(tmp_path):
    """Records with t0 inside the temporal window rank higher."""
    from datetime import datetime

    from seam_runtime.mirl import IRBatch, MIRLRecord, RecordKind
    from seam_runtime.retrieval import search_batch

    april = MIRLRecord(
        id="clm:april", kind=RecordKind.CLM,
        ns="test", scope="thread",
        t0="2024-04-15",
        attrs={"subject": "ent:1", "predicate": "test", "object": "April event"},
    )
    december = MIRLRecord(
        id="clm:december", kind=RecordKind.CLM,
        ns="test", scope="thread",
        t0="2024-12-15",
        attrs={"subject": "ent:2", "predicate": "test", "object": "December event"},
    )
    batch = IRBatch([april, december])

    window = (datetime(2024, 3, 1), datetime(2024, 5, 31))
    result = search_batch(batch, query="event", temporal_window=window, limit=2)
    assert len(result.candidates) >= 2
    # April should rank higher than December
    assert result.candidates[0].record.id == "clm:april", (
        f"April record should rank first with April window, got {result.candidates[0].record.id}"
    )
