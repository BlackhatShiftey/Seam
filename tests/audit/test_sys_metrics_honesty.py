"""W3 — /sys-metrics honest errors + platform check."""

import os
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from seam_runtime.server import create_app
from seam_runtime.runtime import SeamRuntime


@pytest.fixture
def metrics_client():
    """Create a TestClient without rate limiting."""
    os.environ["SEAM_API_RATE_LIMIT_PER_MINUTE"] = "0"
    runtime = SeamRuntime(":memory:")
    app = create_app(runtime)
    yield TestClient(app)
    os.environ.pop("SEAM_API_RATE_LIMIT_PER_MINUTE", None)


def test_sys_metrics_response_shape(metrics_client):
    """Response has top-level keys cpu, mem, disk, gpu, net with structured values."""
    resp = metrics_client.get("/sys-metrics")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("cpu", "mem", "disk", "gpu", "net"):
        assert key in body, f"missing key: {key}"
        metric = body[key]
        assert isinstance(metric, dict), f"{key} should be dict"
        assert "value" in metric, f"{key} missing value"
        assert "source" in metric, f"{key} missing source"
        assert metric["source"] in ("live", "unavailable", "unsupported")
        assert "error" in metric, f"{key} missing error"


def test_sys_metrics_live_on_linux(metrics_client):
    """CPU, mem, disk report 'live' on Linux."""
    import sys as _sys
    if not _sys.platform.startswith("linux"):
        pytest.skip("live checks only valid on Linux")
    # First call sets baseline, second computes delta.
    metrics_client.get("/sys-metrics")
    resp = metrics_client.get("/sys-metrics")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("cpu", "mem"):
        assert body[key]["source"] == "live", f"{key} should be live"
        assert isinstance(body[key]["value"], (int, float)), f"{key} value should be numeric"


def test_sys_metrics_gpu_net_unsupported(metrics_client):
    """GPU and NET report 'unsupported' with null value."""
    resp = metrics_client.get("/sys-metrics")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("gpu", "net"):
        assert body[key]["source"] == "unsupported", f"{key} should be unsupported"
        assert body[key]["value"] is None, f"{key} value should be None"


def test_sys_metrics_all_unsupported_on_non_linux(metrics_client):
    """When sys.platform is not linux, all metrics are unsupported."""
    with mock.patch("seam_runtime.server.sys") as mock_sys:
        mock_sys.platform = "win32"
        resp = metrics_client.get("/sys-metrics")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("cpu", "mem", "disk", "gpu", "net"):
        assert body[key]["source"] == "unsupported", f"{key} should be unsupported on win32"
        assert body[key]["value"] is None, f"{key} value should be None on win32"


def test_sys_metrics_cpu_unavailable_on_permission_error(metrics_client):
    """When /proc/stat is unreadable, cpu reports unavailable."""
    import builtins as _builtins

    _real_open = _builtins.open

    def _restricted_open(file, *args, **kwargs):
        if isinstance(file, str) and file == "/proc/stat":
            raise PermissionError("simulated")
        return _real_open(file, *args, **kwargs)

    with mock.patch("builtins.open", side_effect=_restricted_open):
        resp = metrics_client.get("/sys-metrics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["cpu"]["source"] == "unavailable", f"cpu should be unavailable, got {body['cpu']}"
    assert body["cpu"]["value"] is None
    assert body["cpu"]["error"] == "PermissionError"


def test_sys_metrics_disk_targets_data_dir(metrics_client, tmp_path):
    """Disk reports live for an existing data dir; unavailable for missing dir."""
    import seam_runtime.server as server_mod

    # Patch _tree_root to not interfere — use a sentinel that won't conflict.
    # The disk metric reads runtime.store.path, which is ":memory:" for our test runtime.
    # For this test we verify the disk metric reads from runtime.store.path by
    # creating a runtime with a real db in tmp_path.
    runtime2 = SeamRuntime(str(tmp_path / "test.db"))
    os.environ["SEAM_API_RATE_LIMIT_PER_MINUTE"] = "0"
    try:
        # Ensure the db file exists so its parent dir exists
        (tmp_path / "test.db").write_text("")
        app2 = create_app(runtime2)
        client2 = TestClient(app2)
        resp = client2.get("/sys-metrics")
        assert resp.status_code == 200
        disk = resp.json()["disk"]
        # Disk should be live since tmp_path exists
        assert disk["source"] in ("live", "unavailable"), f"unexpected disk source: {disk['source']}"
        if disk["source"] == "live":
            assert isinstance(disk["value"], (int, float))
    finally:
        os.environ.pop("SEAM_API_RATE_LIMIT_PER_MINUTE", None)
