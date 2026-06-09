"""Free LoCoMo string-match scorer for the H2 self-improvement loop.

Implements the ``seam_runtime.self_improve.Scorer`` protocol on top of the real
LoCoMo adapter, so the proposer optimizes the *actual* benchmark metric
(``common.scoring.context_recall``) rather than a lookalike proxy. It is FREE:
``--answerer none --judge none`` semantics - no judge, no API, no paid call.

Fidelity: it drives the adapter's full ``answer()`` path (retrieval + evidence
closure + char-budget trim), exactly as ``runner.run_benchmark_grouped`` does,
and scores ``context_recall(retrieved_context, gold_answer)``. To evaluate a
candidate lever set it overrides the adapter runtime's cached
``_retrieval_flags`` for the duration of the scoring pass (restored after), so
``search_ir`` retrieves under the candidate flags without env mutation or
re-ingest. The conversation is ingested ONCE at construction; ``score`` only
re-runs retrieval, so a full lever sweep is cheap.

Anti-gaming note: ``context_recall`` rises with the char budget / search_top_k,
but those are FIXED on the adapter for the scorer's lifetime; the proposer's
levers only re-rank within that fixed budget, so it cannot game the score by
enlarging the context.
"""

from __future__ import annotations

from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Sequence

from benchmarks.external.common.dataset import load_locomo_cases
from benchmarks.external.common.scoring import context_recall
from benchmarks.external.common.types import BenchmarkCase
from benchmarks.external.locomo.adapters.seam import SeamLocomoAdapter
from seam_runtime.retrieval import load_retrieval_flags
from seam_runtime.self_improve import ScoreReport


def scope_for(case_id: str) -> str:
    """LoCoMo case_id -> conversation scope (``conv-26::q0`` -> ``conv-26``)."""
    return case_id.split("::", 1)[0]


@dataclass
class LocomoRecallScorer:
    """Mean ``context_recall`` over one conversation's questions, under whatever
    flags are passed to ``score`` (baseline when ``flags is None``)."""

    adapter: SeamLocomoAdapter
    scope: str
    cases: Sequence[BenchmarkCase]
    name: str = "locomo_recall"

    def score(self, runtime, flags=None) -> ScoreReport:
        rt = self.adapter._runtime(self.scope)
        previous = rt._retrieval_flags
        rt._retrieval_flags = flags if flags is not None else load_retrieval_flags(rt.store)
        per_case: dict[str, float] = {}
        category_values: dict[str, list[float]] = defaultdict(list)
        try:
            for case in self.cases:
                answer = self.adapter.answer(self.scope, case.question)
                recall = context_recall(answer.retrieved_context, case.gold_answer)
                per_case[case.case_id] = recall
                category_values[case.category or "unknown"].append(recall)
        finally:
            rt._retrieval_flags = previous
        n = len(self.cases)
        aggregate = sum(per_case.values()) / n if n else 0.0
        per_category = {cat: sum(v) / len(v) for cat, v in category_values.items()}
        return ScoreReport(
            scorer=self.name,
            aggregate=aggregate,
            n=n,
            per_category=per_category,
            per_case=per_case,
        )


def _group_by_scope(cases: Sequence[BenchmarkCase]) -> "OrderedDict[str, list[BenchmarkCase]]":
    groups: "OrderedDict[str, list[BenchmarkCase]]" = OrderedDict()
    for case in cases:
        groups.setdefault(scope_for(case.case_id), []).append(case)
    return groups


def build_locomo_recall_scorers(
    dataset_path: str,
    *,
    max_scopes: int = 1,
    question_limit: int | None = None,
    adapter: SeamLocomoAdapter | None = None,
    **adapter_kwargs,
) -> tuple[SeamLocomoAdapter, list[LocomoRecallScorer]]:
    """Load the dataset, ingest up to ``max_scopes`` conversations once each, and
    return one ``LocomoRecallScorer`` per scope. FREE - no answerer/judge.

    Pass the conversation through the adapter exactly as the benchmark runner
    does (reset -> ingest each turn). ``question_limit`` caps the questions per
    scope (for a faster inner-loop signal).
    """
    cases = load_locomo_cases(dataset_path)
    groups = _group_by_scope(cases)
    # answerer=None -> retrieval only, no generation (free, no judge/API).
    adapter = adapter or SeamLocomoAdapter(answerer=None, **adapter_kwargs)
    scorers: list[LocomoRecallScorer] = []
    for scope, group in list(groups.items())[:max_scopes]:
        adapter.reset(scope)
        for turn in group[0].conversation:
            adapter.ingest_turn(scope, turn)
        questions = list(group[:question_limit]) if question_limit else list(group)
        scorers.append(LocomoRecallScorer(adapter=adapter, scope=scope, cases=questions))
    return adapter, scorers
