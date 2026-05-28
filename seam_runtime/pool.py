"""SQLite connection pool (connection reuse pattern).

Note: SQLite doesn't support true connection pooling like PostgreSQL.
This is a connection reuse pattern that maintains N reusable connections
in a queue. For high-concurrency workloads, migrate to PostgreSQL.
"""
from __future__ import annotations

import logging
import queue
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Callable

LOGGER = logging.getLogger(__name__)


class ConnectionPool:
    def __init__(
        self,
        connect_factory: Callable[[], sqlite3.Connection],
        pool_size: int = 5,
        idle_timeout: int = 300,
        checkout_timeout: int = 5,
    ) -> None:
        self._connect_factory = connect_factory
        self.pool_size = pool_size
        self.idle_timeout = idle_timeout
        self.checkout_timeout = checkout_timeout
        self._lock = threading.Lock()
        self._pool: queue.Queue[tuple[sqlite3.Connection, float]] = queue.Queue(maxsize=pool_size)
        self._active_count = 0
        self._closed = False

    def _validate_connection(self, connection: sqlite3.Connection) -> bool:
        try:
            connection.execute("select 1")
            return True
        except Exception:
            LOGGER.warning("Connection validation failed, will recreate")
            return False

    def _close_connection(self, connection: sqlite3.Connection) -> None:
        try:
            connection.close()
        except Exception:
            LOGGER.warning("Error closing connection", exc_info=True)

    @contextmanager
    def checkout(self):
        if self._closed:
            raise RuntimeError("ConnectionPool is closed")

        connection = None

        with self._lock:
            while not self._pool.empty():
                try:
                    conn, last_used = self._pool.get_nowait()
                    idle_time = time.time() - last_used

                    if idle_time > self.idle_timeout:
                        LOGGER.debug("Closing idle connection (idle %.1fs)", idle_time)
                        self._close_connection(conn)
                        self._active_count -= 1
                        continue

                    if not self._validate_connection(conn):
                        self._close_connection(conn)
                        self._active_count -= 1
                        continue

                    connection = conn
                    break
                except queue.Empty:
                    break

            if connection is None and self._active_count < self.pool_size:
                connection = self._connect_factory()
                self._active_count += 1

        if connection is None:
            try:
                conn, _ = self._pool.get(timeout=self.checkout_timeout)
                connection = conn
            except queue.Empty:
                raise TimeoutError(
                    f"Could not acquire connection within {self.checkout_timeout}s "
                    f"(pool_size={self.pool_size}, active={self._active_count})"
                )

        try:
            yield connection
        finally:
            with self._lock:
                if not self._closed:
                    try:
                        self._pool.put_nowait((connection, time.time()))
                    except queue.Full:
                        LOGGER.warning("Pool is full, closing excess connection")
                        self._close_connection(connection)
                        self._active_count -= 1
                else:
                    self._close_connection(connection)
                    self._active_count -= 1

    def close(self) -> None:
        with self._lock:
            self._closed = True
            while not self._pool.empty():
                try:
                    conn, _ = self._pool.get_nowait()
                    self._close_connection(conn)
                    self._active_count -= 1
                except queue.Empty:
                    break

    def stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "pool_size": self.pool_size,
                "active_connections": self._active_count,
                "idle_connections": self._pool.qsize(),
                "closed": self._closed,
            }
