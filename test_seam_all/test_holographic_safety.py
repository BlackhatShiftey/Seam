from __future__ import annotations

import pytest

from seam_runtime.holographic import DEFAULT_MAX_SURFACE_PAYLOAD_BYTES, _max_surface_payload_bytes, encode_surface


def test_encode_surface_rejects_payload_above_configured_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SEAM_SURFACE_MAX_PAYLOAD_BYTES", "4")

    with pytest.raises(ValueError, match="payload exceeds"):
        encode_surface(b"12345", tmp_path / "too-large.seam.png")


def test_encode_surface_allows_payload_at_configured_limit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SEAM_SURFACE_MAX_PAYLOAD_BYTES", "4")

    artifact = encode_surface(b"1234", tmp_path / "ok.seam.png")

    assert artifact.payload_bytes == 4


def test_payload_limit_default_is_64mb(monkeypatch) -> None:
    monkeypatch.delenv("SEAM_SURFACE_MAX_PAYLOAD_BYTES", raising=False)
    assert _max_surface_payload_bytes() == DEFAULT_MAX_SURFACE_PAYLOAD_BYTES


def test_payload_limit_zero_disables_check(monkeypatch) -> None:
    monkeypatch.setenv("SEAM_SURFACE_MAX_PAYLOAD_BYTES", "0")
    assert _max_surface_payload_bytes() == 0


def test_payload_limit_whitespace_only_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("SEAM_SURFACE_MAX_PAYLOAD_BYTES", "   ")
    assert _max_surface_payload_bytes() == DEFAULT_MAX_SURFACE_PAYLOAD_BYTES


def test_payload_limit_rejects_non_integer(monkeypatch) -> None:
    monkeypatch.setenv("SEAM_SURFACE_MAX_PAYLOAD_BYTES", "twelve")
    with pytest.raises(ValueError, match="must be an integer"):
        _max_surface_payload_bytes()


def test_payload_limit_rejects_negative(monkeypatch) -> None:
    monkeypatch.setenv("SEAM_SURFACE_MAX_PAYLOAD_BYTES", "-1")
    with pytest.raises(ValueError, match="must be non-negative"):
        _max_surface_payload_bytes()


def test_bw1_capacity_bytes_reported_in_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SEAM_SURFACE_MAX_PAYLOAD_BYTES", "1048576")
    artifact = encode_surface(b"hello bw1", tmp_path / "cap.seam.png", mode="bw1")
    assert artifact.capacity_bytes > 0
    assert artifact.mode == "bw1"
    assert artifact.capacity_used_ratio > 0.0


def test_rgb24_capacity_bytes_reported_in_artifact(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SEAM_SURFACE_MAX_PAYLOAD_BYTES", "1048576")
    artifact = encode_surface(b"hello rgb", tmp_path / "cap.seam.png", mode="rgb24")
    assert artifact.capacity_bytes > 0
    assert artifact.mode == "rgb24"
    assert artifact.capacity_used_ratio > 0.0
