"""Regression tests for ConnectionPool reset-on-return (audit P1).

SQLite connections use implicit transactions (isolation_level=""). A
multi-statement write that raises after the first statement but before
commit() leaves an open transaction on the connection. Before the
reset-on-return fix, the pool returned that connection unchanged, so the
next caller's commit() silently persisted the orphaned rows — contaminating
the canonical store (including append-only audit tables).

These tests reproduce that contamination scenario and assert the pool now
discards uncommitted state on return.
"""
from __future__ import annotations

import sqlite3

from seam_runtime.pool import ConnectionPool


def _bootstrap(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("create table t (id integer primary key, v text not null)")
    conn.commit()
    conn.close()


def test_failed_write_does_not_contaminate_next_caller(tmp_path):
    db = str(tmp_path / "poc.db")
    _bootstrap(db)
    pool = ConnectionPool(lambda: sqlite3.connect(db), pool_size=1)

    # Caller A: multi-statement write that raises before commit().
    try:
        with pool.checkout() as conn:
            conn.execute("insert into t (id, v) values (1, 'phantom_from_A')")
            conn.execute("insert into t (id, v) values (2, NULL)")  # NOT NULL -> raises
            conn.commit()
    except sqlite3.IntegrityError:
        pass

    # Caller B: unrelated successful write reusing the SAME pooled connection.
    with pool.checkout() as conn:
        conn.execute("insert into t (id, v) values (3, 'legit_from_B')")
        conn.commit()

    verify = sqlite3.connect(db)
    rows = verify.execute("select id from t order by id").fetchall()
    verify.close()
    pool.close()

    ids = [r[0] for r in rows]
    assert 1 not in ids, f"phantom row from failed Caller A leaked into commit: {rows}"
    assert ids == [3], f"only Caller B's legit row should persist, got {rows}"


def test_uncommitted_write_without_exception_is_discarded(tmp_path):
    db = str(tmp_path / "poc2.db")
    _bootstrap(db)
    pool = ConnectionPool(lambda: sqlite3.connect(db), pool_size=1)

    # Caller leaves an open transaction (no commit, no exception).
    with pool.checkout() as conn:
        conn.execute("insert into t (id, v) values (1, 'never_committed')")

    # Reuse the connection; do nothing that commits the leaked row.
    with pool.checkout() as conn:
        conn.execute("select 1")

    verify = sqlite3.connect(db)
    count = verify.execute("select count(*) from t").fetchone()[0]
    verify.close()
    pool.close()

    assert count == 0, "uncommitted write must be rolled back on connection return"
