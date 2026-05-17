"""LoCoMo benchmark runner for SEAM.

Usage:
    python -m benchmarks.external.locomo.run --quickstart
    python -m benchmarks.external.locomo.run --dataset /path/to/locomo.json --output run.json
    python -m benchmarks.external.locomo.run --dataset /path/to/locomo.json --limit 20 --adapter seam

When --quickstart is passed, loads the quickstart fixture and runs with the SEAM adapter.
When --dataset is passed, loads from the given path.
"""

from __future__ import annotations

import argparse
import json
import sys

from benchmarks.external.common.dataset import load_locomo_cases, load_quickstart_cases
from benchmarks.external.common.runner import run_benchmark
from benchmarks.external.locomo.adapters.seam import SeamLocomoAdapter


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
        choices=["seam"],
        default="seam",
        help="Which adapter to use (default: seam)",
    )
    args = parser.parse_args()

    if not args.quickstart and not args.dataset:
        parser.error("Either --quickstart or --dataset is required.")
    if args.quickstart and args.dataset:
        parser.error("Cannot specify both --quickstart and --dataset.")

    # Load cases
    if args.quickstart:
        cases = load_quickstart_cases()
        source = "quickstart"
    else:
        cases = load_locomo_cases(args.dataset)
        source = args.dataset

    # Apply limit
    if args.limit is not None:
        cases = cases[: args.limit]

    # Build adapter
    if args.adapter == "seam":
        adapter = SeamLocomoAdapter()
    else:
        raise ValueError(f"Unknown adapter: {args.adapter}")

    # Run benchmark
    report = run_benchmark(
        adapter=adapter,
        cases=cases,
        dataset_source=source,
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
