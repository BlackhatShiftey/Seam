"""H1 — write_log durability via fsync."""

import os
from pathlib import Path
from unittest import mock

import pytest

from tools.streams.streams_lib import write_log


def test_write_log_fsyncs_file_and_directory():
    """write_log calls os.fsync on the written file AND its parent directory."""
    with mock.patch("tools.streams.streams_lib.os.open", wraps=os.open) as spy_open, \
         mock.patch("tools.streams.streams_lib.os.fsync") as spy_fsync, \
         mock.patch("tools.streams.streams_lib.log_path") as mock_log_path:

        mock_log_path.return_value = Path(os.environ.get("TMPDIR", "/tmp")) / "test_streams_fsync" / "log.md"

        write_log("test_kind", b"hello fsync test")

        assert spy_fsync.call_count >= 2, f"expected >= 2 fsync calls, got {spy_fsync.call_count}"
        assert spy_open.call_count >= 2, f"expected >= 2 open calls, got {spy_open.call_count}"


def test_write_log_fsync_file_called_in_finally():
    """os.close is called even if fsync fails. The write completes under lock."""
    with mock.patch("tools.streams.streams_lib.os.fsync") as spy_fsync, \
         mock.patch("tools.streams.streams_lib.os.close", wraps=os.close) as spy_close, \
         mock.patch("tools.streams.streams_lib.log_path") as mock_log_path:

        mock_log_path.return_value = Path(os.environ.get("TMPDIR", "/tmp")) / "test_streams_fsync2" / "log.md"
        spy_fsync.side_effect = OSError("simulated fsync failure")

        # File fsync fails (not caught), but fd is closed in finally
        with pytest.raises(OSError):
            write_log("test_kind", b"data")

        assert spy_close.call_count >= 1, f"expected >= 1 close call (file fd), got {spy_close.call_count}"
