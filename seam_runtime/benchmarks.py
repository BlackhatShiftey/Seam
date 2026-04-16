from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from .context_views import build_context_payload, render_context_pretty
from .dsl import compile_dsl
from .evals import default_retrieval_fixtures, run_retrieval_benchmark
from .lossless import benchmark_text_lossless, count_prompt_tokens
from .models import HashEmbeddingModel, cosine
from .vector import INDEXABLE_KINDS, SQLiteVectorIndex

if TYPE_CHECKING:
    from .runtime import SeamRuntime


BENCHMARK_VERSION = "SEAM-BENCH/1"
BENCHMARK_SUITES = ("lossless", "retrieval", "embedding", "long_context", "persistence", "agent_tasks")

BENCHMARK_ROOT = Path(__file__).resolve().parent.parent / "benchmarks"
FIXTURE_ROOT = BENCHMARK_ROOT / "fixtures"
LOSSLESS_FIXTURE_PATH = FIXTURE_ROOT / "lossless_cases.json"
LONG_CONTEXT_FIXTURE_PATH = FIXTURE_ROOT / "long_context_cases.json"
AGENT_TASK_FIXTURE_PATH = FIXTURE_ROOT / "agent_tasks.json"
RETRIEVAL_FIXTURE_PATH = Path(__file__).resolve().parent.parent / "docs" / "retrieval_gold_fixtures.json"
LOSSLESS_DEMO_PATH = Path(__file__).resolve().parent.parent / "tools" / "lossless_demo_input.txt"


