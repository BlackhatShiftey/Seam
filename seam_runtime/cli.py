from __future__ import annotations

import argparse
import json
from pathlib import Path

from experimental.hybrid_orchestrator import HybridOrchestrator
from .mirl import IRBatch
from .runtime import SeamRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEAM v1 memory compiler/runtime")
    parser.add_argument("--db", default="seam.db", help="SQLite database path")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Store raw text from a file or stdin")
    ingest_parser.add_argument("source")

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
    context_parser.add_argument("--format", choices=["pretty", "json", "ids"], default="pretty")
    context_parser.add_argument("--trace", action="store_true")
    context_parser.add_argument("--vector-backend", "--semantic-backend", dest="vector_backend", choices=["seam", "chroma"], default="seam")
    context_parser.add_argument("--vector-path", "--chroma-path", dest="vector_path", default=".seam_chroma")
    context_parser.add_argument("--vector-collection", "--chroma-collection", dest="vector_collection", default="seam_hybrid")

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
    return parser


def run_cli(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    runtime = SeamRuntime(args.db)

    if args.command == "ingest":
        text = Path(args.source).read_text(encoding="utf-8") if args.source != "-" else input()
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
        payload = orchestrator.rag(
            args.query,
            scope=args.scope,
            budget=args.budget,
            pack_budget=args.pack_budget,
            lens=args.lens,
            mode=args.mode,
            include_trace=args.trace,
        ).to_dict()
        _print_retrieval_output(payload, output_format=args.format, renderer=_render_rag_pretty)
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


def _build_retrieval_orchestrator(runtime: SeamRuntime, args: argparse.Namespace) -> HybridOrchestrator:
    return HybridOrchestrator(
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


def _render_rag_pretty(payload: dict[str, object]) -> str:
    pack = payload.get("pack", {})
    lines = [
        f"Backend: {payload.get('backend')}",
        f"Query: {payload.get('query')}",
        f"Candidate ids: {', '.join(payload.get('candidate_ids', [])) or '(none)'}",
        f"Pack id: {pack.get('pack_id')}",
        "Context entries:",
    ]
    entries = pack.get("payload", {}).get("entries", [])
    if not entries:
        lines.append("(none)")
    for index, entry in enumerate(entries, start=1):
        lines.append(f"{index}. {entry.get('id')} [{entry.get('kind')}]")
    if payload.get("trace"):
        lines.append("Trace: included")
    return "\n".join(lines)


def _render_ids(payload: dict[str, object]) -> str:
    if "search" in payload and "retrieve" in payload:
        search_ids = " ".join(candidate["record"]["id"] for candidate in payload["search"].get("candidates", []))
        retrieval_ids = " ".join(candidate["record"]["id"] for candidate in payload["retrieve"].get("candidates", []))
        return f"search: {search_ids}\nretrieve: {retrieval_ids}".strip()
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
