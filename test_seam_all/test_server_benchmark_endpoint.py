from __future__ import annotations

import pytest

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - optional server extra
    TestClient = None  # type: ignore[assignment]


@pytest.mark.skipif(TestClient is None, reason="fastapi server extra is not installed")
def test_benchmark_endpoint_returns_400_for_value_error(monkeypatch) -> None:
    from seam_runtime.runtime import SeamRuntime
    from seam_runtime.server import create_app

    def raise_value_error(*args, **kwargs):
        raise ValueError("bad benchmark input")

    monkeypatch.setattr("seam_runtime.benchmarks.run_benchmark_suite", raise_value_error)

    client = TestClient(create_app(SeamRuntime(":memory:")))
    response = client.post("/benchmark", json={"suite": "all"})

    assert response.status_code == 400
    assert response.json()["detail"] == "bad benchmark input"
