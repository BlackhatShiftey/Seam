from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from benchmarks.external.common.types import AdapterAnswer, BenchmarkCase, MemorySystemAdapter
from benchmarks.external.common.scoring import aggregate_judge_scores, context_recall, exact_match, token_f1

RESULT_VERSION = "SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/1"


def _canonical_json(obj) -> str:
    """Canonical JSON serialization: sorted keys, no trailing whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _integrity_hash(cases_payload: list[dict], scores: dict) -> str:
    """SHA-256 over canonical JSON of cases + scores."""
    payload = _canonical_json({"cases": cases_payload, "scores": scores})
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def run_benchmark(
    *,
    adapter: MemorySystemAdapter,
    cases: list[BenchmarkCase],
    dataset_source: str = "unknown",
    judge: object | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Run adapter against cases and return a RunReport dict.

    The report shape matches SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/1:
    {version, benchmark, adapter, dataset: {source, case_count},
     run_started_at, elapsed_seconds, scores: {context_recall_mean, answer_em_mean, answer_f1_mean},
     cases: [{case_id, category, scores: {context_recall, answer_em, answer_f1},
              retrieval_latency_ms, answer_latency_ms}],
     integrity_hash}
    """
    started_ts = time.time()
    run_started_at = datetime.now(timezone.utc).isoformat()
    case_results: list[dict] = []

    total = len(cases)
    for idx, case in enumerate(cases):
        case_entry = _run_case(adapter, case, judge)
        case_results.append(case_entry)

        if progress:
            progress(idx + 1, total)

    elapsed = time.time() - started_ts
    return _build_report(
        adapter_name=adapter.name,
        dataset_source=dataset_source,
        run_started_at=run_started_at,
        elapsed=elapsed,
        case_results=case_results,
    )


