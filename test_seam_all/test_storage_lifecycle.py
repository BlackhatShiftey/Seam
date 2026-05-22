from __future__ import annotations

import sqlite3

import pytest

from seam_runtime.storage import SQLiteStore


def test_memory_store_close_closes_anchor_connection() -> None:
    store = SQLiteStore(":memory:")
    anchor = store._mem_anchor  # type: ignore[attr-defined]

    store.close()

    with pytest.raises(sqlite3.ProgrammingError):
        anchor.execute("select 1")


def test_memory_store_context_manager_closes_anchor_connection() -> None:
    with SQLiteStore(":memory:") as store:
        anchor = store._mem_anchor  # type: ignore[attr-defined]

    with pytest.raises(sqlite3.ProgrammingError):
        anchor.execute("select 1")
