from __future__ import annotations

import argparse
import json
import os
import shlex
import sqlite3
import sys
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from rich import box
    from rich.console import Console, Group
    from rich.markup import escape
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
    _RICH_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - user-facing guard
    box = Console = Group = Panel = Prompt = Table = Text = None  # type: ignore[assignment]
    escape = lambda value: value  # type: ignore[assignment]
    _RICH_IMPORT_ERROR = exc

from experimental.retrieval_orchestrator import RetrievalOrchestrator

from .context_views import CONTEXT_VIEWS, build_context_payload
from .lossless import LOSSLESS_CODECS, LOSSLESS_TRANSFORMS, TOKENIZER_CHOICES, benchmark_text_lossless, compress_text_lossless, decompress_text_lossless
from .mirl import IRBatch
from .models import HashEmbeddingModel
from .runtime import SeamRuntime


@dataclass
class DashboardMetrics:
    db_path: str
    db_size: str
    total_records: int
    vector_entries: int
    pack_entries: int
    provenance_entries: int
    symbol_entries: int
    raw_entries: int
    namespaces: int
    scopes: int
    top_kinds: list[tuple[str, int]]
    model_name: str
    execution_mode: str
    vector_adapter_name: str
    pgvector_configured: bool
    vector_store_size: str


@dataclass
class DashboardEvent:
    timestamp: str
    kind: str
    message: str


class DashboardParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # pragma: no cover - exercised through controller
        raise ValueError(message)


