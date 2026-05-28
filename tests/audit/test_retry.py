"""Tests for seam_runtime.retry decorator module."""
from __future__ import annotations

import asyncio
import sqlite3
from unittest.mock import patch

import pytest

from seam_runtime.retry import (
    retry,
    retry_db_operation,
    retry_network_operation,
)


class TestRetrySuccessOnFirstTry:
    def test_sync_returns_value(self):
        @retry(max_attempts=3, base_delay=0.001)
        def ok():
            return 42

        assert ok() == 42

    def test_async_returns_value(self):
        @retry(max_attempts=3, base_delay=0.001)
        async def ok():
            return 99

        assert asyncio.run(ok()) == 99

    def test_no_sleep_on_success(self):
        @retry(max_attempts=3, base_delay=1.0)
        def ok():
            return "done"

        with patch("seam_runtime.retry.time.sleep") as mock_sleep:
            assert ok() == "done"
            mock_sleep.assert_not_called()


class TestRetryOnTransientFailure:
    def test_retries_then_succeeds(self):
        calls = {"n": 0}

        @retry(max_attempts=3, base_delay=0.001, exceptions=(ValueError,))
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ValueError("transient")
            return "ok"

        assert flaky() == "ok"
        assert calls["n"] == 3

    def test_async_retries_then_succeeds(self):
        calls = {"n": 0}

        @retry(max_attempts=3, base_delay=0.001, exceptions=(ValueError,))
        async def flaky():
            calls["n"] += 1
            if calls["n"] < 2:
                raise ValueError("transient")
            return "ok"

        assert asyncio.run(flaky()) == "ok"
        assert calls["n"] == 2

    def test_on_retry_callback_invoked(self):
        log: list[tuple[int, type, float]] = []

        def cb(attempt, exc, delay):
            log.append((attempt, type(exc), delay))

        calls = {"n": 0}

        @retry(
            max_attempts=3,
            base_delay=0.001,
            exceptions=(RuntimeError,),
            on_retry=cb,
        )
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("boom")
            return "ok"

        flaky()
        assert len(log) == 2
        assert log[0][0] == 1
        assert log[1][0] == 2
        assert all(entry[1] is RuntimeError for entry in log)


class TestMaxAttemptsExceeded:
    def test_raises_after_max(self):
        @retry(max_attempts=2, base_delay=0.001, exceptions=(ValueError,))
        def always_fail():
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            always_fail()

    def test_async_raises_after_max(self):
        @retry(max_attempts=2, base_delay=0.001, exceptions=(ValueError,))
        async def always_fail():
            raise ValueError("permanent")

        with pytest.raises(ValueError, match="permanent"):
            asyncio.run(always_fail())

    def test_call_count_equals_max_attempts(self):
        calls = {"n": 0}

        @retry(max_attempts=4, base_delay=0.001, exceptions=(ValueError,))
        def always_fail():
            calls["n"] += 1
            raise ValueError("fail")

        with pytest.raises(ValueError):
            always_fail()
        assert calls["n"] == 4


class TestBackoffStrategies:
    def test_exponential_delays(self):
        delays: list[float] = []

        def cb(attempt, exc, delay):
            delays.append(delay)

        calls = {"n": 0}

        @retry(
            max_attempts=4,
            backoff="exponential",
            base_delay=0.1,
            max_delay=10.0,
            exceptions=(ValueError,),
            on_retry=cb,
        )
        def flaky():
            calls["n"] += 1
            if calls["n"] < 4:
                raise ValueError("x")
            return "ok"

        flaky()
        assert delays == pytest.approx([0.1, 0.2, 0.4])

    def test_linear_delays(self):
        delays: list[float] = []

        def cb(attempt, exc, delay):
            delays.append(delay)

        calls = {"n": 0}

        @retry(
            max_attempts=4,
            backoff="linear",
            base_delay=0.1,
            max_delay=10.0,
            exceptions=(ValueError,),
            on_retry=cb,
        )
        def flaky():
            calls["n"] += 1
            if calls["n"] < 4:
                raise ValueError("x")
            return "ok"

        flaky()
        assert delays == pytest.approx([0.1, 0.2, 0.3])

    def test_fixed_delays(self):
        delays: list[float] = []

        def cb(attempt, exc, delay):
            delays.append(delay)

        calls = {"n": 0}

        @retry(
            max_attempts=4,
            backoff="fixed",
            base_delay=0.5,
            max_delay=10.0,
            exceptions=(ValueError,),
            on_retry=cb,
        )
        def flaky():
            calls["n"] += 1
            if calls["n"] < 4:
                raise ValueError("x")
            return "ok"

        flaky()
        assert delays == pytest.approx([0.5, 0.5, 0.5])

    def test_max_delay_cap(self):
        delays: list[float] = []

        def cb(attempt, exc, delay):
            delays.append(delay)

        calls = {"n": 0}

        @retry(
            max_attempts=3,
            backoff="exponential",
            base_delay=10.0,
            max_delay=1.0,
            exceptions=(ValueError,),
            on_retry=cb,
        )
        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ValueError("x")
            return "ok"

        flaky()
        assert all(d <= 1.0 for d in delays)

    def test_invalid_backoff_raises(self):
        @retry(max_attempts=2, backoff="bogus", exceptions=(ValueError,))
        def fail():
            raise ValueError("x")

        with pytest.raises(ValueError, match="unknown backoff"):
            fail()


