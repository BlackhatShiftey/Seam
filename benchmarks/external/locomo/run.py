"""LoCoMo benchmark runner for SEAM.

Usage:
    python -m benchmarks.external.locomo.run --quickstart
    python -m benchmarks.external.locomo.run --dataset-path /path/to/locomo.json --dry-run
    python -m benchmarks.external.locomo.run --dataset-path /path/to/locomo.json --output run.json
    python -m benchmarks.external.locomo.run --dataset-path /path/to/locomo.json --limit 20 --adapter seam

When --quickstart is passed, loads the quickstart fixture and runs with the SEAM adapter.
When --dataset-path is passed, loads from the given path.
--dry-run validates the dataset and prints counts without executing the judge or adapter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from benchmarks.external.common.dataset import load_locomo_cases, load_quickstart_cases
from benchmarks.external.common.judge import build_judge
from benchmarks.external.common.runner import (
    run_benchmark_grouped,
    run_benchmark_grouped_parallel,
)


def build_adapter(name: str, answerer: str | None = None, answerer_model: str | None = None):
    """Lazy-import factory so SEAM-only runs don't require Mem0/Zep installed."""
    if name == "seam":
        from benchmarks.external.locomo.adapters.seam import SeamLocomoAdapter

        return SeamLocomoAdapter(answerer=answerer, answerer_model=answerer_model)
    if name == "mem0":
        from benchmarks.external.locomo.adapters.mem0 import Mem0LocomoAdapter

        return Mem0LocomoAdapter()
    if name == "zep":
        from benchmarks.external.locomo.adapters.zep import ZepLocomoAdapter

        return ZepLocomoAdapter()
    raise ValueError(f"unknown adapter {name!r}")


def _fixture_hash(cases) -> str:
    """Deterministic hash of the case definitions (questions + gold answers)."""
    payload = json.dumps(
        [{"case_id": c.case_id, "question": c.question, "gold_answer": c.gold_answer, "category": c.category}
         for c in cases],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dry_run_report(cases, dataset_path, judge_name):
    """Print case counts, category breakdown, and fixture hash without running anything."""
    category_counts = Counter(c.category for c in cases)
    report = {
        "dataset_path": str(dataset_path),
        "case_count": len(cases),
        "categories": dict(category_counts),
        "fixture_hash": _fixture_hash(cases),
        "estimated_judge_calls": len(cases) if judge_name and judge_name not in ("none", "stub") else 0,
        "judge": judge_name or "none",
        "mode": "dry-run",
    }
    return report


LOCOMO_NAMED_CATEGORIES = {"single-hop", "multi-hop", "open-domain", "temporal"}


def _validate_locomo_categories(cases) -> list[str]:
    """Validate LoCoMo category coverage. Synthetic fixtures may use numeric
    categories; full LoCoMo releases use the four named categories. The
    validator warns when named categories are missing but only fails when
    zero categories are found."""
    issues = []
    cats_present = {c.category for c in cases if c.category is not None}
    if len(cases) == 0:
        issues.append("No cases found in dataset")
        return issues
    if not cats_present:
        issues.append("No categories found in any case")
        return issues
    named_present = cats_present & LOCOMO_NAMED_CATEGORIES
    numeric_present = {c for c in cats_present if str(c).isdigit()}
    if named_present and len(named_present) < 4:
        issues.append(
            f"Only {len(named_present)}/4 named LoCoMo categories present: {sorted(named_present)}. "
            f"Missing: {sorted(LOCOMO_NAMED_CATEGORIES - named_present)}"
        )
    elif not named_present and not numeric_present:
        issues.append(
            f"Categories present ({sorted(cats_present)}) are neither named LoCoMo categories "
            f"nor numeric synthetic IDs"
        )
    return issues


def _locomo_scope_id(case) -> str:
    return case.case_id.split("::", 1)[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="LoCoMo benchmark runner for SEAM")
    parser.add_argument(
        "--quickstart",
        action="store_true",
        help="Use the bundled quickstart fixture",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Path to a LoCoMo JSON file (deprecated alias for --dataset-path)",
    )
    parser.add_argument(
        "--dataset-path",
        type=str,
        default=None,
        help="Path to a LoCoMo JSON file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Write JSON report to this path (prints to stdout if omitted)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of cases",
    )
    parser.add_argument(
        "--adapter",
        choices=["seam", "mem0", "zep"],
        default="seam",
        help="Which adapter to use (default: seam)",
    )
    parser.add_argument(
        "--judge",
        default=None,
        choices=["none", "stub", "claude", "openai"],
        help="LLM judge in addition to string-match scoring",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Override the default judge model id",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate dataset and print counts without executing the benchmark",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of independent case workers for full runs",
    )
    parser.add_argument(
        "--answerer",
        choices=["none", "openai", "claude"],
        default="none",
        help="Generate a short answer from retrieved context (default: none)",
    )
    parser.add_argument(
        "--answerer-model",
        default=None,
        help="Override the default answerer model id",
    )
    args = parser.parse_args()

    dataset_path = args.dataset_path or args.dataset

    if not args.quickstart and not dataset_path:
        parser.error("Either --quickstart or --dataset-path is required.")
    if args.quickstart and dataset_path:
        parser.error("Cannot specify both --quickstart and --dataset-path.")

    # Load cases
    if args.quickstart:
        cases = load_quickstart_cases()
        source = "quickstart"
    else:
        if not Path(dataset_path).exists():
            print(f"ERROR: dataset not found: {dataset_path}", file=sys.stderr)
            raise SystemExit(1)
        cases = load_locomo_cases(dataset_path)
        source = str(dataset_path)

    # Apply limit
    if args.limit is not None:
        cases = cases[: args.limit]

    # Dry-run mode: validate and report, no execution
    if args.dry_run:
        issues = _validate_locomo_categories(cases)
        report = _dry_run_report(cases, source, args.judge)
        report["validation_issues"] = issues
        report["valid"] = len(issues) == 0
        print(json.dumps(report, indent=2))
        raise SystemExit(0 if report["valid"] else 1)

    answerer = None if args.answerer == "none" else args.answerer

    # Run benchmark
    if args.workers > 1:
        report = run_benchmark_grouped_parallel(
            adapter_factory=lambda: build_adapter(args.adapter, answerer=answerer, answerer_model=args.answerer_model),
            adapter_name=args.adapter,
            cases=cases,
            scope_id=_locomo_scope_id,
            dataset_source=source,
            judge_factory=(
                lambda: build_judge(args.judge, model=args.judge_model)
                if args.judge is not None else None
            ),
            workers=args.workers,
        )
    else:
        adapter = build_adapter(args.adapter, answerer=answerer, answerer_model=args.answerer_model)
        judge = build_judge(args.judge, model=args.judge_model)
        report = run_benchmark_grouped(
            adapter=adapter,
            cases=cases,
            scope_id=_locomo_scope_id,
            dataset_source=source,
            judge=judge,
        )

    # Output
    report_json = json.dumps(report, indent=2, default=str)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report_json)
            f.write("\n")
        print(f"Report written to {args.output}")
    else:
        print(report_json)


if __name__ == "__main__":
    main()
