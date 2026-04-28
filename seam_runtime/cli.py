from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from importlib.util import find_spec
from pathlib import Path

from experimental.retrieval_orchestrator import RetrievalOrchestrator
from .benchmarks import (
    BENCHMARK_SUITES,
    render_benchmark_diff_pretty,
    render_benchmark_gate_pretty,
    render_benchmark_pretty,
    render_benchmark_verification_pretty,
    write_holdout_benchmark_bundle,
)
from .context_views import CONTEXT_VIEWS, build_context_payload, render_context_pretty
from .dashboard import run_dashboard
from .installer import default_runtime_db_path
from .lossless import (
    LOSSLESS_CODECS,
    LOSSLESS_TRANSFORMS,
    READABLE_GRANULARITIES,
    TOKENIZER_CHOICES,
    benchmark_text_lossless,
    compress_text_readable,
    compress_text_lossless,
    decompress_text_readable,
    decompress_text_lossless,
    query_readable_compressed,
    render_lossless_benchmark_pretty,
)
from .lx1 import decode as lx1_decode, encode as lx1_encode, token_savings_report
from .agent_memory import render_memory_index, render_memory_records
from .mirl import IRBatch
from .runtime import SeamRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEAM v1 memory compiler/runtime")
    parser.add_argument("--db", default=default_runtime_db_path(), help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Store raw text from a file or stdin")
    ingest_parser.add_argument("source")
    ingest_parser.add_argument("--persist", action="store_true", help="Persist compiled memory records and index them")
    ingest_parser.add_argument("--source-ref")
    ingest_parser.add_argument("--ns", default="local.default")
    ingest_parser.add_argument("--scope", default="thread")
    ingest_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    lossless_compress_parser = subparsers.add_parser("lossless-compress", aliases=["compress-doc"], help="Losslessly compress a document into SEAM machine text")
    lossless_compress_parser.add_argument("source")
    lossless_compress_parser.add_argument("--codec", choices=["auto", *LOSSLESS_CODECS], default="auto")
    lossless_compress_parser.add_argument("--transform", choices=["auto", *LOSSLESS_TRANSFORMS], default="auto")
    lossless_compress_parser.add_argument("--tokenizer", choices=TOKENIZER_CHOICES, default="auto")
    lossless_compress_parser.add_argument("--output")
    lossless_compress_parser.add_argument("--format", choices=["machine", "json"], default="machine")

    readable_compress_parser = subparsers.add_parser(
        "readable-compress",
        aliases=["compress-readable"],
        help="Compress text into directly readable SEAM-RC/1 machine language",
    )
    readable_compress_parser.add_argument("source")
    readable_compress_parser.add_argument("--source-ref")
    readable_compress_parser.add_argument("--granularity", choices=READABLE_GRANULARITIES, default="auto")
    readable_compress_parser.add_argument("--tokenizer", choices=TOKENIZER_CHOICES, default="auto")
    readable_compress_parser.add_argument("--output")
    readable_compress_parser.add_argument("--format", choices=["machine", "json"], default="machine")

    readable_query_parser = subparsers.add_parser(
        "readable-query",
        aliases=["query-compressed"],
        help="Ask a SEAM-RC/1 compressed document directly without rebuilding the source",
    )
    readable_query_parser.add_argument("source")
    readable_query_parser.add_argument("query")
    readable_query_parser.add_argument("--limit", type=int, default=5)
    readable_query_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    readable_rebuild_parser = subparsers.add_parser("readable-rebuild", help="Verify and rebuild exact text from SEAM-RC/1")
    readable_rebuild_parser.add_argument("source")
    readable_rebuild_parser.add_argument("--output")

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
    benchmark_run_parser.add_argument("--holdout", action="store_true", help="Run publish-only holdout fixtures from benchmarks/fixtures/holdout")
    benchmark_run_parser.add_argument("--confirm-holdout", action="store_true", help="Confirm intentional publish-only holdout execution")
    benchmark_run_parser.add_argument("--holdout-output-dir", help="Directory for default holdout result bundles")
    benchmark_run_parser.add_argument("--include-machine-text", action="store_true")
    benchmark_run_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    benchmark_show_parser = benchmark_subparsers.add_parser("show", help="Show a persisted benchmark run")
    benchmark_show_parser.add_argument("run_id", nargs="?", default="latest")
    benchmark_show_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    benchmark_verify_parser = benchmark_subparsers.add_parser("verify", help="Verify a benchmark bundle hash and case hashes")
    benchmark_verify_parser.add_argument("bundle")
    benchmark_verify_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    benchmark_diff_parser = benchmark_subparsers.add_parser("diff", help="Compare two benchmark bundles or persisted run ids")
    benchmark_diff_parser.add_argument("run_a")
    benchmark_diff_parser.add_argument("run_b")
    benchmark_diff_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    benchmark_gate_parser = benchmark_subparsers.add_parser("gate", help="Evaluate benchmark bundle pass/fail and baseline regression gates")
    benchmark_gate_parser.add_argument("bundle")
    benchmark_gate_parser.add_argument("--baseline", help="Baseline bundle path or persisted run id for regression gating")
    benchmark_gate_parser.add_argument("--policy", help="JSON gate policy file")
    benchmark_gate_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    compile_nl_parser = subparsers.add_parser("compile-nl", aliases=["remember"], help="Compile natural language into MIRL and persist (use --no-persist to skip storing)")
    compile_nl_parser.add_argument("text")
    compile_nl_parser.add_argument("--source-ref", default="local://input")
    compile_nl_parser.add_argument("--no-persist", dest="persist", action="store_false", default=True)
    _add_rag_sync_args(compile_nl_parser)

    compile_dsl_parser = subparsers.add_parser("compile-dsl", help="Compile SEAM DSL into MIRL and persist (use --no-persist to skip storing)")
    compile_dsl_parser.add_argument("file")
    compile_dsl_parser.add_argument("--no-persist", dest="persist", action="store_false", default=True)
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

    memory_parser = subparsers.add_parser("memory", help="Progressive-disclosure SEAM memory tools")
    memory_subparsers = memory_parser.add_subparsers(dest="memory_command", required=True)
    memory_search_parser = memory_subparsers.add_parser("search", help="Return compact memory index results")
    memory_search_parser.add_argument("query")
    memory_search_parser.add_argument("--scope")
    memory_search_parser.add_argument("--budget", type=int, default=5)
    memory_search_parser.add_argument("--format", choices=["pretty", "json", "ids"], default="pretty")
    memory_get_parser = memory_subparsers.add_parser("get", help="Return full selected MIRL records")
    memory_get_parser.add_argument("record_ids")
    memory_get_parser.add_argument("--timeline", action="store_true")
    memory_get_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

    mcp_parser = subparsers.add_parser("mcp", help="Run SEAM agent integration bridges")
    mcp_subparsers = mcp_parser.add_subparsers(dest="mcp_command", required=True)
    mcp_subparsers.add_parser("serve", help="Serve a lightweight JSON-lines MCP-compatible bridge over stdio")

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
    context_parser.add_argument("--retrieval-mode", choices=["vector", "graph", "hybrid", "mix"], default="hybrid")
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

    serve_parser = subparsers.add_parser("serve", help="Run the SEAM REST API server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.add_argument("--workers", type=int, default=1)

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

    lx1_encode_parser = subparsers.add_parser("lx1-encode", help="Encode MIRL records to LX/1 compact AI-readable notation")
    lx1_encode_parser.add_argument("source", help="MIRL text file or - for stdin")
    lx1_encode_parser.add_argument("--output", help="Write output to file instead of stdout")
    lx1_encode_parser.add_argument("--ns", default="local.default")
    lx1_encode_parser.add_argument("--scope", default="project")

    lx1_decode_parser = subparsers.add_parser("lx1-decode", help="Decode LX/1 compact notation back to MIRL records")
    lx1_decode_parser.add_argument("source", help="LX/1 file or - for stdin")
    lx1_decode_parser.add_argument("--output", help="Write MIRL text to file instead of stdout")
    lx1_decode_parser.add_argument("--persist", action="store_true", help="Persist decoded records to the database")

    lx1_benchmark_parser = subparsers.add_parser("lx1-benchmark", help="Show token savings of LX/1 notation vs verbose MIRL")
    lx1_benchmark_parser.add_argument("source", help="MIRL text file or - for stdin")
    lx1_benchmark_parser.add_argument("--ns", default="local.default")
    lx1_benchmark_parser.add_argument("--scope", default="project")
    lx1_benchmark_parser.add_argument("--format", choices=["pretty", "json"], default="pretty")

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
        _print_text(artifact.machine_text)
        return
    if args.command in {"readable-compress", "compress-readable"}:
        text = _read_text_source(args.source)
        artifact = compress_text_readable(
            text,
            source_ref=args.source_ref or args.source,
            granularity=args.granularity,
            tokenizer=args.tokenizer,
        )
        if args.output:
            _write_text_output(args.output, artifact.machine_text)
        if args.format == "json":
            print(json.dumps(artifact.to_dict(include_machine_text=True), indent=2))
            return
        _print_text(artifact.machine_text)
        return
    if args.command in {"readable-query", "query-compressed"}:
        machine_text = _read_text_source(args.source)
        result = query_readable_compressed(machine_text, args.query, limit=args.limit)
        payload = result.to_dict()
        if args.format == "json":
            print(json.dumps(payload, indent=2))
            return
        _print_text(_render_readable_query_pretty(payload))
        return
    if args.command == "readable-rebuild":
        text = decompress_text_readable(_read_text_source(args.source))
        if args.output:
            _write_text_output(args.output, text)
            print(args.output)
            return
        _print_text(text)
        return
    if args.command in {"lossless-decompress", "decompress-doc"}:
        machine_text = _read_text_source(args.source)
        text = decompress_text_lossless(machine_text)
        if args.output:
            _write_text_output(args.output, text)
            print(args.output)
            return
        _print_text(text)
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

    if args.command == "lx1-encode":
        batch = IRBatch.from_text(_read_text_source(args.source))
        compact = lx1_encode(batch, ns=args.ns, scope=args.scope)
        if args.output:
            _write_text_output(args.output, compact)
        else:
            print(compact)
        return
    if args.command == "lx1-decode":
        compact = _read_text_source(args.source)
        batch = lx1_decode(compact)
        mirl_text = batch.to_text()
        if args.output:
            _write_text_output(args.output, mirl_text)
        else:
            print(mirl_text)
        if args.persist:
            runtime = SeamRuntime(args.db)
            runtime.persist_ir(batch)
        return
    if args.command == "lx1-benchmark":
        mirl_text = _read_text_source(args.source)
        batch = IRBatch.from_text(mirl_text)
        compact = lx1_encode(batch, ns=args.ns, scope=args.scope)
        report = token_savings_report(mirl_text, compact)
        if args.format == "json":
            print(json.dumps(report, indent=2))
            return
        print(_render_lx1_benchmark_pretty(report))
        return

    if args.command == "serve":
        from .server import run_server

        run_server(host=args.host, port=args.port, db=args.db, reload=args.reload, workers=args.workers)
        return

    runtime = SeamRuntime(args.db)

    if args.command == "ingest":
        text = _read_text_source(args.source)
        if args.persist:
            report = runtime.ingest_text(text, source_ref=args.source_ref or args.source, ns=args.ns, scope=args.scope, persist=True)
            if args.format == "json":
                print(json.dumps(report.to_dict(), indent=2))
                return
            print(_render_ingest_report(report.to_dict()))
            return
        print(runtime.compile_nl(text, source_ref=args.source_ref or args.source, ns=args.ns, scope=args.scope).to_text())
        return
    if args.command in {"compile-nl", "remember"}:
        batch = runtime.compile_nl(args.text, source_ref=args.source_ref)
        if args.persist or args.sync_index:
            runtime.persist_ir(batch)
            if args.sync_index:
                orchestrator = _build_retrieval_orchestrator(runtime, args)
                orchestrator.sync_persistent_indexes(record_ids=[record.id for record in batch.records])
        if args.persist:
            print(f"Encoded {len(batch.records)} records → stored in {args.db}")
        else:
            print(batch.to_text())
        return
    if args.command == "compile-dsl":
        batch = runtime.compile_dsl(Path(args.file).read_text(encoding="utf-8"))
        if args.persist or args.sync_index:
            runtime.persist_ir(batch)
            if args.sync_index:
                orchestrator = _build_retrieval_orchestrator(runtime, args)
                orchestrator.sync_persistent_indexes(record_ids=[record.id for record in batch.records])
        if args.persist:
            print(f"Encoded {len(batch.records)} records → stored in {args.db}")
        else:
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
        plan = orchestrator.plan(args.query, scope=args.scope, budget=args.budget, mode=args.mode)
        _print_retrieval_output(plan.to_dict(), output_format=args.format, renderer=_render_plan_pretty)
        return
    if args.command in {"retrieve", "hybrid-search"}:
        orchestrator = _build_retrieval_orchestrator(runtime, args)
        result = orchestrator.search(args.query, scope=args.scope, budget=args.budget, include_trace=args.trace, mode=args.mode)
        _print_retrieval_output(result.to_dict(), output_format=args.format, renderer=_render_search_pretty)
        return
    if args.command == "memory":
        if args.memory_command == "search":
            payload = runtime.memory_search(args.query, scope=args.scope, budget=args.budget)
            _print_retrieval_output(payload, output_format=args.format, renderer=render_memory_index)
            return
        if args.memory_command == "get":
            payload = runtime.memory_get(_split_ids(args.record_ids), include_timeline=args.timeline)
            if args.format == "json":
                print(json.dumps(payload, indent=2))
                return
            print(render_memory_records(payload))
            return
    if args.command == "mcp" and args.mcp_command == "serve":
        from .mcp import run_stdio_bridge

        run_stdio_bridge(runtime)
        return
    if args.command in {"compare", "hybrid-compare"}:
        orchestrator = _build_retrieval_orchestrator(runtime, args)
        search_result = runtime.search_ir(args.query, scope=args.scope, budget=args.budget).to_dict()
        retrieved = orchestrator.search(args.query, scope=args.scope, budget=args.budget, include_trace=args.trace, mode=args.mode).to_dict()
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
                retrieval_mode=args.retrieval_mode,
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
            if args.holdout and not args.confirm_holdout:
                _confirm_holdout_run()
            payload = runtime.run_benchmark_suite(
                suite=args.suite,
                tokenizer=args.tokenizer,
                min_token_savings=args.min_savings,
                persist=args.persist,
                include_machine_text=args.include_machine_text,
                bundle_path=args.output,
                holdout=args.holdout,
            )
            holdout_output = None
            if args.holdout and args.output is None:
                holdout_output = write_holdout_benchmark_bundle(payload, args.holdout_output_dir)
            if args.format == "json":
                print(json.dumps(payload, indent=2))
                return
            print(render_benchmark_pretty(payload))
            if holdout_output is not None:
                print(f"\nHoldout bundle: {holdout_output}")
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
        if args.benchmark_command == "diff":
            run_a = _resolve_benchmark_ref(runtime, args.run_a)
            run_b = _resolve_benchmark_ref(runtime, args.run_b)
            payload = runtime.diff_benchmark_runs(run_a, run_b)
            if args.format == "json":
                print(json.dumps(payload, indent=2))
                return
            print(render_benchmark_diff_pretty(payload))
            return
        if args.benchmark_command == "gate":
            bundle = _resolve_benchmark_ref(runtime, args.bundle)
            baseline = _resolve_benchmark_ref(runtime, args.baseline) if args.baseline else None
            payload = runtime.evaluate_benchmark_gate(bundle, baseline=baseline, policy=args.policy)
            if args.format == "json":
                print(json.dumps(payload, indent=2))
            else:
                print(render_benchmark_gate_pretty(payload))
            if payload.get("status") != "PASS":
                raise SystemExit(1)
            return

        print(json.dumps(runtime.run_retrieval_benchmark(), indent=2))


def _split_ids(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def _confirm_holdout_run() -> None:
    message = (
        "Holdout benchmark runs are publish-only and should not be used for routine tuning. "
        "Type RUN HOLDOUT to continue: "
    )
    if not sys.stdin.isatty():
        raise SystemExit("Holdout benchmark requires --confirm-holdout in non-interactive shells.")
    try:
        response = input(message).strip()
    except EOFError as exc:
        raise SystemExit("Holdout benchmark requires --confirm-holdout in non-interactive shells.") from exc
    if response != "RUN HOLDOUT":
        raise SystemExit("Holdout benchmark cancelled.")


def _resolve_benchmark_ref(runtime: SeamRuntime, value: str) -> str | dict[str, object]:
    if value == "latest":
        runs = runtime.list_benchmark_runs(limit=1)
        if not runs:
            raise SystemExit("No benchmark runs have been persisted yet.")
        value = str(runs[0]["run_id"])
    path = Path(value)
    if path.exists():
        return value
    payload = runtime.read_benchmark_run(value)
    if not payload:
        raise SystemExit(f"Benchmark bundle or persisted run not found: {value}")
    return payload


def _read_text_source(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_bytes().decode("utf-8")


def _write_text_output(target: str, text: str) -> None:
    if target == "-":
        _print_text(text)
        return
    Path(target).write_bytes(text.encode("utf-8"))


def _print_text(text: str) -> None:
    buffer = getattr(sys.stdout, "buffer", None)
    if buffer is None:
        print(text)
        return
    buffer.write(text.encode("utf-8"))
    buffer.write(b"\n")


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


def _render_readable_query_pretty(payload: dict[str, object]) -> str:
    lines = [
        "Readable query results",
        f"Source: {payload.get('source_ref')}",
        f"SHA256: {payload.get('sha256')}",
        f"Query: {payload.get('query')}",
    ]
    hits = payload.get("hits", [])
    if not hits:
        lines.append("No direct compressed-language hits.")
        return "\n".join(lines)
    for index, hit in enumerate(hits, start=1):
        reasons = ", ".join(str(reason) for reason in hit.get("reasons", []))
        span = ""
        if hit.get("start") is not None and hit.get("end") is not None:
            span = f" span={hit.get('start')}..{hit.get('end')}"
        lines.append(
            f"{index}. {hit.get('record_type')} {hit.get('record_id')} score={hit.get('score')}{span}"
        )
        if reasons:
            lines.append(f"   reasons={reasons}")
        lines.append(f"   {str(hit.get('text', '')).rstrip()}")
    return "\n".join(lines)


def _render_ingest_report(payload: dict[str, object]) -> str:
    document = payload.get("document", {})
    stored_ids = payload.get("stored_ids", [])
    return "\n".join(
        [
            f"Ingested: {document.get('source_ref')}",
            f"Document: {document.get('document_id')}",
            f"Bytes: {document.get('byte_count')}",
            f"Chunks: {document.get('chunk_count')}",
            f"Extraction: {document.get('extraction_status')}",
            f"Index: {document.get('indexed_status')}",
            f"Stored ids: {', '.join(stored_ids) if stored_ids else '(none)'}",
        ]
    )


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
    parser.add_argument("--mode", choices=["vector", "graph", "hybrid", "mix"], default="hybrid")
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
    if "results" in payload:
        return "\n".join(str(item.get("id")) for item in payload.get("results", []))
    if "legs" in payload:
        return "\n".join(leg["name"] for leg in payload.get("legs", []))
    if "record_ids" in payload:
        return "\n".join(payload.get("record_ids", []))
    return ""


def _render_lx1_benchmark_pretty(report: dict[str, object]) -> str:
    return "\n".join([
        "LX/1 notation benchmark",
        f"Original MIRL tokens : {report.get('original_tokens')}",
        f"LX/1 compact tokens  : {report.get('compact_tokens')}",
        f"Token savings        : {float(report.get('token_savings_ratio', 0)):.1%}",
        f"Intelligence/token   : {float(report.get('intelligence_per_token_gain', 0)):.2f}x",
        f"Original chars       : {report.get('original_chars')}",
        f"LX/1 chars           : {report.get('compact_chars')}",
        f"Char savings         : {float(report.get('char_savings_ratio', 0)):.1%}",
    ])


def _record_signal(record: dict[str, object]) -> str:
    attrs = record.get("attrs", {})
    if "predicate" in attrs or "object" in attrs:
        return f"{attrs.get('subject', '')} {attrs.get('predicate', '')} {attrs.get('object', '')}".strip()
    if "target" in attrs:
        return f"target={attrs.get('target')}"
    return ""