def run_benchmark_suite(
    runtime: "SeamRuntime",
    suite: str = "all",
    tokenizer: str = "auto",
    min_token_savings: float = 0.30,
    persist: bool = False,
    include_machine_text: bool = False,
    bundle_path: str | Path | None = None,
) -> dict[str, Any]:
    selected_suites = list(BENCHMARK_SUITES) if suite == "all" else [_validate_suite_name(suite)]
    run_id = f"bench:{uuid4().hex[:12]}"
    family_reports: dict[str, dict[str, Any]] = {}

    for family in selected_suites:
        if family == "lossless":
            family_reports[family] = _run_lossless_family(
                runtime,
                tokenizer=tokenizer,
                min_token_savings=min_token_savings,
                persist=persist,
                include_machine_text=include_machine_text,
            )
            continue
        if family == "retrieval":
            family_reports[family] = _run_retrieval_family(runtime)
            continue
        if family == "embedding":
            family_reports[family] = _run_embedding_family(runtime)
            continue
        if family == "long_context":
            family_reports[family] = _run_long_context_family(runtime, tokenizer=tokenizer, persist=persist)
            continue
        if family == "persistence":
            family_reports[family] = _run_persistence_family(runtime, tokenizer=tokenizer)
            continue
        if family == "agent_tasks":
            family_reports[family] = _run_agent_task_family(runtime, tokenizer=tokenizer, persist=persist)
            continue

    manifest = {
        "version": BENCHMARK_VERSION,
        "run_id": run_id,
        "requested_suite": suite,
        "executed_suites": selected_suites,
        "created_at": _utc_now(),
        "git_sha": _git_sha(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "db_path": runtime.store.path,
        "tokenizer": tokenizer,
        "min_token_savings": round(min_token_savings, 6),
        "dependencies": {
            "rich": find_spec("rich") is not None,
            "chromadb": find_spec("chromadb") is not None,
            "tiktoken": find_spec("tiktoken") is not None,
        },
        "dataset_hashes": _dataset_manifest(),
    }
    summary = _build_suite_summary(family_reports)
    report = {
        "manifest": manifest,
        "summary": summary,
        "families": family_reports,
        "improvement_loop": _aggregate_family_actions(family_reports),
    }
    report["bundle_hash"] = _hash_payload(report, "bundle_hash")

    if bundle_path is not None:
        Path(bundle_path).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if persist:
        runtime.store.write_benchmark_run(report)
    return report


def verify_benchmark_bundle(bundle: str | Path | dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(Path(bundle).read_text(encoding="utf-8")) if isinstance(bundle, (str, Path)) else dict(bundle)
    expected_bundle_hash = payload.get("bundle_hash")
    actual_bundle_hash = _hash_payload(payload, "bundle_hash")
    bundle_hash_ok = expected_bundle_hash == actual_bundle_hash
    case_results: list[dict[str, Any]] = []

    for family_name, family in payload.get("families", {}).items():
        for case in family.get("cases", []):
            expected_case_hash = case.get("case_hash")
            actual_case_hash = _hash_payload(case, "case_hash")
            case_results.append(
                {
                    "family": family_name,
                    "case_id": case.get("case_id"),
                    "expected_case_hash": expected_case_hash,
                    "actual_case_hash": actual_case_hash,
                    "ok": expected_case_hash == actual_case_hash,
                }
            )

    return {
        "status": "PASS" if bundle_hash_ok and all(item["ok"] for item in case_results) else "FAIL",
        "bundle_hash_ok": bundle_hash_ok,
        "expected_bundle_hash": expected_bundle_hash,
        "actual_bundle_hash": actual_bundle_hash,
        "case_checks": case_results,
    }


def render_benchmark_pretty(payload: dict[str, Any]) -> str:
    manifest = payload.get("manifest", {})
    summary = payload.get("summary", {})
    family_lines = []
    for family_name, family in payload.get("families", {}).items():
        family_summary = family.get("summary", {})
        family_lines.append(
            "- "
            f"{family_name}: pass_rate={float(family_summary.get('pass_rate', 0.0)):.1%} "
            f"cases={family_summary.get('case_count', 0)} "
            f"signals={_render_key_metrics(family_name, family_summary)}"
        )
    action_lines = [f"- {action}" for action in payload.get("improvement_loop", [])[:8]]
    if not action_lines:
        action_lines = ["- no immediate regressions detected"]
    return "\n".join(
        [
            f"SEAM benchmark suite: {summary.get('status')}",
            f"Run id: {manifest.get('run_id')}",
            f"Suits: {', '.join(manifest.get('executed_suites', []))}",
            f"Cases: {summary.get('case_count')} ({summary.get('passed_cases')} passed)",
            f"Exactness rate: {float(summary.get('exactness_rate', 0.0)):.1%}",
            f"Token savings p50: {float(summary.get('token_savings_p50', 0.0)):.1%}",
            f"Git SHA: {manifest.get('git_sha') or '(unavailable)'}",
            f"Bundle hash: {payload.get('bundle_hash')}",
            "",
            "Families:",
            *family_lines,
            "",
            "Improvement loop:",
            *action_lines,
        ]
    )


def render_benchmark_verification_pretty(payload: dict[str, Any]) -> str:
    lines = [
        f"Benchmark bundle verification: {payload.get('status')}",
        f"Bundle hash OK: {'yes' if payload.get('bundle_hash_ok') else 'no'}",
    ]
    for item in payload.get("case_checks", [])[:10]:
        lines.append(f"- {item['family']}::{item['case_id']} => {'OK' if item['ok'] else 'MISMATCH'}")
    return "\n".join(lines)


def _run_lossless_family(
    runtime: "SeamRuntime",
    tokenizer: str,
    min_token_savings: float,
    persist: bool,
    include_machine_text: bool,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for config in _load_json_fixture(LOSSLESS_FIXTURE_PATH, _default_lossless_cases()):
        text = _resolve_lossless_text(config)
        result = benchmark_text_lossless(
            text,
            tokenizer=tokenizer,
            min_token_savings=float(config.get("min_token_savings", min_token_savings)),
        )
        artifact_id = None
        if persist:
            artifact_id = runtime.store.write_machine_artifact(
                source_type="benchmark.lossless",
                source_id=config["name"],
                artifact=result.artifact.to_dict(include_machine_text=True),
                roundtrip_ok=result.roundtrip_match,
                metadata={"family": "lossless", "case": config["name"]},
            )
        case = {
            "case_id": config["name"],
            "status": "PASS" if result.passed else "FAIL",
            "metrics": {
                "roundtrip_match": result.roundtrip_match,
                "meets_target": result.meets_target,
                "token_savings_ratio": round(result.artifact.token_savings_ratio, 6),
                "byte_savings_ratio": round(result.artifact.byte_savings_ratio, 6),
                "intelligence_per_token_gain": round(result.artifact.intelligence_per_token_gain, 6),
                "machine_tokens": result.artifact.machine_tokens,
                "original_tokens": result.artifact.original_tokens,
            },
            "trace": result.to_dict(include_machine_text=include_machine_text),
            "debug_flags": list(result.flags),
            "improvement_loop": _lossless_actions(result, config["name"]),
        }
        if artifact_id is not None:
            case["artifact_id"] = artifact_id
        cases.append(_stamp_case_hash(case))

    summary = {
        "case_count": len(cases),
        "pass_rate": _ratio(sum(1 for case in cases if case["status"] == "PASS"), len(cases)),
        "exactness_rate": _ratio(sum(1 for case in cases if case["metrics"]["roundtrip_match"]), len(cases)),
        "avg_token_savings": _average(case["metrics"]["token_savings_ratio"] for case in cases),
        "avg_gain": _average(case["metrics"]["intelligence_per_token_gain"] for case in cases),
        "worst_case_savings": min((case["metrics"]["token_savings_ratio"] for case in cases), default=0.0),
    }
    return {
        "family": "lossless",
        "summary": summary,
        "cases": cases,
        "improvement_loop": _unique_actions(case["improvement_loop"] for case in cases),
    }


def _run_retrieval_family(runtime: "SeamRuntime") -> dict[str, Any]:
    benchmark = run_retrieval_benchmark(embedding_model=runtime.embedding_model)
    cases: list[dict[str, Any]] = []
    ndcg_scores: list[float] = []
    for fixture in benchmark["fixtures"]:
        hybrid = fixture["tracks"]["hybrid"]
        raw = fixture["tracks"]["raw"]
        ndcg = _ndcg_at_k(hybrid["ranked_ids"], fixture["expected_ids"])
        ndcg_scores.append(ndcg)
        case = {
            "case_id": fixture["name"],
            "status": "PASS"
            if hybrid["hit"] and fixture["packs"]["exact"]["reversibility"] == 1.0 and fixture["packs"]["context"]["traceability"] >= 0.66
            else "FAIL",
            "metrics": {
                "hybrid_hit": hybrid["hit"],
                "hybrid_recall_at_k": hybrid["recall_at_k"],
                "hybrid_mrr": hybrid["reciprocal_rank"],
                "hybrid_ndcg_at_k": round(ndcg, 6),
                "raw_recall_at_k": raw["recall_at_k"],
                "hybrid_vs_raw_recall_delta": round(hybrid["recall_at_k"] - raw["recall_at_k"], 6),
                "exact_pack_reversible": fixture["packs"]["exact"]["reversibility"] == 1.0,
                "context_traceability": fixture["packs"]["context"]["traceability"],
            },
            "trace": fixture,
            "debug_flags": _retrieval_flags(fixture),
            "improvement_loop": _retrieval_actions(fixture),
        }
        cases.append(_stamp_case_hash(case))

    summary = {
        "case_count": len(cases),
        "pass_rate": _ratio(sum(1 for case in cases if case["status"] == "PASS"), len(cases)),
        "hybrid_hit_rate": benchmark["summary"]["tracks"]["hybrid"]["hit_rate"],
        "hybrid_mrr": benchmark["summary"]["tracks"]["hybrid"]["mrr"],
        "hybrid_recall_at_k": benchmark["summary"]["tracks"]["hybrid"]["recall_at_k"],
        "hybrid_ndcg_at_k": _average(ndcg_scores),
        "exact_pack_reversible_rate": _ratio(
            sum(1 for case in cases if case["metrics"]["exact_pack_reversible"]),
            len(cases),
        ),
    }
    return {
        "family": "retrieval",
        "summary": summary,
        "cases": cases,
        "improvement_loop": _unique_actions(case["improvement_loop"] for case in cases),
    }


def _run_embedding_family(runtime: "SeamRuntime") -> dict[str, Any]:
    model = runtime.embedding_model or HashEmbeddingModel()
    cases: list[dict[str, Any]] = []
    margins: list[float] = []

    for fixture in default_retrieval_fixtures():
        batch = compile_dsl(fixture.source, scope="project")
        query_vector = model.embed(fixture.query)
        scores: dict[str, float] = {}
        for record in batch.records:
            if record.kind not in INDEXABLE_KINDS:
                continue
            scores[record.id] = cosine(query_vector, model.embed(SQLiteVectorIndex.render_record_text(record)))
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        expected_scores = [score for record_id, score in ranked if record_id in fixture.expected_ids]
        distractor_scores = [score for record_id, score in ranked if record_id not in fixture.expected_ids]
        top_record_id = ranked[0][0] if ranked else None
        expected_best = max(expected_scores, default=0.0)
        distractor_best = max(distractor_scores, default=0.0)
        margin = expected_best - distractor_best
        margins.append(margin)
        case = {
            "case_id": fixture.name,
            "status": "PASS" if top_record_id in fixture.expected_ids and margin >= 0.0 else "FAIL",
            "metrics": {
                "top1_correct": top_record_id in fixture.expected_ids,
                "expected_best_score": round(expected_best, 6),
                "distractor_best_score": round(distractor_best, 6),
                "separation_margin": round(margin, 6),
            },
            "trace": {
                "query": fixture.query,
                "expected_ids": fixture.expected_ids,
                "top_ranked": [{"record_id": record_id, "score": round(score, 6)} for record_id, score in ranked[:5]],
                "embedding_model": model.name,
            },
            "debug_flags": ["weak_margin"] if margin < 0.05 else [],
            "improvement_loop": _embedding_actions(top_record_id, fixture.expected_ids, margin),
        }
        cases.append(_stamp_case_hash(case))

    summary = {
        "case_count": len(cases),
        "pass_rate": _ratio(sum(1 for case in cases if case["status"] == "PASS"), len(cases)),
        "top1_rate": _ratio(sum(1 for case in cases if case["metrics"]["top1_correct"]), len(cases)),
        "avg_margin": _average(margins),
        "min_margin": min(margins, default=0.0),
        "embedding_model": model.name,
    }
    return {
        "family": "embedding",
        "summary": summary,
        "cases": cases,
        "improvement_loop": _unique_actions(case["improvement_loop"] for case in cases),
    }

def _run_long_context_family(runtime: "SeamRuntime", tokenizer: str, persist: bool) -> dict[str, Any]:
    from experimental.retrieval_orchestrator import RetrievalOrchestrator

    cases: list[dict[str, Any]] = []
    for config in _load_json_fixture(LONG_CONTEXT_FIXTURE_PATH, _default_long_context_cases()):
        temp_runtime = runtime.__class__(Path(tempfile.gettempdir()) / f"seam-bench-long-{uuid4().hex}.db")
        batch = compile_dsl(_build_long_context_dsl(config), scope="project")
        temp_runtime.persist_ir(batch)
        rag = RetrievalOrchestrator(temp_runtime).rag(
            config["query"],
            budget=int(config.get("budget", 5)),
            pack_budget=int(config.get("pack_budget", 128)),
        )
        prompt_payload = build_context_payload(rag.to_dict(), view="prompt")
        summary_payload = build_context_payload(rag.to_dict(), view="summary")
        records_payload = build_context_payload(rag.to_dict(), view="records")
        prompt_text = render_context_pretty(prompt_payload)
        summary_text = render_context_pretty(summary_payload)
        records_text = json.dumps(records_payload["output"], indent=2, sort_keys=True)
        prompt_tokens, estimator = count_prompt_tokens(prompt_text, tokenizer=tokenizer)
        records_tokens, _ = count_prompt_tokens(records_text, tokenizer=tokenizer)
        expected_hit = any(record_id in config["expected_ids"] for record_id in rag.candidate_ids)
        prompt_contains = all(snippet in prompt_text for snippet in config.get("required_prompt_snippets", []))
        summary_contains = all(snippet in summary_text for snippet in config.get("required_summary_snippets", []))
        projection_id = None
        if persist:
            temp_runtime.store.write_projection(
                record_id=f"benchmark:{config['name']}",
                projection_kind="prompt",
                projection_text=prompt_text,
                tokenizer=estimator,
                metadata={"family": "long_context", "case": config["name"]},
            )
            projection_id = temp_runtime.store.write_projection(
                record_id=f"benchmark:{config['name']}",
                projection_kind="records",
                projection_text=records_text,
                tokenizer=estimator,
                metadata={"family": "long_context", "case": config["name"]},
            )
        case = {
            "case_id": config["name"],
            "status": "PASS" if expected_hit and prompt_contains and summary_contains else "FAIL",
            "metrics": {
                "expected_hit": expected_hit,
                "prompt_contains": prompt_contains,
                "summary_contains": summary_contains,
                "prompt_tokens": prompt_tokens,
                "records_tokens": records_tokens,
                "prompt_token_savings_vs_records": round(_savings_ratio(records_tokens, prompt_tokens), 6),
                "token_estimator": estimator,
            },
            "trace": {
                "query": config["query"],
                "candidate_ids": rag.candidate_ids,
                "prompt": prompt_text,
                "summary": summary_text,
            },
            "debug_flags": _long_context_flags(expected_hit, prompt_contains, summary_contains, prompt_tokens, records_tokens),
            "improvement_loop": _long_context_actions(expected_hit, prompt_contains, summary_contains, prompt_tokens, records_tokens),
        }
        if projection_id is not None:
            case["projection_id"] = projection_id
        cases.append(_stamp_case_hash(case))

    summary = {
        "case_count": len(cases),
        "pass_rate": _ratio(sum(1 for case in cases if case["status"] == "PASS"), len(cases)),
        "hit_rate": _ratio(sum(1 for case in cases if case["metrics"]["expected_hit"]), len(cases)),
        "prompt_contains_rate": _ratio(sum(1 for case in cases if case["metrics"]["prompt_contains"]), len(cases)),
        "avg_prompt_token_savings_vs_records": _average(case["metrics"]["prompt_token_savings_vs_records"] for case in cases),
    }
    return {
        "family": "long_context",
        "summary": summary,
        "cases": cases,
        "improvement_loop": _unique_actions(case["improvement_loop"] for case in cases),
    }
def _run_persistence_family(runtime: "SeamRuntime", tokenizer: str) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="seam-bench-persist-") as temp_dir:
        temp_db = Path(temp_dir) / "persistence.db"
        temp_runtime = runtime.__class__(temp_db)
        batch = compile_dsl(
            """
entity project "SEAM" as p1
claim c1:
  subject p1
  predicate translator_for
  object natural_language
claim c2:
  subject p1
  predicate projection_index
  object tokenizer_projection
"""
        )
        temp_runtime.persist_ir(batch)
        reopened_runtime = runtime.__class__(temp_db)
        search = reopened_runtime.search_ir("translator natural language", budget=3)
        case = {
            "case_id": "persist_reload_search",
            "status": "PASS" if any(candidate.record.id == "c1" for candidate in search.candidates) else "FAIL",
            "metrics": {
                "candidate_count": len(search.candidates),
                "expected_hit": any(candidate.record.id == "c1" for candidate in search.candidates),
            },
            "trace": search.to_dict(),
            "debug_flags": [],
            "improvement_loop": ["inspect persistence/load path if expected records do not survive reopen"]
            if not any(candidate.record.id == "c1" for candidate in search.candidates)
            else [],
        }
        cases.append(_stamp_case_hash(case))

        lossless = benchmark_text_lossless("SEAM preserves exact context while compressing token usage for lossless recovery.\n" * 12, tokenizer=tokenizer)
        artifact_id = reopened_runtime.store.write_machine_artifact(
            source_type="benchmark.persistence",
            source_id="machine_artifact_roundtrip",
            artifact=lossless.artifact.to_dict(include_machine_text=True),
            roundtrip_ok=lossless.roundtrip_match,
            metadata={"family": "persistence"},
        )
        artifact = reopened_runtime.store.read_machine_artifact(artifact_id)
        case = {
            "case_id": "machine_artifact_roundtrip",
            "status": "PASS" if artifact.get("roundtrip_ok") and artifact.get("sha256_raw") == lossless.artifact.sha256 else "FAIL",
            "metrics": {
                "roundtrip_ok": artifact.get("roundtrip_ok"),
                "token_savings_ratio": artifact.get("token_savings_ratio"),
            },
            "trace": artifact,
            "debug_flags": [],
            "improvement_loop": ["inspect machine_artifacts schema and serialization if roundtrip metadata does not reload"]
            if not artifact.get("roundtrip_ok")
            else [],
        }
        cases.append(_stamp_case_hash(case))

        projection_id = reopened_runtime.store.write_projection(
            record_id="benchmark:persistence",
            projection_kind="prompt",
            projection_text="SEAM retrieved context\n[1] c1 [CLM] p1 translator_for natural_language",
            tokenizer="char4_approx",
            metadata={"family": "persistence"},
        )
        projections = reopened_runtime.store.read_projections("benchmark:persistence")
        case = {
            "case_id": "projection_index_roundtrip",
            "status": "PASS" if any(item["projection_kind"] == "prompt" for item in projections) else "FAIL",
            "metrics": {
                "projection_count": len(projections),
                "projection_id": projection_id,
            },
            "trace": projections,
            "debug_flags": [],
            "improvement_loop": ["inspect projection index writes if benchmark projections are missing after reload"]
            if not any(item["projection_kind"] == "prompt" for item in projections)
            else [],
        }
        cases.append(_stamp_case_hash(case))

        sample_run = {
            "manifest": {"run_id": "bench:persistence-sample", "version": BENCHMARK_VERSION},
            "summary": {"status": "PASS"},
            "families": {},
            "improvement_loop": [],
            "bundle_hash": "sample",
        }
        reopened_runtime.store.write_benchmark_run(sample_run)
        loaded_run = reopened_runtime.store.read_benchmark_run("bench:persistence-sample")
        case = {
            "case_id": "benchmark_run_roundtrip",
            "status": "PASS" if loaded_run.get("summary", {}).get("status") == "PASS" else "FAIL",
            "metrics": {
                "loaded": bool(loaded_run),
                "status": loaded_run.get("summary", {}).get("status"),
            },
            "trace": loaded_run,
            "debug_flags": [],
            "improvement_loop": ["inspect benchmark_runs schema if stored benchmark reports do not reload"]
            if loaded_run.get("summary", {}).get("status") != "PASS"
            else [],
        }
        cases.append(_stamp_case_hash(case))

    summary = {
        "case_count": len(cases),
        "pass_rate": _ratio(sum(1 for case in cases if case["status"] == "PASS"), len(cases)),
        "durability_rate": _ratio(sum(1 for case in cases if case["status"] == "PASS"), len(cases)),
    }
    return {
        "family": "persistence",
        "summary": summary,
        "cases": cases,
        "improvement_loop": _unique_actions(case["improvement_loop"] for case in cases),
    }


def _run_agent_task_family(runtime: "SeamRuntime", tokenizer: str, persist: bool) -> dict[str, Any]:
    from experimental.retrieval_orchestrator import RetrievalOrchestrator

    cases: list[dict[str, Any]] = []
    for config in _load_json_fixture(AGENT_TASK_FIXTURE_PATH, _default_agent_task_cases()):
        temp_runtime = runtime.__class__(Path(tempfile.gettempdir()) / f"seam-bench-agent-{uuid4().hex}.db")
        batch = compile_dsl(config["dsl"], scope="project")
        temp_runtime.persist_ir(batch)
        rag = RetrievalOrchestrator(temp_runtime).rag(
            config["query"],
            budget=int(config.get("budget", 5)),
            pack_budget=int(config.get("pack_budget", 128)),
        )
        prompt_payload = build_context_payload(rag.to_dict(), view="prompt")
        evidence_payload = build_context_payload(rag.to_dict(), view="evidence")
        summary_payload = build_context_payload(rag.to_dict(), view="summary")
        records_payload = build_context_payload(rag.to_dict(), view="records")
        prompt_text = render_context_pretty(prompt_payload)
        summary_text = render_context_pretty(summary_payload)
        records_text = render_context_pretty(records_payload)
        evidence_rows = evidence_payload["output"]
        payload_text = records_text if records_text != "[]" else prompt_text
        payload_benchmark = benchmark_text_lossless(payload_text, tokenizer=tokenizer, min_token_savings=0.10)
        prompt_tokens, estimator = count_prompt_tokens(prompt_text, tokenizer=tokenizer)
        records_tokens, _ = count_prompt_tokens(records_text, tokenizer=tokenizer)
        expected_hit = any(record_id in config["expected_ids"] for record_id in rag.candidate_ids)
        prompt_contains = all(snippet in prompt_text for snippet in config.get("required_prompt_snippets", []))
        summary_contains = all(snippet in summary_text for snippet in config.get("required_summary_snippets", []))
        evidence_contains = any(row["record_id"] in config["expected_ids"] for row in evidence_rows)
        records_contain = all(record_id in records_text for record_id in config["expected_ids"])
        artifact_id = None
        if persist:
            artifact_id = temp_runtime.store.write_machine_artifact(
                source_type="benchmark.agent_task",
                source_id=config["name"],
                artifact=payload_benchmark.artifact.to_dict(include_machine_text=True),
                roundtrip_ok=payload_benchmark.roundtrip_match,
                metadata={"family": "agent_tasks", "case": config["name"], "projection": "exact_payload"},
            )
        case = {
            "case_id": config["name"],
            "status": "PASS"
            if expected_hit and prompt_contains and summary_contains and evidence_contains and records_contain and payload_benchmark.roundtrip_match
            else "FAIL",
            "metrics": {
                "expected_hit": expected_hit,
                "prompt_contains": prompt_contains,
                "summary_contains": summary_contains,
                "evidence_contains": evidence_contains,
                "records_contain": records_contain,
                "prompt_tokens": prompt_tokens,
                "records_tokens": records_tokens,
                "prompt_token_savings_vs_records": round(_savings_ratio(records_tokens, prompt_tokens), 6),
                "exact_payload_lossless_savings": round(payload_benchmark.artifact.token_savings_ratio, 6),
                "exact_payload_roundtrip_match": payload_benchmark.roundtrip_match,
                "token_estimator": estimator,
            },
            "trace": {
                "query": config["query"],
                "candidate_ids": rag.candidate_ids,
                "prompt": prompt_text,
                "summary": summary_text,
                "evidence": evidence_rows,
                "exact_payload_compression": payload_benchmark.to_dict(include_machine_text=False),
            },
            "debug_flags": _agent_task_flags(
                expected_hit,
                prompt_contains,
                summary_contains,
                evidence_contains,
                records_contain,
                prompt_tokens,
                records_tokens,
            ),
            "improvement_loop": _agent_task_actions(
                expected_hit,
                prompt_contains,
                summary_contains,
                evidence_contains,
                records_contain,
                prompt_tokens,
                records_tokens,
                payload_benchmark.artifact.token_savings_ratio,
            ),
        }
        if artifact_id is not None:
            case["artifact_id"] = artifact_id
        cases.append(_stamp_case_hash(case))

    summary = {
        "case_count": len(cases),
        "pass_rate": _ratio(sum(1 for case in cases if case["status"] == "PASS"), len(cases)),
        "task_success_rate": _ratio(sum(1 for case in cases if case["metrics"]["expected_hit"]), len(cases)),
        "avg_prompt_token_savings_vs_records": _average(case["metrics"]["prompt_token_savings_vs_records"] for case in cases),
        "avg_exact_payload_lossless_savings": _average(case["metrics"]["exact_payload_lossless_savings"] for case in cases),
    }
    return {
        "family": "agent_tasks",
        "summary": summary,
        "cases": cases,
        "improvement_loop": _unique_actions(case["improvement_loop"] for case in cases),
    }
def _build_suite_summary(family_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    cases = [case for family in family_reports.values() for case in family.get("cases", [])]
    token_savings = [
        case["metrics"].get("token_savings_ratio")
        for case in cases
        if isinstance(case.get("metrics", {}).get("token_savings_ratio"), (int, float))
    ]
    exactness_values = []
    for case in cases:
        metrics = case.get("metrics", {})
        if "roundtrip_match" in metrics:
            exactness_values.append(1.0 if metrics["roundtrip_match"] else 0.0)
        elif "exact_pack_reversible" in metrics:
            exactness_values.append(1.0 if metrics["exact_pack_reversible"] else 0.0)
        elif "prompt_roundtrip_match" in metrics:
            exactness_values.append(1.0 if metrics["prompt_roundtrip_match"] else 0.0)
    passed_cases = sum(1 for case in cases if case["status"] == "PASS")
    return {
        "status": "PASS" if cases and passed_cases == len(cases) else "FAIL",
        "family_count": len(family_reports),
        "case_count": len(cases),
        "passed_cases": passed_cases,
        "exactness_rate": _average(exactness_values) if exactness_values else 1.0,
        "token_savings_p50": _percentile(token_savings, 0.50),
        "token_savings_p95": _percentile(token_savings, 0.95),
        "token_savings_min": min(token_savings, default=0.0),
    }


def _aggregate_family_actions(family_reports: dict[str, dict[str, Any]]) -> list[str]:
    family_actions = [family.get("improvement_loop", []) for family in family_reports.values()]
    summary = _build_suite_summary(family_reports)
    actions = _unique_actions(family_actions)
    if summary["exactness_rate"] < 1.0:
        actions.insert(0, "Lossless and exact reconstruction gates must stay at 100% before release.")
    if summary.get("token_savings_available") and summary["token_savings_p50"] < 0.30:
        actions.append("Median token savings are below the machine-efficiency target; add stronger reversible transforms and projection rules.")
    return actions


def _load_json_fixture(path: Path, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _default_lossless_cases() -> list[dict[str, Any]]:
    return [
        {"name": "lossless_demo_input", "source_file": str(LOSSLESS_DEMO_PATH), "min_token_savings": 0.75},
        {
            "name": "operator_memory_repeat",
            "text": "\n".join(["SEAM preserves exact context while compressing token usage for lossless recovery."] * 32),
            "min_token_savings": 0.30,
        },
    ]


def _default_long_context_cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "translator_anchor_early",
            "query": "predicate:translator_for object:natural_language",
            "expected_ids": ["anchor_early"],
            "required_prompt_snippets": ["translator_for", "natural_language"],
            "required_summary_snippets": ["translator_for", "natural_language"],
            "filler_count": 18,
            "target_position": "early",
            "target": {"id": "anchor_early", "predicate": "translator_for", "object": "natural_language"},
        },
        {
            "name": "projection_anchor_late",
            "query": "predicate:projection_index object:tokenizer_projection",
            "expected_ids": ["anchor_late"],
            "required_prompt_snippets": ["projection_index", "tokenizer_projection"],
            "required_summary_snippets": ["projection_index", "tokenizer_projection"],
            "filler_count": 18,
            "target_position": "late",
            "target": {"id": "anchor_late", "predicate": "projection_index", "object": "tokenizer_projection"},
        },
    ]


def _default_agent_task_cases() -> list[dict[str, Any]]:
    return [
        {
            "name": "translator_context_task",
            "query": "predicate:translator_for object:natural_language",
            "expected_ids": ["c1"],
            "required_prompt_snippets": ["translator_for", "natural_language"],
            "required_summary_snippets": ["translator_for", "natural_language"],
            "dsl": """
entity project "SEAM" as p1
claim c1:
  subject p1
  predicate translator_for
  object natural_language
claim c2:
  subject p1
  predicate memory_runtime
  object durable_context
claim c3:
  subject p1
  predicate exact_rebuild
  object source_state
""",
        },
        {
            "name": "projection_context_task",
            "query": "predicate:projection_index object:tokenizer_projection",
            "expected_ids": ["c2"],
            "required_prompt_snippets": ["projection_index", "tokenizer_projection"],
            "required_summary_snippets": ["projection_index", "tokenizer_projection"],
            "dsl": """
entity project "SEAM" as p1
claim c1:
  subject p1
  predicate persistent_memory
  object sqlite_truth
claim c2:
  subject p1
  predicate projection_index
  object tokenizer_projection
claim c3:
  subject p1
  predicate benchmark_engine
  object glassbox_traces
""",
        },
    ]


def _resolve_lossless_text(config: dict[str, Any]) -> str:
    source_file = config.get("source_file")
    if source_file:
        return Path(source_file).read_text(encoding="utf-8")
    return str(config.get("text", ""))


def _build_long_context_dsl(config: dict[str, Any]) -> str:
    target = config["target"]
    filler_count = int(config.get("filler_count", 12))
    filler_claims = [
        f"""claim filler_{index}:
  subject p1
  predicate memory_note_{index}
  object filler_context_{index}
"""
        for index in range(1, filler_count + 1)
    ]
    target_claim = f"""claim {target['id']}:
  subject p1
  predicate {target['predicate']}
  object {target['object']}
"""
    if config.get("target_position") == "early":
        claim_blocks = [target_claim, *filler_claims]
    else:
        claim_blocks = [*filler_claims, target_claim]
    return "\n".join(['entity project "SEAM" as p1', *claim_blocks])


def _dataset_manifest() -> list[dict[str, str]]:
    items = []
    for path in [LOSSLESS_FIXTURE_PATH, LONG_CONTEXT_FIXTURE_PATH, AGENT_TASK_FIXTURE_PATH, RETRIEVAL_FIXTURE_PATH, LOSSLESS_DEMO_PATH]:
        if path.exists():
            items.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return items


def _validate_suite_name(suite: str) -> str:
    if suite not in BENCHMARK_SUITES:
        raise ValueError(f"Unsupported benchmark suite: {suite}")
    return suite


def _stamp_case_hash(case: dict[str, Any]) -> dict[str, Any]:
    stamped = dict(case)
    stamped["case_hash"] = _hash_payload(stamped, "case_hash")
    return stamped


def _hash_payload(payload: dict[str, Any], ignore_key: str) -> str:
    normalized = {key: value for key, value in payload.items() if key != ignore_key}
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _lossless_actions(result, case_id: str) -> list[str]:
    actions = []
    if not result.roundtrip_match:
        actions.append(f"{case_id}: investigate lossless roundtrip mismatch before trusting machine-language compression.")
    if not result.meets_target:
        actions.append(f"{case_id}: add stronger reversible transforms or codec ordering because token savings target was missed.")
    if any(flag.startswith("iteration_") for flag in result.flags):
        actions.append(f"{case_id}: review fluctuation log and promote stable reversible rules from the best candidate search.")
    return actions


def _retrieval_flags(fixture: dict[str, Any]) -> list[str]:
    flags = []
    if not fixture["tracks"]["hybrid"]["hit"]:
        flags.append("hybrid_miss")
    if fixture["tracks"]["hybrid"]["recall_at_k"] < fixture["tracks"]["raw"]["recall_at_k"]:
        flags.append("hybrid_below_raw")
    if fixture["packs"]["context"]["traceability"] < 0.66:
        flags.append("context_traceability_low")
    return flags


def _retrieval_actions(fixture: dict[str, Any]) -> list[str]:
    actions = []
    hybrid = fixture["tracks"]["hybrid"]
    raw = fixture["tracks"]["raw"]
    if not hybrid["hit"]:
        actions.append(f"{fixture['name']}: improve structured query planning or lexical gating because hybrid retrieval missed the expected record.")
    if hybrid["recall_at_k"] < raw["recall_at_k"]:
        actions.append(f"{fixture['name']}: hybrid ranking regressed below raw search; inspect merge weights and SQL/vector balance.")
    if fixture["packs"]["context"]["traceability"] < 0.66:
        actions.append(f"{fixture['name']}: context pack traceability is weak; inspect pack provenance and citation renderers.")
    return actions


def _embedding_actions(top_record_id: str | None, expected_ids: list[str], margin: float) -> list[str]:
    actions = []
    if top_record_id not in expected_ids:
        actions.append("Embedding top-1 ranking missed the expected record; compare natural, machine, and hybrid projection text.")
    if margin < 0.05:
        actions.append("Embedding separation margin is weak; benchmark alternate embedding models or retrieval projections before promotion.")
    return actions


def _long_context_flags(expected_hit: bool, prompt_contains: bool, summary_contains: bool, prompt_tokens: int, records_tokens: int) -> list[str]:
    flags = []
    if not expected_hit:
        flags.append("anchor_miss")
    if not prompt_contains:
        flags.append("prompt_missing_signal")
    if not summary_contains:
        flags.append("summary_missing_signal")
    if prompt_tokens > records_tokens:
        flags.append("prompt_bloat")
    return flags


def _long_context_actions(expected_hit: bool, prompt_contains: bool, summary_contains: bool, prompt_tokens: int, records_tokens: int) -> list[str]:
    actions = []
    if not expected_hit:
        actions.append("Long-context retrieval missed an anchor; improve segmentation, lexical gating, or retrieval planning for large histories.")
    if not prompt_contains or not summary_contains:
        actions.append("Long-context views dropped required evidence; tighten prompt/summary renderers so critical facts survive compression.")
    if prompt_tokens > records_tokens:
        actions.append("Prompt-ready context is larger than the exact records payload; tune projection rules to reduce prompt bloat.")
    return actions


def _agent_task_flags(
    expected_hit: bool,
    prompt_contains: bool,
    summary_contains: bool,
    evidence_contains: bool,
    records_contain: bool,
    prompt_tokens: int,
    records_tokens: int,
) -> list[str]:
    flags = []
    if not expected_hit:
        flags.append("task_retrieval_miss")
    if not prompt_contains:
        flags.append("task_prompt_missing_signal")
    if not summary_contains:
        flags.append("task_summary_missing_signal")
    if not evidence_contains:
        flags.append("task_evidence_missing_citation")
    if not records_contain:
        flags.append("task_records_missing_exact_payload")
    if prompt_tokens > records_tokens:
        flags.append("task_prompt_bloat")
    return flags


def _agent_task_actions(
    expected_hit: bool,
    prompt_contains: bool,
    summary_contains: bool,
    evidence_contains: bool,
    records_contain: bool,
    prompt_tokens: int,
    records_tokens: int,
    prompt_lossless_savings: float,
) -> list[str]:
    actions = []
    if not expected_hit:
        actions.append("Agent task retrieval missed the expected record; improve retrieval plan selection for operator tasks.")
    if not (prompt_contains and summary_contains and evidence_contains and records_contain):
        actions.append("One or more agent-facing views dropped required signal; align context renderers before using them as the default agent surface.")
    if prompt_tokens > records_tokens:
        actions.append("Prompt view is more expensive than records view; tighten prompt projection and benchmark token savings again.")
    if prompt_lossless_savings < 0.10:
        actions.append("Prompt compression headroom is weak; add reversible projection rules before claiming machine-efficiency gains for agent contexts.")
    return actions

def _render_key_metrics(family_name: str, summary: dict[str, Any]) -> str:
    if family_name == "lossless":
        return f"avg_savings={float(summary.get('avg_token_savings', 0.0)):.1%}"
    if family_name == "retrieval":
        return f"hybrid_recall={float(summary.get('hybrid_recall_at_k', 0.0)):.1%}"
    if family_name == "embedding":
        return f"avg_margin={float(summary.get('avg_margin', 0.0)):.3f}"
    if family_name == "long_context":
        return f"prompt_savings={float(summary.get('avg_prompt_token_savings_vs_records', 0.0)):.1%}"
    if family_name == "persistence":
        return f"durability={float(summary.get('durability_rate', 0.0)):.1%}"
    if family_name == "agent_tasks":
        return f"task_success={float(summary.get('task_success_rate', 0.0)):.1%}"
    return "n/a"


def _ndcg_at_k(ranked_ids: list[str], expected_ids: list[str]) -> float:
    if not ranked_ids or not expected_ids:
        return 0.0
    gains = []
    for rank, record_id in enumerate(ranked_ids, start=1):
        if record_id in expected_ids:
            gains.append(1.0 / _log2(rank + 1))
    ideal = [1.0 / _log2(rank + 1) for rank in range(1, min(len(expected_ids), len(ranked_ids)) + 1)]
    ideal_dcg = sum(ideal)
    return round(sum(gains) / ideal_dcg, 6) if ideal_dcg else 0.0


def _log2(value: int) -> float:
    import math

    return math.log2(value)


def _savings_ratio(original: int, compressed: int) -> float:
    if original <= 0:
        return 0.0
    return 1.0 - (compressed / original)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _git_sha() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None
    return result.stdout.strip() or None


def _average(values) -> float:
    numeric = [float(value) for value in values if isinstance(value, (int, float))]
    if not numeric:
        return 0.0
    return round(sum(numeric) / len(numeric), 6)


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def _percentile(values: list[float], percentile: float) -> float:
    numeric = sorted(float(value) for value in values if isinstance(value, (int, float)))
    if not numeric:
        return 0.0
    index = int(round((len(numeric) - 1) * percentile))
    return round(numeric[index], 6)


def _unique_actions(action_groups) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for group in action_groups:
        for action in group:
            if action and action not in seen:
                seen.add(action)
                output.append(action)
    return output










def _cleanup_temp_db(base_path: Path) -> None:
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(base_path) + suffix)
        if candidate.exists():
            try:
                candidate.unlink()
            except PermissionError:
                pass

