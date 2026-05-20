from __future__ import annotations

import json
from pathlib import Path

from benchmarks.external.common.types import AdapterAnswer, ConversationTurn


class SeamLocomoAdapter:
    """SEAM memory system adapter for LoCoMo benchmarks.

    Implements the MemorySystemAdapter protocol. Each scope_id maps to a
    dedicated SQLite database under ``{db_root}/{scope_id}.db``, providing
    per-scope storage isolation.

    Lazy imports of ``seam_runtime`` modules avoid import-time side effects
    (such as embedding model initialisation) during test discovery.
    """

    name = "seam"

    def __init__(self, db_path: str | None = None, budget: int = 2000) -> None:
        # TODO: default db_path should be tmp_path, not a gitignored project dir
        self._db_root = Path(db_path) if db_path is not None else Path("test_seam/locomo")
        self.budget = budget

    # ------------------------------------------------------------------
    # Protocol methods
    # ------------------------------------------------------------------

    def reset(self, scope_id: str) -> None:
        """Drop the per-scope database file (and any WAL artefacts)."""
        db = self._db_path(scope_id)
        _remove_db_files(db)

    def ingest_turn(self, scope_id: str, turn: ConversationTurn) -> None:
        """Compile a conversation turn to MIRL and persist it in the
        scope's database."""
        from seam_runtime.runtime import SeamRuntime  # lazy

        text = _format_turn(turn)
        rt = _open_runtime(self._db_path(scope_id))
        rt.ingest_text(
            text=text,
            source_ref=f"locomo:{scope_id}:turn",
            ns=f"locomo:{scope_id}",
            scope="thread",
            persist=True,
        )

    def answer(self, scope_id: str, question: str) -> AdapterAnswer:
        """Search the scope's memory for relevant records, pack them, and
        return the packed text as retrieved context.

        No LLM calls are made; ``generated_answer`` is always ``None``.
        """
        import time as _time

        from seam_runtime.runtime import SeamRuntime  # lazy

        rt = _open_runtime(self._db_path(scope_id))
        t0 = _time.monotonic()
        result = rt.search_ir(question, scope="thread", budget=self.budget)
        retrieval_latency_ms = (_time.monotonic() - t0) * 1000.0

        record_ids = [candidate.record.id for candidate in result.candidates]

        if not record_ids:
            return AdapterAnswer(
                retrieved_context="",
                retrieval_latency_ms=retrieval_latency_ms,
            )

        pack = rt.pack_ir(record_ids, lens="general", budget=self.budget)
        pack_dict = pack.to_dict() if hasattr(pack, "to_dict") else {}
        retrieved_context = json.dumps(pack_dict, sort_keys=True, indent=2)
        return AdapterAnswer(
            retrieved_context=retrieved_context,
            retrieval_latency_ms=retrieval_latency_ms,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _db_path(self, scope_id: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in scope_id)
        return self._db_root / f"{safe}.db"


# ------------------------------------------------------------------
# Module-level helpers (avoid cluttering the class)
# ------------------------------------------------------------------

def _format_turn(turn: ConversationTurn) -> str:
    """Format a conversation turn into the canonical SEAM ingest string."""
    ts = turn.timestamp or ""
    return f"[{turn.speaker} {ts}] {turn.text}".strip()


def _open_runtime(db_path: Path):
    """Open (or reopen) a SeamRuntime for a per-scope SQLite database."""
    from seam_runtime.runtime import SeamRuntime  # lazy

    db_path.parent.mkdir(parents=True, exist_ok=True)
    return SeamRuntime(str(db_path))


def _remove_db_files(db_path: Path) -> None:
    """Remove a SQLite database file and any WAL / SHM sidecars."""
    if db_path.exists():
        db_path.unlink()
    for suffix in (".db-wal", ".db-shm"):
        sidecar = db_path.with_name(db_path.name + suffix)
        if sidecar.exists():
            sidecar.unlink()