class TestExceptionFiltering:
    def test_unmatched_exception_propagates(self):
        @retry(max_attempts=3, base_delay=0.001, exceptions=(ValueError,))
        def wrong_type():
            raise TypeError("not retried")

        with pytest.raises(TypeError, match="not retried"):
            wrong_type()

    def test_default_exceptions_include_sqlite(self):
        calls = {"n": 0}

        @retry(max_attempts=2, base_delay=0.001)
        def db_fail():
            calls["n"] += 1
            raise sqlite3.OperationalError("database is locked")

        with pytest.raises(sqlite3.OperationalError):
            db_fail()
        assert calls["n"] == 2

    def test_default_exceptions_include_connection(self):
        calls = {"n": 0}

        @retry(max_attempts=2, base_delay=0.001)
        def net_fail():
            calls["n"] += 1
            raise ConnectionError("refused")

        with pytest.raises(ConnectionError):
            net_fail()
        assert calls["n"] == 2

    def test_exception_check_predicate(self):
        calls = {"n": 0}

        @retry(
            max_attempts=3,
            base_delay=0.001,
            exceptions=(ValueError,),
            exception_check=lambda e: "retry" in str(e),
        )
        def selective():
            calls["n"] += 1
            if calls["n"] == 1:
                raise ValueError("retry this")
            if calls["n"] == 2:
                raise ValueError("nope")
            return "ok"

        with pytest.raises(ValueError, match="nope"):
            selective()
        assert calls["n"] == 2


class TestRetryDbOperation:
    def test_retries_database_locked(self):
        calls = {"n": 0}

        @retry_db_operation(max_attempts=3, base_delay=0.001)
        def locked():
            calls["n"] += 1
            if calls["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        assert locked() == "ok"
        assert calls["n"] == 3

    def test_retries_cannot_commit(self):
        calls = {"n": 0}

        @retry_db_operation(max_attempts=3, base_delay=0.001)
        def commit_fail():
            calls["n"] += 1
            if calls["n"] < 2:
                raise sqlite3.OperationalError("cannot commit - no transaction is active")
            return "ok"

        assert commit_fail() == "ok"
        assert calls["n"] == 2

    def test_non_transient_db_error_propagates(self):
        @retry_db_operation(max_attempts=3, base_delay=0.001)
        def other_error():
            raise sqlite3.OperationalError("no such table: foo")

        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            other_error()


class TestRetryNetworkOperation:
    def test_retries_connection_error(self):
        calls = {"n": 0}

        @retry_network_operation(max_attempts=3, base_delay=0.001)
        def connect():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("refused")
            return "connected"

        assert connect() == "connected"
        assert calls["n"] == 3

    def test_retries_timeout_error(self):
        calls = {"n": 0}

        @retry_network_operation(max_attempts=2, base_delay=0.001)
        def timeout():
            calls["n"] += 1
            if calls["n"] < 2:
                raise TimeoutError("timed out")
            return "ok"

        assert timeout() == "ok"

    def test_retries_os_error(self):
        calls = {"n": 0}

        @retry_network_operation(max_attempts=2, base_delay=0.001)
        def net():
            calls["n"] += 1
            if calls["n"] < 2:
                raise OSError("Network is unreachable")
            return "ok"

        assert net() == "ok"

    def test_non_network_error_propagates(self):
        @retry_network_operation(max_attempts=3, base_delay=0.001)
        def wrong():
            raise ValueError("not network")

        with pytest.raises(ValueError, match="not network"):
            wrong()


class TestAsyncRetry:
    def test_async_uses_asyncio_sleep(self):
        calls = {"n": 0}

        @retry(max_attempts=3, base_delay=0.001, exceptions=(ValueError,))
        async def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise ValueError("x")
            return "ok"

        async def _noop(*a, **kw):
            pass

        with patch("seam_runtime.retry.asyncio.sleep", side_effect=_noop) as mock_sleep:
            result = asyncio.run(flaky())

        assert result == "ok"
        assert mock_sleep.call_count == 2

    def test_async_network_retry(self):
        calls = {"n": 0}

        @retry_network_operation(max_attempts=2, base_delay=0.001)
        async def fetch():
            calls["n"] += 1
            if calls["n"] < 2:
                raise ConnectionError("refused")
            return "data"

        assert asyncio.run(fetch()) == "data"
        assert calls["n"] == 2
