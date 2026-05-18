from __future__ import annotations

import os
import time

from benchmarks.external.common.types import AdapterAnswer, ConversationTurn


class ZepLocomoAdapter:
    """Zep / Graphiti comparator adapter for LoCoMo.

    One Zep ``user_id`` per scope_id; one Zep ``session_id`` per scope_id.
    Conversation turns are added as messages on the session. ``answer`` runs
    Zep memory search and returns the joined retrieved facts as
    ``retrieved_context``.

    Like the SEAM and Mem0 adapters, this adapter does NOT generate an answer;
    LLM-judge scoring is layered separately.

    Zep ingestion is asynchronous on the server side (fact extraction runs in
    a background job). A naive ``add then immediately search`` can return zero
    hits. The adapter does NOT insert a sleep; operators should use a
    processing-complete check or wait before running benchmarks against a
    real Zep instance.
    """

    name = "zep"

    def __init__(
        self,
        *,
        search_limit: int = 8,
        _client: object | None = None,
    ):
        self.search_limit = search_limit

        if _client is not None:
            self._client = _client
            self._sessions: dict[str, str] = {}
            self._is_stub = True
            return

        self._is_stub = False
        Zep = None
        try:
            from zep_cloud.client import Zep as ZepCloud

            Zep = ZepCloud
        except ImportError:
            try:
                from zep_python.client import Zep as ZepPython

                Zep = ZepPython
            except ImportError as exc:
                raise RuntimeError(
                    "--adapter zep requires the zep-cloud (or zep-python) package. "
                    "Install with: pip install seam[bench-zep]"
                ) from exc

        api_key = os.environ.get("ZEP_API_KEY")
        base_url = os.environ.get("ZEP_API_URL")
        if not api_key and not base_url:
            raise RuntimeError(
                "Zep requires ZEP_API_KEY (Zep Cloud) or ZEP_API_URL "
                "(self-hosted Zep CE) in the environment."
            )
        kwargs: dict = {}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self._client = Zep(**kwargs)
        self._sessions: dict[str, str] = {}

    # -- Protocol methods -------------------------------------------------

    def reset(self, scope_id: str) -> None:
        user_id = f"seam-bench-{scope_id}"
        session_id = f"seam-bench-{scope_id}-session"
        try:
            self._client.user.delete(user_id=user_id)
        except Exception:
            pass
        self._client.user.add(user_id=user_id)
        self._client.memory.add_session(session_id=session_id, user_id=user_id)
        self._sessions[scope_id] = session_id

    def ingest_turn(self, scope_id: str, turn: ConversationTurn) -> None:
        session_id = self._sessions[scope_id]
        role = (
            "user"
            if turn.speaker.lower().startswith(("speaker_a", "alice", "user"))
            else "assistant"
        )
        ts = turn.timestamp or ""
        prefix = f"[{turn.speaker} {ts}] ".rstrip() + " " if ts else f"[{turn.speaker}] "
        self._client.memory.add(
            session_id=session_id,
            messages=[{"role": role, "role_type": role, "content": prefix + turn.text}],
        )

    def answer(self, scope_id: str, question: str) -> AdapterAnswer:
        session_id = self._sessions[scope_id]
        t0 = time.perf_counter()
        results = self._client.memory.search_sessions(
            text=question,
            session_ids=[session_id],
            limit=self.search_limit,
        )
        retrieval_ms = (time.perf_counter() - t0) * 1000.0

        facts = []
        for hit in (getattr(results, "results", None) or []):
            fact = getattr(hit, "fact", None) or getattr(hit, "content", None) or str(hit)
            facts.append(str(fact))
        return AdapterAnswer(
            retrieved_context="\n".join(facts),
            generated_answer=None,
            retrieval_latency_ms=retrieval_ms,
            answer_latency_ms=0.0,
        )

    def close(self) -> None:
        if self._is_stub:
            self._sessions.clear()
            return
        for scope_id in list(self._sessions.keys()):
            user_id = f"seam-bench-{scope_id}"
            try:
                self._client.user.delete(user_id=user_id)
            except Exception:
                pass
        self._sessions.clear()
