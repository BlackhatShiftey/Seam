from __future__ import annotations

import hashlib
import json
import time
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
        adapter.reset(case.case_id)

        for turn in case.conversation:
            adapter.ingest_turn(case.case_id, turn)

        answer: AdapterAnswer = adapter.answer(case.case_id, case.question)

        cr = context_recall(answer.retrieved_context, case.gold_answer)
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

        case_results.append(case_entry)

        if progress:
            progress(idx + 1, total)

    elapsed = time.time() - started_ts

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

    stable_cases = [
        {k: v for k, v in c.items() if k not in ("retrieval_latency_ms", "answer_latency_ms", "judge")}
        for c in case_results
    ]
    integrity = _integrity_hash(stable_cases, scores)

    return {
        "version": RESULT_VERSION,
        "benchmark": "locomo",
        "adapter": adapter.name,
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
