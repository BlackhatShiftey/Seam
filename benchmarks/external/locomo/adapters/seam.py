from __future__ import annotations

import hashlib
import json
import os
import time as _time
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

    def __init__(
        self,
        db_path: str | None = None,
        budget: int = 2000,
        include_evidence_closure: bool = True,
        answerer: str | None = None,
        answerer_model: str | None = None,
    ) -> None:
        # TODO: default db_path should be tmp_path, not a gitignored project dir
        self._db_root = Path(db_path) if db_path is not None else Path("test_seam/locomo")
        self.budget = budget
        self.include_evidence_closure = include_evidence_closure
        self._answerer = answerer
        self._answerer_model = answerer_model

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
        turn_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        rt = _open_runtime(self._db_path(scope_id))
        rt.ingest_conversation_turn(
            text=text,
            source_ref=f"locomo:{scope_id}:turn:{turn_hash}",
            ns=f"locomo:{scope_id}",
            scope="thread",
            persist=True,
        )

    def answer(self, scope_id: str, question: str) -> AdapterAnswer:
        """Search the scope's memory and return source evidence text.

        Standard LoCoMo scoring uses token overlap against retrieved context.
        The default context pack is useful for SEAM graph inspection but elides
        natural-language evidence into symbolic records, so this adapter follows
        evidence/provenance and SPAN-to-RAW links before returning source text.
        """
        from seam_runtime.runtime import SeamRuntime  # lazy

        rt = _open_runtime(self._db_path(scope_id))
        t0 = _time.monotonic()
        result = rt.search_ir(question, scope="thread", budget=self.budget, include_raw=True)
        retrieval_latency_ms = (_time.monotonic() - t0) * 1000.0

        if not result.candidates:
            return AdapterAnswer(
                retrieved_context="",
                retrieval_latency_ms=retrieval_latency_ms,
            )

        if self.include_evidence_closure:
            retrieved_context = self._build_evidence_context(rt, result)
        else:
            record_ids = [candidate.record.id for candidate in result.candidates]
            pack = rt.pack_ir(record_ids, lens="general", budget=self.budget)
            pack_dict = pack.to_dict() if hasattr(pack, "to_dict") else {}
            retrieved_context = json.dumps(pack_dict, sort_keys=True, indent=2)

        generated = None
        answer_latency_ms = None
        if self._answerer:
            t1 = _time.monotonic()
            generated = self._generate_answer(question, retrieved_context)
            answer_latency_ms = (_time.monotonic() - t1) * 1000.0

        return AdapterAnswer(
            retrieved_context=retrieved_context,
            generated_answer=generated,
            retrieval_latency_ms=retrieval_latency_ms,
            answer_latency_ms=answer_latency_ms,
        )

    def _generate_answer(self, question: str, context: str) -> str:
        prompt = (
            "Answer the question using ONLY the context. "
            "If the answer is not in the context, say 'unknown'. "
            "Reply with the shortest possible answer, no preamble.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
        )
        if self._answerer == "openai":
            return _openai_short_answer(self._answerer_model or "gpt-4o-mini", prompt)
        if self._answerer == "claude":
            return _claude_short_answer(self._answerer_model or "claude-haiku-4-5-20251001", prompt)
        raise ValueError(f"unknown answerer {self._answerer!r}")

    def _build_evidence_context(self, rt, result) -> str:
        """Build a bounded text context from candidate evidence closure."""
        closure_ids: set[str] = set()
        for candidate in result.candidates:
            closure_ids.add(candidate.record.id)
            closure_ids.update(candidate.record.evidence or [])
            closure_ids.update(candidate.record.prov or [])

        if closure_ids:
            first_batch = rt.store.load_ir(ids=list(closure_ids))
            for record in first_batch.records:
                if record.kind.value == "SPAN":
                    raw_id = record.attrs.get("raw_id")
                    if isinstance(raw_id, str) and raw_id:
                        closure_ids.add(raw_id)

        if not closure_ids:
            return ""

        batch = rt.store.load_ir(ids=sorted(closure_ids))
        text_snippets: list[str] = []
        seen: set[str] = set()
        for record in batch.records:
            if record.kind.value != "RAW":
                continue
            content = record.attrs.get("content")
            if isinstance(content, str) and content and content not in seen:
                seen.add(content)
                text_snippets.append(content)

        if text_snippets:
            return _trim_context("\n".join(text_snippets), self.budget)

        try:
            pack = rt.pack_ir(sorted(closure_ids), lens="general", budget=self.budget, mode="exact")
        except ValueError:
            record_ids = [candidate.record.id for candidate in result.candidates]
            pack = rt.pack_ir(record_ids, lens="general", budget=self.budget)
        pack_dict = pack.to_dict() if hasattr(pack, "to_dict") else {}
        return _trim_context(json.dumps(pack_dict, sort_keys=True, indent=2), self.budget)

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


def _trim_context(text: str, budget: int) -> str:
    if budget <= 0 or len(text) <= budget:
        return text
    return text[:budget]


def _uses_completion_token_budget(model: str) -> bool:
    model_id = model.lower()
    return model_id.startswith(("gpt-5", "o1", "o3", "o4"))


def _openai_short_answer(model: str, prompt: str, max_tokens: int = 64) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "openai answerer requires the openai package. "
            "Install with: pip install openai"
        ) from exc
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("openai answerer requires OPENAI_API_KEY in the environment")
    client = OpenAI(api_key=api_key)
    request: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }
    if _uses_completion_token_budget(model):
        request["max_completion_tokens"] = max_tokens
    else:
        request["max_tokens"] = max_tokens
    response = client.chat.completions.create(**request)
    return (response.choices[0].message.content or "").strip()


def _claude_short_answer(model: str, prompt: str, max_tokens: int = 64) -> str:
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError(
            "claude answerer requires the anthropic package. "
            "Install with: pip install anthropic"
        ) from exc
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("claude answerer requires ANTHROPIC_API_KEY in the environment")
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
