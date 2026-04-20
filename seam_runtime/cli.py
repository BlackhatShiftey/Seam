from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from importlib.util import find_spec
from pathlib import Path

from experimental.retrieval_orchestrator import RetrievalOrchestrator
from .benchmarks import BENCHMARK_SUITES, render_benchmark_pretty, render_benchmark_verification_pretty
from .context_views import CONTEXT_VIEWS, build_context_payload, render_context_pretty
from .dashboard import run_dashboard
from .installer import default_runtime_db_path
from .lossless import (
    LOSSLESS_CODECS,
    LOSSLESS_TRANSFORMS,
    TOKENIZER_CHOICES,
    benchmark_text_lossless,
    compress_text_lossless,
    decompress_text_lossless,
    render_lossless_benchmark_pretty,
)
from .mirl import IRBatch
from .runtime import SeamRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEAM v1 memory compiler/runtime")
    parser.add_argument("--db", default=default_runtime_db_path(), help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Store raw text from a file or stdin")
    ingest_parser.add_argument("source")

    lossless_compress_parser = subparsers.add_parser("lossless-compress", aliases=["compress-doc"], help="Losslessly compress a document into SEAM machine text")
    lossless_compress_parser.add_argument("source")
    lossless_compress_parser.add_argument("--codec", choices=["auto", *LOSSLESS_CODECS], default="auto")
    lossless_compress_parser.add_argument("--transform", choices=["auto", *LOSSLESS_TRANSFORMS], default="auto")
    lossless_compress_parser.add_argument("--tokenizer", choices=TOKENIZER_CHOICES, default="auto")
    lossless_compress_parser.add_argument("--output")
    lossless_compress_parser.add_argument("--format", choices=["machine", "json"], default="machine")

    lossless_decompress_parser = subparsers.add_parser("lossless-decompress", aliases=["decompress-doc"], help="Restore a SEAM lossless document back to exact text")
    lossless_decompress_parser.add_argument("source")
    lossless_decompress_parser.add_argument("--output")

    lossless_benchmark_parser = subparsers.add_parser("lossless-benchmark", aliases=["benchmark-doc"], help="Benchmark lossless document compression and roundtrip recovery")
    lossless_benchmark_parser.add_argument("source")
    lossless_benchmark_parser.add_argument("--codec", choices=["auto", *LOSSLESS_CODECS], default="auto")
    lossless_benchmark_parser.add_argument("--transform", choices=["auto", *LOSSLESS_TRANSFORMS], default="auto")
    lossless_benchmark_parser.add_argument("--tokenizer", choices=TOKENIZER_CHOICES, default="auto")
    lossless_benchmark_parser.add_argument("--min-savings", type=float, default=0.30)
    lossless_benchmark_parser.add_argument("--compressed-output")
    lossless_benchmark_parser.add_argument("--roundtrip-output")
    lossless_benchmark_parser.add_argument("--log-output")
    lossless_benchmark_parser.add_argument("--show-machine", action="store_true")
    lossless_benchmark_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    demo_parser = subparsers.add_parser("demo", help="Run operator-facing SEAM demos")
    demo_subparsers = demo_parser.add_subparsers(dest="demo_command", required=True)
    demo_lossless_parser = demo_subparsers.add_parser("lossless", help="Compress or rebuild a lossless SEAM-LX document demo")
    demo_lossless_parser.add_argument("source")
    demo_lossless_parser.add_argument("output")
    demo_lossless_parser.add_argument("--rebuild", action="store_true", help="Treat the source as machine text and rebuild the original document")
    demo_lossless_parser.add_argument("--codec", choices=["auto", *LOSSLESS_CODECS], default="auto")
    demo_lossless_parser.add_argument("--transform", choices=["auto", *LOSSLESS_TRANSFORMS], default="auto")
    demo_lossless_parser.add_argument("--tokenizer", choices=TOKENIZER_CHOICES, default="auto")
    demo_lossless_parser.add_argument("--min-savings", type=float, default=0.30)
    demo_lossless_parser.add_argument("--show-machine", action="store_true")
    demo_lossless_parser.add_argument("--log-output")
    demo_lossless_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")
    
    benchmark_parser = subparsers.add_parser("benchmark", help="Run or inspect SEAM glassbox benchmark suites")
    benchmark_subparsers = benchmark_parser.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run_parser = benchmark_subparsers.add_parser("run", help="Run benchmark suites")
    benchmark_run_parser.add_argument("suite", nargs="?", choices=["all", *BENCHMARK_SUITES], default="all")
    benchmark_run_parser.add_argument("--tokenizer", choices=TOKENIZER_CHOICES, default="auto")
    benchmark_run_parser.add_argument("--min-savings", type=float, default=0.30)
    benchmark_run_parser.add_argument("--persist", action="store_true")
    benchmark_run_parser.add_argument("--output")
    benchmark_run_parser.add_argument("--include-machine-text", action="store_true")
    benchmark_run_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    benchmark_show_parser = benchmark_subparsers.add_parser("show", help="Show a persisted benchmark run")
    benchmark_show_parser.add_argument("run_id", nargs="?", default="latest")
    benchmark_show_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    benchmark_verify_parser = benchmark_subparsers.add_parser("verify", help="Verify a benchmark bundle hash and case hashes")
    benchmark_verify_parser.add_argument("bundle")
    benchmark_verify_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    compile_nl_parser = subparsers.add_parser("compile-nl", help="Compile natural language into MIRL")
    compile_nl_parser.add_argument("text")
    compile_nl_parser.add_argument("--source-ref", default="local://input")
    compile_nl_parser.add_argument("--persist", action="store_true")
    _add_rag_sync_args(compile_nl_parser)

    compile_dsl_parser = subparsers.add_parser("compile-dsl", help="Compile SEAM DSL into MIRL")
    compile_dsl_parser.add_argument("file")
    compile_dsl_parser.add_argument("--persist", action="store_true")
    _add_rag_sync_args(compile_dsl_parser)

    verify_parser = subparsers.add_parser("verify", help="Verify MIRL from a text file")
    verify_parser.add_argument("file")

    persist_parser = subparsers.add_parser("persist", help="Persist MIRL from a text file")
    persist_parser.add_argument("file")
    _add_rag_sync_args(persist_parser)

    search_parser = subparsers.add_parser("search", help="Combined search over persisted MIRL")
    search_parser.add_argument("query")
    search_parser.add_argument("--scope")
    search_parser.add_argument("--budget", type=int, default=5)

    plan_parser = subparsers.add_parser("plan", aliases=["hybrid-plan"], help="Plan a retrieval run")
    plan_parser.add_argument("query")
    _add_retrieval_common_args(plan_parser, include_backend=False)

    retrieve_parser = subparsers.add_parser("retrieve", aliases=["hybrid-search"], help="Run retrieval and rank results")
    retrieve_parser.add_argument("query")
    _add_retrieval_common_args(retrieve_parser)

    compare_parser = subparsers.add_parser("compare", aliases=["hybrid-compare"], help="Compare basic search with retrieval ranking")
    compare_parser.add_argument("query")
    _add_retrieval_common_args(compare_parser)

    index_parser = subparsers.add_parser("index", aliases=["rag-sync"], help="Sync persisted records into the active vector indexes")
    index_parser.add_argument("--record-ids", default="")
    index_parser.add_argument("--scope")
    index_parser.add_argument("--namespace")
    index_parser.add_argument("--format", choices=["pretty", "json", "ids"], default="pretty")
    index_parser.add_argument("--vector-backend", "--semantic-backend", dest="vector_backend", choices=["seam", "chroma"], default="seam")
    index_parser.add_argument("--vector-path", "--chroma-path", dest="vector_path", default=".seam_chroma")
    index_parser.add_argument("--vector-collection", "--chroma-collection", dest="vector_collection", default="seam_hybrid")

    context_parser = subparsers.add_parser("context", aliases=["rag-search"], help="Retrieve context for generation")
    context_parser.add_argument("query")
    context_parser.add_argument("--scope")
    context_parser.add_argument("--budget", type=int, default=5)
    context_parser.add_argument("--pack-budget", type=int, default=512)
    context_parser.add_argument("--lens", default="rag")
    context_parser.add_argument("--mode", choices=["context", "narrative", "exact"], default="context")
    context_parser.add_argument("--view", choices=CONTEXT_VIEWS, default="pack")
    context_parser.add_argument("--format", choices=["pretty", "json", "ids"], default="pretty")
    context_parser.add_argument("--trace", action="store_true")
    context_parser.add_argument("--vector-backend", "--semantic-backend", dest="vector_backend", choices=["seam", "chroma"], default="seam")
    context_parser.add_argument("--vector-path", "--chroma-path", dest="vector_path", default=".seam_chroma")
    context_parser.add_argument("--vector-collection", "--chroma-collection", dest="vector_collection", default="seam_hybrid")

    dashboard_parser = subparsers.add_parser("dashboard", help="Launch the runtime-connected terminal dashboard")
    dashboard_parser.add_argument("--snapshot", action="store_true", help="Render one dashboard frame and exit")
    dashboard_parser.add_argument("--run", dest="dashboard_commands", action="append", default=[], help="Run a dashboard command non-interactively")
    dashboard_parser.add_argument("--no-clear", action="store_true", help="Do not clear the terminal between renders")
    dashboard_parser.add_argument("--vector-backend", "--semantic-backend", dest="vector_backend", choices=["seam", "chroma"], default="seam")
    dashboard_parser.add_argument("--vector-path", "--chroma-path", dest="vector_path", default=".seam_chroma")
    dashboard_parser.add_argument("--vector-collection", "--chroma-collection", dest="vector_collection", default="seam_hybrid")

    pack_parser = subparsers.add_parser("pack", help="Build a pack from persisted record ids")
    pack_parser.add_argument("record_ids")
    pack_parser.add_argument("--lens", default="general")
    pack_parser.add_argument("--budget", type=int, default=512)
    pack_parser.add_argument("--mode", choices=["exact", "context", "narrative"], default="context")

    decompile_parser = subparsers.add_parser("decompile", help="Decompile persisted record ids")
    decompile_parser.add_argument("record_ids")
    decompile_parser.add_argument("--mode", default="expanded")

    trace_parser = subparsers.add_parser("trace", help="Trace provenance for a persisted object id")
    trace_parser.add_argument("obj_id")

    reconcile_parser = subparsers.add_parser("reconcile", help="Reconcile claims and emit relation/state updates")
    reconcile_parser.add_argument("--record-ids", default="")

    transpile_parser = subparsers.add_parser("transpile", help="Transpile MIRL workflows to Python")
    transpile_parser.add_argument("record_ids")
    transpile_parser.add_argument("--target", default="python")

    reindex_parser = subparsers.add_parser("reindex", help="Rebuild vector index entries")
    reindex_parser.add_argument("--record-ids", default="")

    promote_symbols_parser = subparsers.add_parser("promote-symbols", help="Propose and persist machine-only symbols")
    promote_symbols_parser.add_argument("--record-ids", default="")
    promote_symbols_parser.add_argument("--min-frequency", type=int, default=2)

    export_symbols_parser = subparsers.add_parser("export-symbols", help="Export symbol nursery markdown for audit/safety")
    export_symbols_parser.add_argument("--namespace")
    export_symbols_parser.add_argument("--output")

    doctor_parser = subparsers.add_parser("doctor", help="Check SEAM install health and run a lightweight smoke test")
    doctor_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    subparsers.add_parser("stats", help="Run retrieval benchmark summary")
    return parser


def run_cli(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in {"lossless-compress", "compress-doc"}:
        text = _read_text_source(args.source)
        artifact = compress_text_lossless(text, codec=args.codec, transform=args.transform, tokenizer=args.tokenizer)
        if args.output:
            _write_text_output(args.output, artifact.machine_text)
        if args.format == "json":
            print(json.dumps(artifact.to_dict(include_machine_text=True), indent=2))
            return
        print(artifact.machine_text)
        return
    if args.command in {"lossless-decompress", "decompress-doc"}:
        machine_text = _read_text_source(args.source)
        text = decompress_text_lossless(machine_text)
        if args.output:
            _write_text_output(args.output, text)
            print(args.output)
            return
        print(text)
        return
    if args.command in {"lossless-benchmark", "benchmark-doc"}:
        text = _read_text_source(args.source)
        result = benchmark_text_lossless(
            text,
            codec=args.codec,
            transform=args.transform,
            min_token_savings=args.min_savings,
            tokenizer=args.tokenizer,
        )
        if args.compressed_output:
            _write_text_output(args.compressed_output, result.artifact.machine_text)
        if args.roundtrip_output:
            _write_text_output(args.roundtrip_output, result.roundtrip_text)
        payload = result.to_dict(include_machine_text=args.show_machine)
        if args.log_output:
            _write_text_output(args.log_output, json.dumps(payload, indent=2))
        if args.format == "json":
            print(json.dumps(payload, indent=2))
            return
        print(render_lossless_benchmark_pretty(payload))
        return
    if args.command == "demo" and args.demo_command == "lossless":
        if args.rebuild:
            rebuilt_text = decompress_text_lossless(_read_text_source(args.source))
            _write_text_output(args.output, rebuilt_text)
            payload = {
                "mode": "rebuild",
                "source": args.source,
                "output": args.output,
                "status": "PASS",
                "sha256": hashlib.sha256(rebuilt_text.encode("utf-8")).hexdigest(),
                "output_bytes": len(rebuilt_text.encode("utf-8")),
                "integrity": "verified against embedded SEAM-LX/1 hash",
            }
            if args.format == "json":
                print(json.dumps(payload, indent=2))
                return
            print(_render_lossless_demo_result(payload))
            return

        text = _read_text_source(args.source)
        result = benchmark_text_lossless(
            text,
            codec=args.codec,
            transform=args.transform,
            min_token_savings=args.min_savings,
            tokenizer=args.tokenizer,
        )
        _write_text_output(args.output, result.artifact.machine_text)
        payload = result.to_dict(include_machine_text=args.show_machine)
        payload["mode"] = "compress"
        payload["source"] = args.source
        payload["output"] = args.output
        if args.log_output:
            payload["log_output"] = args.log_output
            _write_text_output(args.log_output, json.dumps(payload, indent=2))
        if args.format == "json":
            print(json.dumps(payload, indent=2))
            return
        print(_render_lossless_demo_result(payload))
        return

    runtime = SeamRuntime(args.db)

    if args.command == "ingest":
        text = _read_text_source(args.source)
        print(runtime.compile_nl(text, source_ref=args.source).to_text())
        return
    if args.command == "compile-nl":
        batch = runtime.compile_nl(args.text, source_ref=args.source_ref)
        if args.persist or args.sync_index:
            runtime.persist_ir(batch)
            if args.sync_index:
                orchestrator = _build_retrieval_orchestrator(runtime, args)
                orchestrator.sync_persistent_indexes(record_ids=[record.id for record in batch.records])
        print(batch.to_text())
        return
    if args.command == "compile-dsl":
        batch = runtime.compile_dsl(Path(args.file).read_text(encoding="utf-8"))
        if args.persist or args.sync_index:
            runtime.persist_ir(batch)
            if args.sync_index:
                orchestrator = _build_retrieval_orchestrator(runtime, args)
                orchestrator.sync_persistent_indexes(record_ids=[record.id for record in batch.records])
        print(batch.to_text())
        return
    if args.command == "verify":
        batch = IRBatch.from_text(Path(args.file).read_text(encoding="utf-8"))
        print(json.dumps(runtime.verify_ir(batch).to_dict(), indent=2))
        return
    if args.command == "persist":
        batch = IRBatch.from_text(Path(args.file).read_text(encoding="utf-8"))
        report = runtime.persist_ir(batch).to_dict()
        if args.sync_index:
            orchestrator = _build_retrieval_orchestrator(runtime, args)
            report["index"] = orchestrator.sync_persistent_indexes(record_ids=[record["id"] for record in batch.to_json()])
        print(json.dumps(report, indent=2))
        return
    if args.command == "search":
        print(json.dumps(runtime.search_ir(args.query, scope=args.scope, budget=args.budget).to_dict(), indent=2))
        return
    if args.command in {"plan", "hybrid-plan"}:
        orchestrator = _build_retrieval_orchestrator(runtime, args)
        plan = orchestrator.plan(args.query, scope=args.scope, budget=args.budget)
        _print_retrieval_output(plan.to_dict(), output_format=args.format, renderer=_render_plan_pretty)
        return
    if args.command in {"retrieve", "hybrid-search"}:
        orchestrator = _build_retrieval_orchestrator(runtime, args)
        result = orchestrator.search(args.query, scope=args.scope, budget=args.budget, include_trace=args.trace)
        _print_retrieval_output(result.to_dict(), output_format=args.format, renderer=_render_search_pretty)
        return
    if args.command in {"compare", "hybrid-compare"}:
        orchestrator = _build_retrieval_orchestrator(runtime, args)
        search_result = runtime.search_ir(args.query, scope=args.scope, budget=args.budget).to_dict()
        retrieved = orchestrator.search(args.query, scope=args.scope, budget=args.budget, include_trace=args.trace).to_dict()
        _print_retrieval_output({"search": search_result, "retrieve": retrieved}, output_format=args.format, renderer=_render_compare_pretty)
        return
    if args.command in {"index", "rag-sync"}:
        orchestrator = _build_retrieval_orchestrator(runtime, args)
        payload = orchestrator.sync_persistent_indexes(
            record_ids=_split_ids(args.record_ids) if args.record_ids else None,
            scope=args.scope,
            namespace=args.namespace,
        )
        _print_retrieval_output(payload, output_format=args.format, renderer=_render_rag_sync_pretty)
        return
    if args.command in {"context", "rag-search"}:
        orchestrator = _build_retrieval_orchestrator(runtime, args)
        payload = build_context_payload(
            orchestrator.rag(
                args.query,
                scope=args.scope,
                budget=args.budget,
                pack_budget=args.pack_budget,
                lens=args.lens,
                mode=args.mode,
                include_trace=args.trace,
            ).to_dict(),
            view=args.view,
        )
        _print_retrieval_output(payload, output_format=args.format, renderer=render_context_pretty)
        return
    if args.command == "dashboard":
        run_dashboard(
            runtime,
            vector_backend=args.vector_backend,
            vector_path=args.vector_path,
            vector_collection=args.vector_collection,
            snapshot=args.snapshot,
            commands=args.dashboard_commands,
            no_clear=args.no_clear,
        )
        return
    if args.command == "pack":
        print(json.dumps(runtime.pack_ir(record_ids=_split_ids(args.record_ids), lens=args.lens, budget=args.budget, mode=args.mode).to_dict(), indent=2))
        return
    if args.command == "decompile":
        print(runtime.decompile_ir(record_ids=_split_ids(args.record_ids), mode=args.mode))
        return
    if args.command == "trace":
        print(json.dumps(runtime.trace(args.obj_id).to_dict(), indent=2))
        return
    if args.command == "reconcile":
        record_ids = _split_ids(args.record_ids) if args.record_ids else None
        print(json.dumps(runtime.reconcile_ir(record_ids=record_ids).to_dict(), indent=2))
        return
    if args.command == "transpile":
        print(json.dumps(runtime.transpile_ir(record_ids=_split_ids(args.record_ids), target=args.target).to_dict(), indent=2))
        return
    if args.command == "reindex":
        record_ids = _split_ids(args.record_ids) if args.record_ids else None
        print(json.dumps(runtime.reindex_vectors(record_ids=record_ids), indent=2))
        return
    if args.command == "promote-symbols":
        record_ids = _split_ids(args.record_ids) if args.record_ids else None
        print(json.dumps(runtime.promote_symbols(record_ids=record_ids, min_frequency=args.min_frequency).to_dict(), indent=2))
        return
    if args.command == "export-symbols":
        print(runtime.export_symbols(namespace=args.namespace, output_path=args.output))
        return
    if args.command == "doctor":
        payload = _build_doctor_report()
        if args.format == "json":
            print(json.dumps(payload, indent=2))
            return
        print(_render_doctor_report(payload))
        return
    if args.command == "benchmark":
        if args.benchmark_command == "run":
            payload = runtime.run_benchmark_suite(
                suite=args.suite,
                tokenizer=args.tokenizer,
                min_token_savings=args.min_savings,
                persist=args.persist,
                include_machine_text=args.include_machine_text,
                bundle_path=args.output,
            )
            if args.format == "json":
                print(json.dumps(payload, indent=2))
                return
            print(render_benchmark_pretty(payload))
            return
        if args.benchmark_command == "show":
            if args.run_id == "latest":
                runs = runtime.list_benchmark_runs(limit=1)
                if not runs:
                    raise SystemExit("No benchmark runs have been persisted yet.")
                run_id = str(runs[0]["run_id"])
            else:
                run_id = args.run_id
            payload = runtime.read_benchmark_run(run_id)
            if not payload:
                raise SystemExit(f"Benchmark run not found: {run_id}")
            if args.format == "json":
                print(json.dumps(payload, indent=2))
                return
            print(render_benchmark_pretty(payload))
            return
        if args.benchmark_command == "verify":
            payload = runtime.verify_benchmark_bundle(args.bundle)
            if args.format == "json":
                print(json.dumps(payload, indent=2))
                return
            print(render_benchmark_verification_pretty(payload))
            return

        print(json.dumps(runtime.run_retrieval_benchmark(), indent=2))


def _split_ids(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _read_text_source(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_bytes().decode("utf-8")


def _write_text_output(target: str, text: str) -> None:
    if target == "-":
        print(text)
        return
    Path(target).write_bytes(text.encode("utf-8"))


def _render_lossless_demo_result(payload: dict[str, object]) -> str:
    if payload.get("mode") == "rebuild":
        return "\n".join(
            [
                "Demo: REBUILD PASS",
                f"Source machine text: {payload.get('source')}",
                f"Rebuilt output: {payload.get('output')}",
                f"Rebuilt bytes: {payload.get('output_bytes')}",
                f"SHA256: {payload.get('sha256')}",
                f"Integrity: {payload.get('integrity')}",
            ]
        )

    lines = [
        f"Demo: {'PASS' if payload.get('passed') else 'FAIL'}",
        f"Source document: {payload.get('source')}",
        f"Compressed output: {payload.get('output')}",
    ]
    if payload.get("log_output"):
        lines.append(f"Log output: {payload.get('log_output')}")
    lines.extend(["", render_lossless_benchmark_pretty(payload)])
    return "\n".join(lines)


def _check_pgvector(dsn: str | None) -> dict[str, object]:
    if not dsn:
        return {"configured": False}
    try:
        import psycopg
        conn = psycopg.connect(dsn)
        conn.close()
        return {"configured": True, "reachable": True}
    except Exception as exc:
        return {"configured": True, "reachable": False, "error": str(exc)}


def _build_doctor_report() -> dict[str, object]:
    runtime = SeamRuntime(":memory:")
    batch = runtime.compile_nl("SEAM doctor smoke test for durable local memory.")
    smoke_ok = bool(batch.records)
    lossless_result = benchmark_text_lossless(
        "\n".join(["SEAM preserves exact context while compressing token usage for lossless recovery."] * 12),
        min_token_savings=0.30,
    )
    pgvector_dsn = os.environ.get("SEAM_PGVECTOR_DSN")
    dependencies = {
        "rich": find_spec("rich") is not None,
        "chromadb": find_spec("chromadb") is not None,
        "tiktoken": find_spec("tiktoken") is not None,
        "psycopg": find_spec("psycopg") is not None,
        "sentence_transformers": find_spec("sentence_transformers") is not None,
    }
    required_dependencies = ["rich", "chromadb", "tiktoken"]
    missing_required = [name for name in required_dependencies if not dependencies.get(name)]
    deps_ok = not missing_required
    status = "PASS" if smoke_ok and lossless_result.roundtrip_match and deps_ok else "FAIL"
    return {
        "status": status,
        "python": sys.version.split()[0],
        "db_mode": "in-memory",
        "default_db_path": default_runtime_db_path(),
        "smoke_compile": {
            "status": "PASS" if smoke_ok else "FAIL",
            "record_count": len(batch.records),
        },
        "lossless": {
            "status": "PASS" if lossless_result.roundtrip_match else "FAIL",
            "token_estimator": lossless_result.artifact.token_estimator,
            "token_savings_ratio": round(lossless_result.artifact.token_savings_ratio, 6),
        },
        "pgvector": _check_pgvector(pgvector_dsn),
        "dependencies": dependencies,
        "required_dependencies": required_dependencies,
        "missing_required_dependencies": missing_required,
    }


def _render_doctor_report(payload: dict[str, object]) -> str:
    dependency_lines = [
        f"- {name}: {'installed' if installed else 'missing'}"
        for name, installed in payload.get("dependencies", {}).items()
    ]
    pgvector = payload.get("pgvector", {})
    if pgvector.get("configured"):
        pg_line = f"PgVector: {'reachable' if pgvector.get('reachable') else 'configured but unreachable'}"
        if not pgvector.get("reachable") and pgvector.get("error"):
            pg_line += f" ({pgvector['error']})"
    else:
        pg_line = "PgVector: not configured (set SEAM_PGVECTOR_DSN to enable)"
    return "\n".join(
        [
            f"SEAM doctor: {payload.get('status')}",
            f"Python: {payload.get('python')}",
            f"DB mode: {payload.get('db_mode')}",
            f"Default DB: {payload.get('default_db_path')}",
            f"Compile smoke: {payload.get('smoke_compile', {}).get('status')} ({payload.get('smoke_compile', {}).get('record_count')} records)",
            (
                "Lossless smoke: "
                f"{payload.get('lossless', {}).get('status')} "
                f"({payload.get('lossless', {}).get('token_savings_ratio')} savings, "
                f"estimator={payload.get('lossless', {}).get('token_estimator')})"
            ),
            pg_line,
            (
                "Required deps: OK"
                if not payload.get("missing_required_dependencies")
                else f"Required deps: missing ({', '.join(payload.get('missing_required_dependencies', []))})"
            ),
            "Dependencies:",
            *dependency_lines,
        ]
    )


def _add_retrieval_common_args(parser: argparse.ArgumentParser, include_backend: bool = True) -> None:
    parser.add_argument("--scope")
    parser.add_argument("--budget", type=int, default=5)
    parser.add_argument("--format", choices=["pretty", "json", "ids"], default="pretty")
    parser.add_argument("--trace", action="store_true")
    if include_backend:
        parser.add_argument("--vector-backend", "--semantic-backend", dest="vector_backend", choices=["seam", "chroma"], default="seam")
        parser.add_argument("--vector-path", "--chroma-path", dest="vector_path", default=".seam_chroma")
        parser.add_argument("--vector-collection", "--chroma-collection", dest="vector_collection", default="seam_hybrid")


def _add_rag_sync_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--index", "--rag-sync", dest="sync_index", action="store_true")
    parser.add_argument("--vector-backend", "--semantic-backend", dest="vector_backend", choices=["seam", "chroma"], default="seam")
    parser.add_argument("--vector-path", "--chroma-path", dest="vector_path", default=".seam_chroma")
    parser.add_argument("--vector-collection", "--chroma-collection", dest="vector_collection", default="seam_hybrid")


def _build_retrieval_orchestrator(runtime: SeamRuntime, args: argparse.Namespace) -> RetrievalOrchestrator:
    return RetrievalOrchestrator(
        runtime,
        semantic_backend=getattr(args, "vector_backend", "seam"),
        chroma_path=getattr(args, "vector_path", ".seam_chroma"),
        chroma_collection=getattr(args, "vector_collection", "seam_hybrid"),
    )


def _print_retrieval_output(payload: dict[str, object], output_format: str, renderer) -> None:
    if output_format == "json":
        print(json.dumps(payload, indent=2))
        return
    if output_format == "ids":
        print(_render_ids(payload))
        return
    print(renderer(payload))


def _render_plan_pretty(payload: dict[str, object]) -> str:
    filters = payload.get("filters", {})
    legs = payload.get("legs", [])
    active_filters = [f"{key}={value}" for key, value in filters.items() if value not in (None, [], "")]
    lines = [
        f"Intent: {payload.get('intent')}",
        f"Query: {payload.get('query')}",
        f"Normalized: {payload.get('normalized_query') or '(none)'}",
        f"Filters: {', '.join(active_filters) if active_filters else '(none)'}",
        "Legs:",
    ]
    for leg in legs:
        lines.append(f"- {leg['name']} (limit={leg['limit']}): {leg['rationale']}")
    return "\n".join(lines)


def _render_search_pretty(payload: dict[str, object]) -> str:
    lines = [
        f"Intent: {payload.get('intent')}",
        f"Query: {payload.get('query')}",
        f"Normalized: {payload.get('normalized_query') or '(none)'}",
        "Candidates:",
    ]
    candidates = payload.get("candidates", [])
    if not candidates:
        lines.append("(none)")
    for index, candidate in enumerate(candidates, start=1):
        record = candidate["record"]
        source_text = ", ".join(f"{name}={score:.2f}" for name, score in candidate.get("sources", {}).items())
        lines.append(f"{index}. {record['id']} [{record['kind']}] score={candidate['score']:.3f} sources={source_text or '(none)'}")
        signal = _record_signal(record)
        if signal:
            lines.append(f"   {signal}")
    if payload.get("trace"):
        lines.append("Trace: included")
    return "\n".join(lines)


def _render_compare_pretty(payload: dict[str, object]) -> str:
    base_search = payload.get("search", {})
    retrieval = payload.get("retrieve", {})
    search_ids = ", ".join(candidate["record"]["id"] for candidate in base_search.get("candidates", [])) or "(none)"
    retrieval_ids = ", ".join(candidate["record"]["id"] for candidate in retrieval.get("candidates", [])) or "(none)"
    return "\n".join(
        [
            f"Query: {retrieval.get('query') or base_search.get('query')}",
            f"Search: {search_ids}",
            f"Retrieve: {retrieval_ids}",
            f"Retrieval intent: {retrieval.get('intent')}",
            "Use --format json for full scores and trace payloads.",
        ]
    )


def _render_rag_sync_pretty(payload: dict[str, object]) -> str:
    sqlite_ids = payload.get("sqlite_indexed", [])
    return "\n".join(
        [
            f"Backend: {payload.get('backend')}",
            f"SQLite indexed: {len(sqlite_ids)}",
            f"Chroma indexed: {payload.get('chroma_indexed', 0)}",
            f"Record ids: {', '.join(payload.get('record_ids', [])) or '(none)'}",
        ]
    )


def _render_ids(payload: dict[str, object]) -> str:
    if "search" in payload and "retrieve" in payload:
        search_ids = " ".join(candidate["record"]["id"] for candidate in payload["search"].get("candidates", []))
        retrieval_ids = " ".join(candidate["record"]["id"] for candidate in payload["retrieve"].get("candidates", []))
        return f"search: {search_ids}\nretrieve: {retrieval_ids}".strip()
    if "records" in payload:
        return "\n".join(payload.get("candidate_ids", []))
    if "candidates" in payload:
        return "\n".join(candidate["record"]["id"] for candidate in payload.get("candidates", []))
    if "candidate_ids" in payload:
        return "\n".join(payload.get("candidate_ids", []))
    if "legs" in payload:
        return "\n".join(leg["name"] for leg in payload.get("legs", []))
    if "record_ids" in payload:
        return "\n".join(payload.get("record_ids", []))
    return ""


def _record_signal(record: dict[str, object]) -> str:
    attrs = record.get("attrs", {})
    if "predicate" in attrs or "object" in attrs:
        return f"{attrs.get('subject', '')} {attrs.get('predicate', '')} {attrs.get('object', '')}".strip()
    if "target" in attrs:
        return f"target={attrs.get('target')}"
    return ""





