"""Shared pytest fixtures for the SEAM test suite.

Ambient ``SEAM_PGVECTOR_DSN`` isolation: an operator shell that exports the
pgvector DSN (the documented local dev setup) otherwise leaks into every
persist-path test, which then routes to the optional Docker pgvector backend
and fails with a raw ``connection refused`` when that container is down. Tests
that genuinely exercise the real adapter opt in with ``@pytest.mark.external``
and self-gate via ``skipif``; everything else must run on the default SQLite
vector backend so local runs are deterministic and match CI (which sets no DSN).
"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_ambient_pgvector_dsn(request, monkeypatch):
    """Route non-``external`` tests to SQLite by hiding any ambient pgvector DSN."""
    if request.node.get_closest_marker("external") is None:
        monkeypatch.delenv("SEAM_PGVECTOR_DSN", raising=False)
