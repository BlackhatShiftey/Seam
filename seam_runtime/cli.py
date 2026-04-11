from __future__ import annotations

import argparse
import json
from pathlib import Path

from .mirl import IRBatch
from .runtime import SeamRuntime
from .validation import validate_runtime_stack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEAM v1 memory compiler/runtime")
    parser.add_argument("--db", default="seam.db", help="SQLite database path")
    parser.add_argument("--pgvector-dsn", default=None, help="Optional pgvector DSN; falls back to SEAM_PGVECTOR_DSN")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Store raw text from a file or stdin")
    ingest_parser.add_argument("source")

    compile_nl_parser = subparsers.add_parser("compile-nl", help="Compile natural language into MIRL")
    compile_nl_parser.add_argument("text")
    compile_nl_parser.add_argument("--source-ref", default="local://input")
    compile_nl_parser.add_argument("--persist", action="store_true")

    compile_dsl_parser = subparsers.add_parser("compile-dsl", help="Compile SEAM DSL into MIRL")
    compile_dsl_parser.add_argument("file")
    compile_dsl_parser.add_argument("--persist", action="store_true")

    verify_parser = subparsers.add_parser("verify", help="Verify MIRL from a text file")
    verify_parser.add_argument("file")

    persist_parser = subparsers.add_parser("persist", help="Persist MIRL from a text file")
    persist_parser.add_argument("file")

    search_parser = subparsers.add_parser("search", help="Hybrid search over persisted MIRL")
    search_parser.add_argument("query")
    search_parser.add_argument("--scope")
    search_parser.add_argument("--budget", type=int, default=5)

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

    subparsers.add_parser("stats", help="Run retrieval benchmark summary")
    subparsers.add_parser("validate-stack", help="Validate embedding and pgvector runtime wiring")
    return parser


def run_cli(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "validate-stack":
        print(json.dumps(validate_runtime_stack(args.db, pgvector_dsn=args.pgvector_dsn), indent=2))
        return
    runtime = SeamRuntime(args.db, pgvector_dsn=args.pgvector_dsn)

    if args.command == "ingest":
        text = Path(args.source).read_text(encoding="utf-8") if args.source != "-" else input()
        print(runtime.compile_nl(text, source_ref=args.source).to_text())
        return
    if args.command == "compile-nl":
        batch = runtime.compile_nl(args.text, source_ref=args.source_ref)
        if args.persist:
            runtime.persist_ir(batch)
        print(batch.to_text())
        return
    if args.command == "compile-dsl":
        batch = runtime.compile_dsl(Path(args.file).read_text(encoding="utf-8"))
        if args.persist:
            runtime.persist_ir(batch)
        print(batch.to_text())
        return
    if args.command == "verify":
        batch = IRBatch.from_text(Path(args.file).read_text(encoding="utf-8"))
        print(json.dumps(runtime.verify_ir(batch).to_dict(), indent=2))
        return
    if args.command == "persist":
        batch = IRBatch.from_text(Path(args.file).read_text(encoding="utf-8"))
        print(json.dumps(runtime.persist_ir(batch).to_dict(), indent=2))
        return
    if args.command == "search":
        print(json.dumps(runtime.search_ir(args.query, scope=args.scope, budget=args.budget).to_dict(), indent=2))
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
    if args.command == "stats":
        print(json.dumps(runtime.run_retrieval_benchmark(), indent=2))


def _split_ids(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]