def run_benchmark_parallel(
    *,
    adapter_factory: Callable[[], MemorySystemAdapter],
    adapter_name: str,
    cases: list[BenchmarkCase],
    dataset_source: str = "unknown",
    judge_factory: Callable[[], object | None] | None = None,
    workers: int = 4,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Run independent benchmark cases concurrently while preserving report order."""
    if workers <= 1:
        return run_benchmark(
            adapter=adapter_factory(),
            cases=cases,
            dataset_source=dataset_source,
            judge=judge_factory() if judge_factory else None,
            progress=progress,
        )

    started_ts = time.time()
    run_started_at = datetime.now(timezone.utc).isoformat()
    total = len(cases)
    case_results: list[dict | None] = [None] * total

    def _worker(index: int, case: BenchmarkCase) -> tuple[int, dict]:
        adapter = adapter_factory()
        judge = judge_factory() if judge_factory else None
        return index, _run_case(adapter, case, judge)

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_worker, index, case)
            for index, case in enumerate(cases)
        ]
        for future in as_completed(futures):
            index, case_entry = future.result()
            case_results[index] = case_entry
            completed += 1
            if progress:
                progress(completed, total)

    elapsed = time.time() - started_ts
    return _build_report(
        adapter_name=adapter_name,
        dataset_source=dataset_source,
        run_started_at=run_started_at,
        elapsed=elapsed,
        case_results=[case for case in case_results if case is not None],
    )


def run_benchmark_grouped(
    *,
    adapter: MemorySystemAdapter,
    cases: list[BenchmarkCase],
    scope_id: Callable[[BenchmarkCase], str],
    dataset_source: str = "unknown",
    judge: object | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Run cases grouped by shared conversation scope, ingesting each scope once."""
    started_ts = time.time()
    run_started_at = datetime.now(timezone.utc).isoformat()
    total = len(cases)
    case_results: list[dict] = []
    completed = 0

    for scope, group in _group_cases(cases, scope_id).items():
        adapter.reset(scope)
        for turn in group[0].conversation:
            adapter.ingest_turn(scope, turn)
        for case in group:
            answer = adapter.answer(scope, case.question)
            case_results.append(_score_case(case, answer, judge))
            completed += 1
            if progress:
                progress(completed, total)

    elapsed = time.time() - started_ts
    return _build_report(
        adapter_name=adapter.name,
        dataset_source=dataset_source,
        run_started_at=run_started_at,
        elapsed=elapsed,
        case_results=case_results,
    )


def run_benchmark_grouped_parallel(
    *,
    adapter_factory: Callable[[], MemorySystemAdapter],
    adapter_name: str,
    cases: list[BenchmarkCase],
    scope_id: Callable[[BenchmarkCase], str],
    dataset_source: str = "unknown",
    judge_factory: Callable[[], object | None] | None = None,
    workers: int = 4,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    """Run grouped scopes concurrently while preserving original case order."""
    if workers <= 1:
        return run_benchmark_grouped(
            adapter=adapter_factory(),
            cases=cases,
            scope_id=scope_id,
            dataset_source=dataset_source,
            judge=judge_factory() if judge_factory else None,
            progress=progress,
        )

    started_ts = time.time()
    run_started_at = datetime.now(timezone.utc).isoformat()
    groups = _group_cases(cases, scope_id)
    case_order = {case.case_id: index for index, case in enumerate(cases)}
    total = len(cases)
    case_results: list[dict | None] = [None] * total

    def _worker(scope: str, group: list[BenchmarkCase]) -> list[dict]:
        adapter = adapter_factory()
        judge = judge_factory() if judge_factory else None
        adapter.reset(scope)
        for turn in group[0].conversation:
            adapter.ingest_turn(scope, turn)
        return [
            _score_case(case, adapter.answer(scope, case.question), judge)
            for case in group
        ]

    completed = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(_worker, scope, group)
            for scope, group in groups.items()
        ]
        for future in as_completed(futures):
            entries = future.result()
            for entry in entries:
                case_results[case_order[entry["case_id"]]] = entry
            completed += len(entries)
            if progress:
                progress(completed, total)

    elapsed = time.time() - started_ts
    return _build_report(
        adapter_name=adapter_name,
        dataset_source=dataset_source,
        run_started_at=run_started_at,
        elapsed=elapsed,
        case_results=[case for case in case_results if case is not None],
    )


def _group_cases(
    cases: list[BenchmarkCase],
    scope_id: Callable[[BenchmarkCase], str],
) -> OrderedDict[str, list[BenchmarkCase]]:
    groups: OrderedDict[str, list[BenchmarkCase]] = OrderedDict()
    for case in cases:
        groups.setdefault(scope_id(case), []).append(case)
    return groups


def _run_case(adapter: MemorySystemAdapter, case: BenchmarkCase, judge: object | None) -> dict:
    adapter.reset(case.case_id)

    for turn in case.conversation:
        adapter.ingest_turn(case.case_id, turn)

    answer: AdapterAnswer = adapter.answer(case.case_id, case.question)
    return _score_case(case, answer, judge)


def _score_case(case: BenchmarkCase, answer: AdapterAnswer, judge: object | None) -> dict:
    cr = context_recall(answer.retrieved_context, case.gold_answer)

    if answer.generated_answer is not None:
        em = exact_match(answer.generated_answer, case.gold_answer)
        f1 = token_f1(answer.generated_answer, case.gold_answer)
    else:
        em = exact_match(answer.retrieved_context, case.gold_answer)
        f1 = token_f1(answer.retrieved_context, case.gold_answer)

    case_entry: dict = {
        "case_id": case.case_id,
        "category": case.category,
        "scores": {
            "context_recall": cr,
            "answer_em": em,
            "answer_f1": f1,
        },
        "retrieval_latency_ms": answer.retrieval_latency_ms,
        "answer_latency_ms": answer.answer_latency_ms,
    }

    if judge is not None:
        try:
            verdict = judge.score(
                question=case.question,
                gold=case.gold_answer,
                pred=answer.generated_answer or answer.retrieved_context,
            )
            case_entry["judge"] = {
                "verdict": verdict.verdict,
                "score": verdict.score,
                "rationale": verdict.rationale,
                "judge_name": verdict.judge_name,
                "judge_model": verdict.judge_model,
            }
        except Exception as exc:
            case_entry["judge"] = {"error": str(exc)}

    return case_entry


def _build_report(
    *,
    adapter_name: str,
    dataset_source: str,
    run_started_at: str,
    elapsed: float,
    case_results: list[dict],
) -> dict:
    total = len(case_results)

    # Compute means
    if total > 0:
        cr_mean = sum(c["scores"]["context_recall"] for c in case_results) / total
        em_mean = sum(c["scores"]["answer_em"] for c in case_results) / total
        f1_mean = sum(c["scores"]["answer_f1"] for c in case_results) / total
    else:
        cr_mean = em_mean = f1_mean = 0.0

    scores: dict = {
        "context_recall_mean": cr_mean,
        "answer_em_mean": em_mean,
        "answer_f1_mean": f1_mean,
    }

    judge_verdicts = []
    for c in case_results:
        j = c.get("judge")
        if j and "verdict" in j:
            judge_verdicts.append(j)
        else:
            judge_verdicts.append(None)
    if any(v is not None for v in judge_verdicts):
        scores.update(aggregate_judge_scores(judge_verdicts))

    # Per-category score breakdown when cases carry category metadata
    _add_per_category_scores(scores, case_results)

    stable_cases = [
        {k: v for k, v in c.items() if k not in ("retrieval_latency_ms", "answer_latency_ms", "judge")}
        for c in case_results
    ]
    integrity = _integrity_hash(stable_cases, scores)

    return {
        "version": RESULT_VERSION,
        "benchmark": "locomo",
        "adapter": adapter_name,
        "dataset": {
            "source": dataset_source,
            "case_count": total,
        },
        "run_started_at": run_started_at,
        "elapsed_seconds": elapsed,
        "scores": scores,
        "cases": case_results,
        "integrity_hash": integrity,
    }


def _add_per_category_scores(scores: dict, case_results: list[dict]) -> None:
    """Mutate *scores* to include per-category means when cases carry category fields.

    Only adds ``per_category`` if at least one case has a non-None category.
    Each entry contains ``context_recall_mean``, ``judge_score_mean`` (when a
    judge verdict is present in the category group), and ``case_count``.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for case in case_results:
        cat = case.get("category")
        if cat is not None:
            groups[str(cat)].append(case)

    if not groups:
        return

    per_category: dict[str, dict] = {}
    for cat, cases in sorted(groups.items(), key=lambda x: x[0]):
        n = len(cases)
        cr_mean = sum(c["scores"]["context_recall"] for c in cases) / n

        entry: dict = {
            "context_recall_mean": cr_mean,
            "case_count": n,
        }

        judge_scores = [
            c["judge"]["score"]
            for c in cases
            if isinstance(c.get("judge"), dict) and "score" in c["judge"]
        ]
        if judge_scores:
            entry["judge_score_mean"] = sum(judge_scores) / len(judge_scores)

        per_category[cat] = entry

    scores["per_category"] = per_category
