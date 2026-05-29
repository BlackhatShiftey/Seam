"""Regression tests: LoCoMo benchmark results must always persist durably.

Prior behavior wrote results to a caller-chosen path (the SOPs used /tmp) and,
when no --output was given, only printed to stdout — so multi-hour runs were
lost. These tests lock in: (1) atomic+verified durable writes, (2) per-scope
checkpoints that survive an interrupted run, (3) a durable copy is always
written even without --output, into a non-/tmp location.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from benchmarks.external.locomo import run as locomo_run


class TestDurableWriteHelpers:
    def test_atomic_write_then_verify_roundtrip(self, tmp_path):
        target = tmp_path / "nested" / "result.json"
        payload = json.dumps({"a": 1, "b": [1, 2, 3]}) + "\n"
        locomo_run._atomic_write(target, payload)
        locomo_run._verify_saved(target, payload)  # must not raise
        assert target.read_text(encoding="utf-8") == payload
        # no temp residue
        assert not list(target.parent.glob("*.tmp"))

    def test_verify_saved_detects_corruption(self, tmp_path):
        target = tmp_path / "r.json"
        locomo_run._atomic_write(target, "real-content")
        with pytest.raises(RuntimeError):
            locomo_run._verify_saved(target, "different-expected-content")

    def test_verify_saved_detects_missing(self, tmp_path):
        with pytest.raises(RuntimeError):
            locomo_run._verify_saved(tmp_path / "missing.json", "x")

    def test_tmp_paths_flagged_ephemeral(self):
        assert locomo_run._is_ephemeral_path("/tmp/run.json")
        assert locomo_run._is_ephemeral_path("/var/tmp/run.json")
        # a repo-anchored path is NOT ephemeral
        repo_path = locomo_run.Path(__file__).resolve().parents[2] / "benchmarks" / "runs" / "x.json"
        assert not locomo_run._is_ephemeral_path(str(repo_path))

    def test_archive_dir_respects_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SEAM_BENCH_RESULTS_DIR", str(tmp_path / "custom"))
        assert locomo_run._resolve_archive_dir() == tmp_path / "custom"
        monkeypatch.delenv("SEAM_BENCH_RESULTS_DIR")
        # default is on persistent disk, never /tmp
        default = locomo_run._resolve_archive_dir()
        assert not locomo_run._is_ephemeral_path(str(default))


class TestGroupedRunnerCheckpoint:
    def test_checkpoint_fires_per_scope(self):
        from benchmarks.external.common.runner import run_benchmark_grouped
        from benchmarks.external.common.types import AdapterAnswer

        class FakeCase:
            def __init__(self, scope, q, conv):
                self.case_id = f"{scope}-{q}"
                self.question = q
                self.gold_answer = "x"
                self.category = 1
                self.conversation = conv

        conv = [{"speaker": "a", "text": "hi"}]
        cases = [FakeCase("s1", "q1", conv), FakeCase("s1", "q2", conv), FakeCase("s2", "q3", conv)]

        class FakeAdapter:
            name = "fake"
            def reset(self, scope): pass
            def ingest_turn(self, scope, turn): pass
            def answer(self, scope, q):
                return AdapterAnswer(retrieved_context="x")

        seen = []
        run_benchmark_grouped(
            adapter=FakeAdapter(),
            cases=cases,
            scope_id=lambda c: c.case_id.split("-")[0],
            checkpoint=lambda results, done, total: seen.append((len(results), done, total)),
        )
        # one checkpoint per scope (s1 with 2 cases, s2 with 1)
        assert seen == [(2, 2, 3), (3, 3, 3)]

    def test_parallel_checkpoint_fires(self):
        from benchmarks.external.common.runner import run_benchmark_grouped_parallel
        from benchmarks.external.common.types import AdapterAnswer

        class FakeCase:
            def __init__(self, scope, q, conv):
                self.case_id = f"{scope}-{q}"
                self.question = q
                self.gold_answer = "x"
                self.category = 1
                self.conversation = conv

        conv = [{"speaker": "a", "text": "hi"}]
        cases = [FakeCase("s1", "q1", conv), FakeCase("s2", "q2", conv), FakeCase("s3", "q3", conv)]

        class FakeAdapter:
            name = "fake"
            def reset(self, scope): pass
            def ingest_turn(self, scope, turn): pass
            def answer(self, scope, q):
                return AdapterAnswer(retrieved_context="x")

        seen = []
        run_benchmark_grouped_parallel(
            adapter_factory=FakeAdapter,
            adapter_name="fake",
            cases=cases,
            scope_id=lambda c: c.case_id.split("-")[0],
            workers=2,
            checkpoint=lambda results, done, total: seen.append((len(results), done, total)),
        )
        # 3 scopes -> 3 checkpoints; final one sees all 3 results (order of
        # completion is nondeterministic, so assert counts not exact tuples)
        assert len(seen) == 3
        assert seen[-1] == (3, 3, 3)
        assert [s[1] for s in seen] == [1, 2, 3]  # monotonic completed count


class TestQuickstartArchives:
    def test_quickstart_writes_durable_copy_without_output(self, tmp_path):
        env = dict(os.environ)
        env["SEAM_BENCH_RESULTS_DIR"] = str(tmp_path / "results")
        env.pop("SEAM_PGVECTOR_DSN", None)  # force chromadb default
        proc = subprocess.run(
            [sys.executable, "-m", "benchmarks.external.locomo.run",
             "--quickstart", "--adapter", "seam", "--judge", "stub"],
            capture_output=True, text=True, env=env, timeout=300,
        )
        assert proc.returncode == 0, proc.stderr
        # stdout is still pure JSON (archive messages go to stderr)
        json.loads(proc.stdout)
        results_dir = tmp_path / "results"
        finals = list(results_dir.glob("*.json"))
        assert len(finals) == 1, f"expected one durable bundle, got {finals}"
        assert not list(results_dir.glob("*.partial.json")), "partial must be removed on success"
        assert not list(results_dir.glob("*.tmp")), "no temp residue"
        bundle = json.loads(finals[0].read_text(encoding="utf-8"))
        assert bundle.get("cases") and bundle.get("scores")
        assert "Durable copy archived (verified)" in proc.stderr