class DashboardApp:
    def __init__(
        self,
        runtime: SeamRuntime,
        vector_backend: str = "seam",
        vector_path: str = ".seam_chroma",
        vector_collection: str = "seam_hybrid",
        console: Console | None = None,
        no_clear: bool = False,
    ) -> None:
        _ensure_rich()
        self.runtime = runtime
        self.console = console or Console(legacy_windows=False)
        self.vector_backend = vector_backend
        self.vector_path = vector_path
        self.vector_collection = vector_collection
        self.no_clear = no_clear
        self.orchestrator = RetrievalOrchestrator(
            runtime,
            semantic_backend=vector_backend,
            chroma_path=vector_path,
            chroma_collection=vector_collection,
        )
        self.events: deque[DashboardEvent] = deque(maxlen=10)
        self.active_tab = "runtime"
        self.last_benchmark_payload: dict[str, Any] | None = None
        self.last_machine_text: str | None = None
        self.last_command = "help"
        self.result_title = "Welcome"
        self.result_body = (
            "SEAM dashboard is live.\n\n"
            "Try commands like:\n"
            "  compile We need durable memory for AI systems\n"
            "  retrieve translator natural language\n"
            "  context translator natural language\n"
            "  stats\n"
            "  help\n"
            "  quit"
        )
        self.command_parser = self._build_command_parser()
        self._log("system", f"Dashboard attached to {self.runtime.store.path}")

    def _build_command_parser(self) -> DashboardParser:
        parser = DashboardParser(add_help=False, prog="seam-dashboard")
        subparsers = parser.add_subparsers(dest="command")

        help_parser = subparsers.add_parser("help", add_help=False)
        help_parser.add_argument("topic", nargs="?")

        quit_parser = subparsers.add_parser("quit", add_help=False, aliases=["exit"])
        quit_parser.add_argument("rest", nargs="*")

        tab_parser = subparsers.add_parser("tab", add_help=False)
        tab_parser.add_argument("view", choices=["runtime", "benchmark"])

        compile_parser = subparsers.add_parser("compile", add_help=False, aliases=["compile-nl"])
        compile_parser.add_argument("text", nargs="+")
        compile_parser.add_argument("--scope", default="thread")
        compile_parser.add_argument("--ns", default="local.default")
        compile_parser.add_argument("--source-ref", default="dashboard://interactive")
        compile_parser.add_argument("--no-index", action="store_true")

        dsl_parser = subparsers.add_parser("compile-dsl", add_help=False, aliases=["dsl"])
        dsl_parser.add_argument("file")
        dsl_parser.add_argument("--scope", default="project")
        dsl_parser.add_argument("--ns", default="local.default")
        dsl_parser.add_argument("--no-index", action="store_true")

        for name in ("search", "plan", "retrieve", "context"):
            command_parser = subparsers.add_parser(name, add_help=False)
            command_parser.add_argument("query", nargs="+")
            command_parser.add_argument("--scope")
            command_parser.add_argument("--budget", type=int, default=5)
            if name == "context":
                command_parser.add_argument("--pack-budget", type=int, default=512)
                command_parser.add_argument("--lens", default="rag")
                command_parser.add_argument("--mode", choices=["context", "narrative", "exact"], default="context")
                command_parser.add_argument("--view", choices=CONTEXT_VIEWS, default="pack")
            else:
                command_parser.add_argument("--trace", action="store_true")

        index_parser = subparsers.add_parser("index", add_help=False)
        index_parser.add_argument("--scope")
        index_parser.add_argument("--namespace")
        index_parser.add_argument("--record-ids", default="")

        trace_parser = subparsers.add_parser("trace", add_help=False)
        trace_parser.add_argument("obj_id")

        benchmark_parser = subparsers.add_parser("benchmark", add_help=False)
        benchmark_parser.add_argument("source")
        benchmark_parser.add_argument("--codec", choices=["auto", *LOSSLESS_CODECS], default="auto")
        benchmark_parser.add_argument("--transform", choices=["auto", *LOSSLESS_TRANSFORMS], default="auto")
        benchmark_parser.add_argument("--tokenizer", choices=TOKENIZER_CHOICES, default="auto")
        benchmark_parser.add_argument("--min-savings", type=float, default=0.30)
        benchmark_parser.add_argument("--show-machine", action="store_true")

        compress_parser = subparsers.add_parser("compress-doc", add_help=False, aliases=["lossless-compress"])
        compress_parser.add_argument("source")
        compress_parser.add_argument("--codec", choices=["auto", *LOSSLESS_CODECS], default="auto")
        compress_parser.add_argument("--transform", choices=["auto", *LOSSLESS_TRANSFORMS], default="auto")
        compress_parser.add_argument("--tokenizer", choices=TOKENIZER_CHOICES, default="auto")

        decompress_parser = subparsers.add_parser("decompress-doc", add_help=False, aliases=["lossless-decompress"])
        decompress_parser.add_argument("source")

        subparsers.add_parser("decompress-last", add_help=False)

        stats_parser = subparsers.add_parser("stats", add_help=False)
        stats_parser.add_argument("rest", nargs="*")
        return parser

    def run_script(self, commands: list[str], render_each: bool = False) -> None:
        for command in commands:
            should_exit = self.execute(command)
            if render_each:
                self.render()
            if should_exit:
                break
        if not render_each:
            self.render()

    def run_interactive(self) -> None:  # pragma: no cover - interactive shell path
        while True:
            self.render()
            raw_command = Prompt.ask("[bold cyan]seam[/bold cyan]")
            should_exit = self.execute(raw_command)
            if should_exit:
                self.render()
                return

    def execute(self, raw_command: str) -> bool:
        command = raw_command.strip()
        if not command:
            self.result_title = "No Command"
            self.result_body = "Enter a command or type `help`."
            return False

        self.last_command = command
        try:
            args = self.command_parser.parse_args(shlex.split(command))
        except ValueError as exc:
            self._fail("Command Error", str(exc))
            return False

        if args.command in {"quit", "exit"}:
            self.result_title = "Dashboard Exit"
            self.result_body = "SEAM dashboard closed cleanly."
            self._log("system", "Dashboard shutdown requested.")
            return True
        if args.command == "help":
            self.result_title = "Dashboard Help"
            self.result_body = self._help_text()
            self._log("help", "Displayed interactive command help.")
            return False
        if args.command == "tab":
            self.active_tab = args.view
            self.result_title = "Dashboard Tab"
            self.result_body = f"Switched to the {args.view} tab."
            self._log("system", f"Switched dashboard tab to {args.view}.")
            return False

        try:
            if args.command in {"compile", "compile-nl"}:
                batch = self.runtime.compile_nl(
                    " ".join(args.text),
                    source_ref=args.source_ref,
                    ns=args.ns,
                    scope=args.scope,
                )
                report = self.runtime.persist_ir(batch).to_dict()
                index_report = None
                if not args.no_index:
                    index_report = self.orchestrator.sync_persistent_indexes(record_ids=[record.id for record in batch.records])
                payload = {"persist": report, "index": index_report, "records": batch.to_json()}
                self._succeed("Compile", payload, f"Compiled and stored {len(batch.records)} MIRL records.")
                return False

            if args.command in {"compile-dsl", "dsl"}:
                batch = self.runtime.compile_dsl(Path(args.file).read_text(encoding="utf-8"), ns=args.ns, scope=args.scope)
                report = self.runtime.persist_ir(batch).to_dict()
                index_report = None
                if not args.no_index:
                    index_report = self.orchestrator.sync_persistent_indexes(record_ids=[record.id for record in batch.records])
                payload = {"persist": report, "index": index_report, "records": batch.to_json()}
                self._succeed("Compile DSL", payload, f"Compiled DSL file {args.file}.")
                return False

            if args.command == "search":
                result = self.runtime.search_ir(" ".join(args.query), scope=args.scope, budget=args.budget).to_dict()
                self._succeed("Search", result, f"Ran lexical/vector search with budget {args.budget}.")
                return False

            if args.command == "plan":
                result = self.orchestrator.plan(" ".join(args.query), scope=args.scope, budget=args.budget).to_dict()
                self._succeed("Plan", result, "Built retrieval plan.")
                return False

            if args.command == "retrieve":
                result = self.orchestrator.search(
                    " ".join(args.query),
                    scope=args.scope,
                    budget=args.budget,
                    include_trace=args.trace,
                ).to_dict()
                self._succeed("Retrieve", result, "Ran ranked retrieval across active legs.")
                return False

            if args.command == "context":
                result = build_context_payload(
                    self.orchestrator.rag(
                        " ".join(args.query),
                        scope=args.scope,
                        budget=args.budget,
                        pack_budget=args.pack_budget,
                        lens=args.lens,
                        mode=args.mode,
                    ).to_dict(),
                    view=args.view,
                )
                self._succeed("Context", result, "Built generation context from retrieved records.")
                return False

            if args.command == "index":
                result = self.orchestrator.sync_persistent_indexes(
                    record_ids=self._split_ids(args.record_ids),
                    scope=args.scope,
                    namespace=args.namespace,
                )
                self._succeed("Index", result, "Synced persisted records into the active vector backend.")
                return False

            if args.command == "trace":
                result = self.runtime.trace(args.obj_id).to_dict()
                self._succeed("Trace", result, f"Traced provenance for {args.obj_id}.")
                return False

            if args.command == "benchmark":
                benchmark_result = benchmark_text_lossless(
                    self._read_text_source(args.source),
                    codec=args.codec,
                    transform=args.transform,
                    min_token_savings=args.min_savings,
                    tokenizer=args.tokenizer,
                )
                result = benchmark_result.to_dict(include_machine_text=args.show_machine)
                self.last_benchmark_payload = result
                self.last_machine_text = benchmark_result.artifact.machine_text
                self.active_tab = "benchmark"
                self._succeed("Benchmark", result, "Ran iterative lossless benchmark search.")
                return False

            if args.command in {"compress-doc", "lossless-compress"}:
                artifact = compress_text_lossless(
                    self._read_text_source(args.source),
                    codec=args.codec,
                    transform=args.transform,
                    tokenizer=args.tokenizer,
                ).to_dict(include_machine_text=True)
                self.last_machine_text = str(artifact.get("machine_text", ""))
                self.active_tab = "benchmark"
                self._succeed("Compress Doc", artifact, "Built lossless machine text.")
                return False

            if args.command in {"decompress-doc", "lossless-decompress"}:
                text = decompress_text_lossless(self._read_text_source(args.source))
                self.active_tab = "benchmark"
                self._succeed("Decompress Doc", text, "Restored source document from machine text.")
                return False

            if args.command == "decompress-last":
                if not self.last_machine_text:
                    raise ValueError("No in-memory machine text is available yet. Run benchmark or compress-doc first.")
                text = decompress_text_lossless(self.last_machine_text)
                self.active_tab = "benchmark"
                self._succeed("Decompress Last", text, "Restored the latest machine text from the benchmark tab.")
                return False

            if args.command == "stats":
                metrics = self._collect_metrics()
                payload = {
                    "db_path": metrics.db_path,
                    "db_size": metrics.db_size,
                    "total_records": metrics.total_records,
                    "vector_entries": metrics.vector_entries,
                    "pack_entries": metrics.pack_entries,
                    "provenance_entries": metrics.provenance_entries,
                    "symbol_entries": metrics.symbol_entries,
                    "raw_entries": metrics.raw_entries,
                    "namespaces": metrics.namespaces,
                    "scopes": metrics.scopes,
                    "top_kinds": metrics.top_kinds,
                    "model_name": metrics.model_name,
                    "execution_mode": metrics.execution_mode,
                    "vector_adapter": metrics.vector_adapter_name,
                    "pgvector_configured": metrics.pgvector_configured,
                    "vector_store_size": metrics.vector_store_size,
                }
                self._succeed("Stats", payload, "Refreshed runtime metrics.")
                return False
        except Exception as exc:  # pragma: no cover - error handling path is exercised through scripted smoke
            self._fail(type(exc).__name__, str(exc))
            return False

        self._fail("Command Error", f"Unknown command: {args.command}")
        return False

    def render(self) -> None:
        metrics = self._collect_metrics()
        if not self.no_clear:
            self.console.clear()
        self.console.print(self._build_dashboard(metrics))

    def _build_dashboard(self, metrics: DashboardMetrics):
        return Group(
            self._build_header(metrics),
            self._build_runtime_panels(metrics),
            self._build_activity_panels(metrics),
        )

    def _build_header(self, metrics: DashboardMetrics) -> Panel:
        title = Text("SEAM Console", style="bold cyan")
        db_line = Text(f"db={metrics.db_path}  records={metrics.total_records}", style="dim white")
        tabs = Text()
        tabs.append(" Runtime ", style="bold black on bright_white" if self.active_tab == "runtime" else "white on grey23")
        tabs.append("  ")
        tabs.append(" Benchmark ", style="bold black on bright_white" if self.active_tab == "benchmark" else "white on grey23")
        return Panel(Group(title, db_line, tabs), border_style="bright_blue", box=box.ROUNDED)

    def _build_runtime_panels(self, metrics: DashboardMetrics):
        pgvector_status = "[green]configured[/green]" if metrics.pgvector_configured else "[dim]not set[/dim]"
        runtime_table = Table.grid(expand=True)
        runtime_table.add_column(ratio=1)
        runtime_table.add_column(ratio=1)
        runtime_table.add_row("Execution Mode", metrics.execution_mode)
        runtime_table.add_row("Embedding Model", metrics.model_name)
        runtime_table.add_row("Vector Adapter", metrics.vector_adapter_name)
        runtime_table.add_row("PgVector DSN", pgvector_status)

        storage_table = Table.grid(expand=True)
        storage_table.add_column(ratio=1)
        storage_table.add_column(justify="right")
        storage_table.add_row("DB Size", metrics.db_size)
        storage_table.add_row("Vector Store Size", metrics.vector_store_size)
        storage_table.add_row("Records", str(metrics.total_records))
        storage_table.add_row("Vectors", str(metrics.vector_entries))
        storage_table.add_row("Packs", str(metrics.pack_entries))
        storage_table.add_row("Provenance", str(metrics.provenance_entries))
        storage_table.add_row("Symbols", str(metrics.symbol_entries))
        storage_table.add_row("Raw Docs", str(metrics.raw_entries))
        storage_table.add_row("Namespaces / Scopes", f"{metrics.namespaces} / {metrics.scopes}")

        kinds_table = Table.grid(expand=True)
        kinds_table.add_column(ratio=1)
        kinds_table.add_column(justify="right")
        for kind, count in metrics.top_kinds:
            kinds_table.add_row(kind, str(count))
        if not metrics.top_kinds:
            kinds_table.add_row("No persisted records", "0")

        panels = Table.grid(expand=True)
        panels.add_column(ratio=1)
        panels.add_column(ratio=1)
        panels.add_column(ratio=1)
        third_panel = (
            Panel(self._build_benchmark_summary_table(), title="[cyan]Benchmark[/cyan]", border_style="bright_blue", box=box.ROUNDED)
            if self.active_tab == "benchmark"
            else Panel(kinds_table, title="[cyan]Top Kinds[/cyan]", border_style="bright_blue", box=box.ROUNDED)
        )
        panels.add_row(
            Panel(runtime_table, title="[cyan]Runtime[/cyan]", border_style="bright_blue", box=box.ROUNDED),
            Panel(storage_table, title="[cyan]Storage[/cyan]", border_style="bright_blue", box=box.ROUNDED),
            third_panel,
        )
        return panels

    def _build_activity_panels(self, metrics: DashboardMetrics):
        body = Table.grid(expand=True)
        body.add_column(ratio=3)
        body.add_column(ratio=2)
        side_group = (
            Group(
                Panel(self._build_benchmark_log_table(), title="[cyan]Benchmark Log[/cyan]", border_style="bright_blue", box=box.ROUNDED),
                Panel(self._build_command_help(), title="[cyan]Commands[/cyan]", border_style="bright_blue", box=box.ROUNDED),
            )
            if self.active_tab == "benchmark"
            else Group(
                Panel(self._build_log_table(), title="[cyan]Runtime Log[/cyan]", border_style="bright_blue", box=box.ROUNDED),
                Panel(self._build_command_help(), title="[cyan]Commands[/cyan]", border_style="bright_blue", box=box.ROUNDED),
            )
        )
        body.add_row(
            Panel(self._build_result_body(), title=f"[cyan]{escape(self.result_title)}[/cyan]", border_style="bright_blue", box=box.ROUNDED),
            side_group,
        )
        footer = Panel(
            Text(f"Last command: {self.last_command}", style="green"),
            border_style="blue",
            box=box.ROUNDED,
        )
        return Group(body, footer)

    def _build_result_body(self):
        lines = self.result_body.splitlines() or ["(no output)"]
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        for line in lines[:28]:
            table.add_row(Text(line))
        if len(lines) > 28:
            table.add_row(Text(f"... {len(lines) - 28} more lines", style="dim"))
        return table

    def _build_log_table(self):
        table = Table.grid(expand=True)
        table.add_column(width=8, style="dim")
        table.add_column(width=10)
        table.add_column(ratio=1)
        for event in list(self.events)[-8:]:
            style = {
                "system": "cyan",
                "compile": "green",
                "search": "cyan",
                "retrieve": "magenta",
                "context": "green",
                "index": "yellow",
                "trace": "blue",
                "help": "white",
                "error": "red",
            }.get(event.kind, "white")
            table.add_row(event.timestamp, f"[{style}]{event.kind}[/{style}]", event.message)
        return table

    def _build_command_help(self):
        help_lines = [
            ("tab", "runtime|benchmark"),
            ("compile", "<text>"),
            ("compile-dsl", "<file>"),
            ("search", "<query> [--budget N]"),
            ("plan", "<query>"),
            ("retrieve", "<query> [--budget N] [--trace]"),
            ("context", "<query> [--view pack|prompt|evidence|summary]"),
            ("benchmark", "<file> [--min-savings N] [--tokenizer auto|...]"),
            ("compress-doc", "<file>"),
            ("decompress-doc / decompress-last", ""),
            ("index", "[--scope S] [--namespace NS]"),
            ("trace", "<record-id>"),
            ("stats", ""),
            ("help / quit", ""),
        ]
        table = Table.grid(expand=True)
        table.add_column(style="cyan", no_wrap=True)
        table.add_column(style="dim white")
        for cmd, args in help_lines:
            table.add_row(cmd, args)
        return table

    def _succeed(self, title: str, payload: object, log_message: str) -> None:
        self.result_title = title
        self.result_body = self._format_payload(payload)
        self._log(title.lower(), log_message)

    def _fail(self, title: str, message: str) -> None:
        self.result_title = title
        self.result_body = message
        self._log("error", message)

    def _log(self, kind: str, message: str) -> None:
        self.events.append(DashboardEvent(timestamp=datetime.now().strftime("%H:%M:%S"), kind=kind, message=message))

    def _format_payload(self, payload: object) -> str:
        if isinstance(payload, IRBatch):
            return payload.to_text()
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict) and "artifact" in payload and "roundtrip_match" in payload:
            from .lossless import render_lossless_benchmark_pretty

            return render_lossless_benchmark_pretty(payload)
        return json.dumps(payload, indent=2, sort_keys=True)

    def _build_benchmark_summary_table(self):
        table = Table.grid(expand=True)
        table.add_column(ratio=1)
        table.add_column(justify="right")
        payload = self.last_benchmark_payload
        if not payload:
            table.add_row("Status", "No benchmark yet")
            table.add_row("Run", "benchmark <file>")
            return table
        artifact = payload.get("artifact", {})
        table.add_row("Status", "PASS" if payload.get("passed") else "FAIL")
        table.add_row("Roundtrip", "PASS" if payload.get("roundtrip_match") else "FAIL")
        table.add_row("Transform", str(artifact.get("transform")))
        table.add_row("Codec", str(artifact.get("codec")))
        table.add_row("Tokenizer", str(artifact.get("token_estimator")))
        table.add_row("Savings", f"{float(artifact.get('token_savings_ratio', 0.0)):.1%}")
        table.add_row("Gain", f"{float(artifact.get('intelligence_per_token_gain', 0.0)):.2f}x")
        table.add_row("Flags", str(len(payload.get("flags", []))))
        return table

    def _build_benchmark_log_table(self):
        table = Table.grid(expand=True)
        table.add_column(width=6, style="dim")
        table.add_column(width=14)
        table.add_column(ratio=1)
        payload = self.last_benchmark_payload or {}
        attempts = payload.get("search_log", [])
        if not attempts:
            table.add_row("-", "benchmark", "Run a benchmark to populate the search log.")
            return table
        for attempt in attempts[-8:]:
            flags = f" flags={','.join(attempt.get('flags', []))}" if attempt.get("flags") else ""
            detail = (
                f"{attempt.get('transform')}/{attempt.get('codec')} "
                f"savings={float(attempt.get('token_savings_ratio', 0.0)):.1%} "
                f"tokens={attempt.get('machine_tokens')}{flags}"
            )
            table.add_row(str(attempt.get("iteration")), str(attempt.get("status")), detail)
        return table

    def _collect_metrics(self) -> DashboardMetrics:
        db_path = Path(self.runtime.store.path)
        model = self.runtime.embedding_model
        if isinstance(model, HashEmbeddingModel):
            execution_mode = "local"
        elif getattr(model, "name", "").startswith("st:"):
            execution_mode = "local (neural)"
        else:
            execution_mode = "cloud"
        db_size = self._format_bytes(db_path.stat().st_size if db_path.exists() else 0)
        vector_store_size = self._format_bytes(self._directory_size(Path(self.vector_path))) if self.vector_backend == "chroma" else "embedded"
        vector_adapter_name = getattr(self.runtime.vector_adapter, "name", "unknown")
        pgvector_configured = bool(os.environ.get("SEAM_PGVECTOR_DSN"))

        total_records = 0
        vector_entries = 0
        pack_entries = 0
        provenance_entries = 0
        symbol_entries = 0
        raw_entries = 0
        namespaces = 0
        scopes = 0
        top_kinds: list[tuple[str, int]] = []

        with sqlite3.connect(self.runtime.store.path) as connection:
            cursor = connection.cursor()
            total_records = cursor.execute("select count(*) from ir_records").fetchone()[0]
            vector_entries = cursor.execute("select count(*) from vector_index").fetchone()[0]
            pack_entries = cursor.execute("select count(*) from pack_store").fetchone()[0]
            provenance_entries = cursor.execute("select count(*) from prov_log").fetchone()[0]
            symbol_entries = cursor.execute("select count(*) from symbol_table").fetchone()[0]
            raw_entries = cursor.execute("select count(*) from raw_docs").fetchone()[0]
            namespaces = cursor.execute("select count(distinct ns) from ir_records").fetchone()[0]
            scopes = cursor.execute("select count(distinct scope) from ir_records").fetchone()[0]
            top_kinds = cursor.execute(
                "select kind, count(*) as n from ir_records group by kind order by n desc, kind asc limit 5"
            ).fetchall()
        return DashboardMetrics(
            db_path=str(db_path),
            db_size=db_size,
            total_records=total_records,
            vector_entries=vector_entries,
            pack_entries=pack_entries,
            provenance_entries=provenance_entries,
            symbol_entries=symbol_entries,
            raw_entries=raw_entries,
            namespaces=namespaces,
            scopes=scopes,
            top_kinds=[(str(kind), int(count)) for kind, count in top_kinds],
            model_name=self.runtime.embedding_model.name,
            execution_mode=execution_mode,
            vector_adapter_name=vector_adapter_name,
            pgvector_configured=pgvector_configured,
            vector_store_size=vector_store_size,
        )

    def _help_text(self) -> str:
        return (
            "SEAM dashboard commands\n\n"
            "tab runtime|benchmark\n"
            "compile <text>\n"
            "compile-dsl <file>\n"
            "search <query> [--budget N]\n"
            "plan <query> [--budget N]\n"
            "retrieve <query> [--budget N] [--trace]\n"
            "context <query> [--budget N] [--pack-budget N] [--view pack|prompt|evidence|summary|records]\n"
            "benchmark <file> [--min-savings N] [--tokenizer auto|char4_approx|cl100k_base|o200k_base]\n"
            "compress-doc <file> [--tokenizer auto|char4_approx|cl100k_base|o200k_base]\n"
            "decompress-doc <file>\n"
            "decompress-last\n"
            "index [--scope S] [--namespace NS]\n"
            "trace <record-id>\n"
            "stats\n"
            "quit"
        )

    @staticmethod
    def _split_ids(text: str) -> list[str] | None:
        parts = [part.strip() for part in text.split(",") if part.strip()]
        return parts or None

    @staticmethod
    def _read_text_source(source: str) -> str:
        if source == "-":
            return sys.stdin.read()
        return Path(source).read_bytes().decode("utf-8")

    @staticmethod
    def _directory_size(path: Path) -> int:
        if not path.exists():
            return 0
        return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())

    @staticmethod
    def _format_bytes(value: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(value)
        unit = units[0]
        for unit in units:
            if size < 1024 or unit == units[-1]:
                break
            size /= 1024
        return f"{size:.1f}{unit}" if unit != "B" else f"{int(size)}B"


def run_dashboard(
    runtime: SeamRuntime,
    vector_backend: str = "seam",
    vector_path: str = ".seam_chroma",
    vector_collection: str = "seam_hybrid",
    snapshot: bool = False,
    commands: list[str] | None = None,
    no_clear: bool = False,
    console: Console | None = None,
) -> None:
    _ensure_rich()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    app = DashboardApp(
        runtime,
        vector_backend=vector_backend,
        vector_path=vector_path,
        vector_collection=vector_collection,
        console=console,
        no_clear=no_clear,
    )
    if commands:
        app.run_script(commands)
        return
    if snapshot:
        app.render()
        return
    app.run_interactive()


def _ensure_rich() -> None:
    if _RICH_IMPORT_ERROR is not None:  # pragma: no cover - environment-dependent path
        raise SystemExit(
            "The dashboard requires 'rich'. Install dependencies with:\n"
            "  .\\.venv\\Scripts\\python -m pip install -r requirements.txt"
        ) from _RICH_IMPORT_ERROR
