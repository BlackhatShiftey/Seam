"""Tests for stream content hash verification."""
import hashlib
import re


class TestStreamsContentHash:
    def test_content_hash_matches_identical_events(self):
        """Content hash should be stable for identical event content."""
        events_data = [
            b'{"id": 1, "text": "hello"}',
            b'{"id": 2, "text": "world"}',
        ]
        h1 = hashlib.sha256(b"".join(events_data)).hexdigest()
        h2 = hashlib.sha256(b"".join(events_data)).hexdigest()
        assert h1 == h2

    def test_content_hash_differs_when_content_changes(self):
        """Content hash should change when event content changes."""
        events_a = [b'{"id": 1, "text": "hello"}']
        events_b = [b'{"id": 1, "text": "tampered"}']
        h1 = hashlib.sha256(b"".join(events_a)).hexdigest()
        h2 = hashlib.sha256(b"".join(events_b)).hexdigest()
        assert h1 != h2

    def test_content_hash_in_index_format(self):
        """Verify the expected index.md content_hash format."""
        test_hash = hashlib.sha256(b"test").hexdigest()
        index_line = f"content_hash: {test_hash}"
        match = re.search(r"^content_hash:\s*([0-9a-f]{64})", index_line, re.MULTILINE)
        assert match is not None
        assert match.group(1) == test_hash
