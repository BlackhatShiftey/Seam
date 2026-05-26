"""P3 Fix 9 — MCP artifact_path containment check."""
from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

from seam_runtime.mcp import _resolve_registered_surface_path
from seam_runtime.runtime import SeamRuntime


def _make_mock_runtime(db_dir: Path):
    runtime = SeamRuntime(str(db_dir / "test.db"))
    return runtime


def test_allowed_path_under_store_dir(tmp_path: Path) -> None:
    runtime = _make_mock_runtime(tmp_path)
    artifact = tmp_path / "surfaces" / "test.seam.png"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.touch()

    mock_row = {"artifact_path": str(artifact)}
    with mock.patch.object(runtime.store, "read_surface_artifact", return_value=mock_row):
        result = _resolve_registered_surface_path(runtime, "hs:abcd1234")
        assert result == artifact


def test_path_outside_store_dir_raises(tmp_path: Path) -> None:
    runtime = _make_mock_runtime(tmp_path)
    outside = tmp_path / ".." / "outside.txt"
    # Resolve to get an absolute path outside tmp_path
    resolved_outside = outside.resolve()
    resolved_outside.parent.mkdir(parents=True, exist_ok=True)
    resolved_outside.touch()

    mock_row = {"artifact_path": str(resolved_outside)}
    with mock.patch.object(runtime.store, "read_surface_artifact", return_value=mock_row):
        with pytest.raises(PermissionError, match="outside the allowed root"):
            _resolve_registered_surface_path(runtime, "hs:abcd1234")


def test_env_override_restores_permissive_behavior(tmp_path: Path) -> None:
    runtime = _make_mock_runtime(tmp_path)
    outside = tmp_path / ".." / "outside2.txt"
    resolved_outside = outside.resolve()
    resolved_outside.parent.mkdir(parents=True, exist_ok=True)
    resolved_outside.touch()

    mock_row = {"artifact_path": str(resolved_outside)}
    with mock.patch.dict(os.environ, {"SEAM_SURFACE_ROOT": str(resolved_outside.parent)}):
        with mock.patch.object(runtime.store, "read_surface_artifact", return_value=mock_row):
            result = _resolve_registered_surface_path(runtime, "hs:abcd1234")
            assert result == resolved_outside
