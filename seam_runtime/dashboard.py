from __future__ import annotations

import argparse
import json
import os
import shlex
import sqlite3
import sys
import time
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

try:
    from textual import on
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal
    from textual.widgets import Footer, Input, Static

    _TEXTUAL_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - optional dashboard path
    on = App = ComposeResult = Horizontal = Footer = Input = Static = None  # type: ignore[assignment]
    _TEXTUAL_IMPORT_ERROR = exc

from experimental.retrieval_orchestrator import RetrievalOrchestrator

from .context_views import CONTEXT_VIEWS, build_context_payload
from .lossless import LOSSLESS_CODECS, LOSSLESS_TRANSFORMS, TOKENIZER_CHOICES, benchmark_text_lossless, compress_text_lossless, decompress_text_lossless
from .mirl import IRBatch
from .models import HashEmbeddingModel
from .runtime import SeamRuntime
from .installer import default_runtime_db_path


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


class SeamChatClient:
    def __init__(self) -> None:
        self.base_url = os.environ.get("SEAM_CHAT_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.model = os.environ.get("SEAM_CHAT_MODEL", "gpt-4o-mini")
        self.api_key = os.environ.get("SEAM_CHAT_API_KEY") or os.environ.get("OPENAI_API_KEY")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def complete(self, messages: list[dict[str, str]], context_prompt: str) -> str:
        if not self.configured:
            return (
                "Chat model is not configured.\n"
                "Set SEAM_CHAT_API_KEY (or OPENAI_API_KEY) and optionally SEAM_CHAT_MODEL / SEAM_CHAT_BASE_URL."
            )
        try:
            import httpx

            payload_messages = [
                {
                    "role": "system",
                    "content": (
                        "You are the SEAM dashboard assistant. Keep answers concise, actionable, and grounded in runtime state.\n\n"
                        f"Runtime context:\n{context_prompt}"
                    ),
                },
                *messages[-8:],
            ]
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0.2,
                    "messages": payload_messages,
                },
                timeout=45.0,
            )
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                return "No response choices were returned by the chat model."
            content = choices[0].get("message", {}).get("content", "")
            return str(content).strip() or "(empty model response)"
        except Exception as exc:
            return f"Chat request failed: {exc}"


if App is not None and Static is not None and Input is not None:
    class _TextualPanel(Static):
        def __init__(self, title: str, panel_id: str) -> None:
            super().__init__("", id=panel_id, markup=False)
            self._title = title
            self._lines: list[str] = []

        def on_mount(self) -> None:  # pragma: no cover - textual runtime behavior
            self.border_title = self._title
            self._refresh_content()

        def set_title(self, title: str) -> None:
            self._title = title
            self.border_title = title

        def set_lines(self, lines: list[str]) -> None:
            self._lines = lines[-200:]
            self._refresh_content()

        def _refresh_content(self) -> None:
            self.update("\n".join(self._lines[-200:]) if self._lines else "(empty)")


    class TextualDashboardApp(App[None]):
        CSS = """
        Screen {
            layout: vertical;
        }
        #logo-header {
            height: 7;
            border: round $primary;
            padding: 0 1;
        }
        #metrics {
            height: 7;
            border: round $primary;
            padding: 0 1;
        }
        #tab-bar {
            height: 2;
            border: round $primary;
            padding: 0 1;
        }
        #top-row, #middle-row {
            height: 1fr;
            layout: horizontal;
        }
        #bottom-row {
            height: 2fr;
            layout: horizontal;
        }
        #command-input {
            dock: bottom;
            border: round $primary;
        }
        #memory-panel, #retrieval-panel, #benchmark-panel, #result-panel, #runtime-log-panel, #chat-panel, #command-history-panel, #mirl-panel {
            width: 1fr;
            border: round $primary;
            margin: 0 1;
            padding: 0 1;
        }
        """

        BINDINGS = [("ctrl+c", "quit", "Quit"), ("ctrl+d", "quit", "Quit")]

        def __init__(
            self,
            runtime: SeamRuntime,
            vector_backend: str = "seam",
            vector_path: str = ".seam_chroma",
            vector_collection: str = "seam_hybrid",
        ) -> None:
            super().__init__()
            self.controller = DashboardApp(
                runtime,
                vector_backend=vector_backend,
                vector_path=vector_path,
                vector_collection=vector_collection,
                no_clear=True,
            )
            self.memory_lines: list[str] = []
            self.retrieval_lines: list[str] = []
            self.benchmark_lines: list[str] = []
            self.result_lines: list[str] = []
            self.side_lines: list[str] = []
            self.chat_lines: list[str] = []
            self.chat_history: list[dict[str, str]] = []
            self.command_history_lines: list[str] = []
            self.mirl_lines: list[str] = []
            self.chat_client = SeamChatClient()
            self.transcript_dir = Path(os.environ.get("SEAM_CHAT_TRANSCRIPT_DIR", ".seam/chat_transcripts"))
            self.input_mode = "model"
            self.command_names = {
                "help",
                "quit",
                "exit",
                "tab",
                "compile",
                "compile-nl",
                "compile-dsl",
                "dsl",
                "search",
                "plan",
                "retrieve",
                "context",
                "index",
                "trace",
                "benchmark",
                "compress-doc",
                "lossless-compress",
                "decompress-doc",
                "lossless-decompress",
                "decompress-last",
                "stats",
            }
            self._animation_phase = 0
            self._anim_until = 0.0
            self._anim_label = "idle"
            self._anim_preview = ""
            self._token_source_total = 0
            self._token_machine_total = 0
            self._token_events: deque[tuple[float, int]] = deque(maxlen=32)

        def compose(self) -> ComposeResult:
            yield Static("", id="logo-header")
            yield Static("", id="metrics")
            yield Static("", id="tab-bar")
            with Horizontal(id="top-row"):
                yield _TextualPanel("Memory Records", "memory-panel")
                yield _TextualPanel("Search / Retrieval", "retrieval-panel")
                yield _TextualPanel("Benchmark", "benchmark-panel")
            with Horizontal(id="middle-row"):
                yield _TextualPanel("MIRL Compression", "mirl-panel")
                yield _TextualPanel("Command History", "command-history-panel")
                yield _TextualPanel("Chat", "chat-panel")
            with Horizontal(id="bottom-row"):
                yield _TextualPanel("Results", "result-panel")
                yield _TextualPanel("Runtime Log", "runtime-log-panel")
            yield Input(placeholder="", id="command-input")
            yield Footer()

        def on_mount(self) -> None:  # pragma: no cover - textual runtime behavior
            self._refresh_logo()
            self._refresh_metrics()
            self._refresh_tab_bar()
            self._refresh_input_placeholder()
            self._sync_side_panel()
            self.query_one("#benchmark-panel", _TextualPanel).set_lines(["Run `benchmark <file>` to populate benchmark results."])
            self.query_one("#chat-panel", _TextualPanel).set_lines(
                [
                    "Chat ready.",
                    "Shortcuts: /model /cmd /hybrid /help /savechat",
                    "Model mode: plain text chats, !<command> runs terminal commands.",
                ]
            )
            self.query_one("#command-history-panel", _TextualPanel).set_lines(["No command events yet."])
            self.query_one("#mirl-panel", _TextualPanel).set_lines(["Idle. Run compile/compress/benchmark for live machine animation."])
            self._push_result("Welcome", self.controller.result_body)
            self.set_interval(0.25, self._tick_mirl_animation)
            self.set_interval(1.0, self._tick_metrics)

        @on(Input.Submitted, "#command-input")
        def _on_command_submitted(self, event: Input.Submitted) -> None:  # pragma: no cover - textual runtime behavior
            command = event.value.strip()
            event.input.value = ""
            if not command:
                return
            self.process_command(command)

        def process_command(self, command: str) -> None:
            raw = command.strip()
            if not raw:
                return
            if raw.startswith("/"):
                self._handle_shortcut(raw)
                return
            force_command = raw.startswith("!")
            force_chat = raw.startswith("?")
            candidate = raw[1:].strip() if (force_command or force_chat) else raw
            token = candidate.split()[0].lower() if candidate else ""

            if self.input_mode == "model":
                if not force_command:
                    self._handle_chat_message(candidate)
                    return
            elif self.input_mode == "command":
                if force_chat:
                    self._handle_chat_message(candidate)
                    return
            else:  # hybrid
                if force_chat:
                    self._handle_chat_message(candidate)
                    return
                if not force_command and token not in self.command_names:
                    self._handle_chat_message(candidate)
                    return

            command = candidate
            self._execute_dashboard_command(command)

        def _execute_dashboard_command(self, command: str) -> None:
            started_at = time.perf_counter()
            self._record_command("run", command)
            should_exit = self.controller.execute(command)
            elapsed = max(0.0, time.perf_counter() - started_at)
            title = self.controller.result_title
            body = self.controller.result_body
            self._route_command_output(command, title, body)
            self._push_result(title, body)
            self._sync_side_panel()
            self._refresh_metrics()
            self._refresh_tab_bar()
            phase = "ok" if self.controller.last_command_ok else "err"
            self._record_command(phase, f"{command} -> {title} ({self._format_elapsed(elapsed)})")
            self._capture_token_metrics_from_command(command)
            if should_exit:
                self.exit()

        def _handle_shortcut(self, raw: str) -> None:
            parts = raw.strip().split(maxsplit=1)
            shortcut = parts[0].lower() if parts else ""
            argument = parts[1].strip() if len(parts) > 1 else ""
            argument = argument.strip("\"'")
            if shortcut in {"/model", "/m"}:
                self.input_mode = "model"
                self._refresh_input_placeholder()
                self._push_result("Input Mode", "Switched to model mode. Plain text chats. Use !<command> for terminal commands.")
                self._record_command("mode", "model")
                self._refresh_tab_bar()
                return
            if shortcut in {"/cmd", "/command", "/c"}:
                self.input_mode = "command"
                self._refresh_input_placeholder()
                self._push_result("Input Mode", "Switched to command mode. Plain text runs terminal commands. Use ?<message> to chat.")
                self._record_command("mode", "command")
                self._refresh_tab_bar()
                return
            if shortcut in {"/hybrid", "/h"}:
                self.input_mode = "hybrid"
                self._refresh_input_placeholder()
                self._push_result("Input Mode", "Switched to hybrid mode. Commands auto-detect; unknown input goes to chat.")
                self._record_command("mode", "hybrid")
                self._refresh_tab_bar()
                return
            if shortcut in {"/clear", "/cls"}:
                self.chat_lines.clear()
                self.chat_history.clear()
                self.query_one("#chat-panel", _TextualPanel).set_lines(["Chat cleared."])
                self._push_result("Chat", "Chat history cleared.")
                self._record_command("chat", "clear")
                return
            if shortcut in {"/help", "/?"}:
                self._push_result(
                    "Shortcuts",
                    (
                        "/model  -> plain text chats, !<command> for commands\n"
                        "/cmd    -> plain text commands, ?<message> for chat\n"
                        "/hybrid -> auto route (commands or chat)\n"
                        "/clear  -> clear chat history\n"
                        "/savechat [path] -> export chat transcript (.jsonl)\n"
                        "/export-chat [path] -> alias for /savechat"
                    ),
                )
                self._record_command("help", "shortcuts")
                return
            if shortcut in {"/savechat", "/save-chat", "/export-chat", "/exportchat"}:
                destination = Path(argument).expanduser() if argument else self._default_chat_export_path()
                target, count = self._save_chat_transcript(destination)
                self._push_result("Chat Transcript", f"Exported {count} messages to {target}")
                self._record_command("state", f"chat transcript -> {target}")
                return
            self._push_result("Shortcut Error", f"Unknown shortcut: {raw}. Use /help.")
            self._record_command("error", f"shortcut {raw}")

        def _route_command_output(self, command: str, title: str, body: str) -> None:
            token = command.split()[0].lower()
            if token in {"compile", "compile-nl", "compile-dsl", "dsl", "stats", "trace", "index"}:
                self.memory_lines.extend([f"{title}: {command}", body, ""])
                self.query_one("#memory-panel", _TextualPanel).set_lines(self.memory_lines)
                if token in {"compile", "compile-nl", "compile-dsl", "dsl"}:
                    self._trigger_mirl_animation("compile", body)
                return
            if token in {"search", "retrieve", "context", "plan"}:
                self.retrieval_lines.extend([f"{title}: {command}", body, ""])
                self.query_one("#retrieval-panel", _TextualPanel).set_lines(self.retrieval_lines)
                return
            if token in {"benchmark", "compress-doc", "lossless-compress", "decompress-doc", "lossless-decompress", "decompress-last"}:
                self.benchmark_lines.extend([f"{title}: {command}", body, ""])
                self.query_one("#benchmark-panel", _TextualPanel).set_lines(self.benchmark_lines)
                if token in {"benchmark", "compress-doc", "lossless-compress"}:
                    self._trigger_mirl_animation(token, body)
            if token == "tab":
                self._record_command("state", f"active tab => {self.controller.active_tab}")

        def _push_result(self, title: str, body: str) -> None:
            self.result_lines.extend([f"{title}", body, ""])
            self.query_one("#result-panel", _TextualPanel).set_lines(self.result_lines)

        def _sync_side_panel(self) -> None:
            panel = self.query_one("#runtime-log-panel", _TextualPanel)
            if self.controller.active_tab == "benchmark":
                attempts = (self.controller.last_benchmark_payload or {}).get("search_log", [])
                if not attempts:
                    lines = ["No benchmark search log yet. Run `benchmark <file>` to populate this panel."]
                else:
                    lines = []
                    for attempt in attempts[-16:]:
                        flags = f" flags={','.join(attempt.get('flags', []))}" if attempt.get("flags") else ""
                        lines.append(
                            (
                                f"iter={attempt.get('iteration')} status={attempt.get('status')} "
                                f"{attempt.get('transform')}/{attempt.get('codec')} "
                                f"savings={float(attempt.get('token_savings_ratio', 0.0)):.1%} "
                                f"tokens={attempt.get('machine_tokens')}{flags}"
                            )
                        )
                panel.set_title("Benchmark Log")
            else:
                lines = [f"{event.timestamp} {event.kind}: {event.message}" for event in list(self.controller.events)]
                panel.set_title("Runtime Log")
            self.side_lines = lines
            panel.set_lines(lines)

        def _refresh_metrics(self) -> None:
            metrics = self.controller._collect_metrics()
            db_bytes = Path(metrics.db_path).stat().st_size if Path(metrics.db_path).exists() else 0
            db_ratio = min(1.0, db_bytes / float(1024 * 1024 * 1024))
            source_tokens = self._token_source_total
            machine_tokens = self._token_machine_total
            compressed = max(source_tokens - machine_tokens, 0)
            savings_ratio = 0.0 if source_tokens == 0 else compressed / float(source_tokens)
            token_rate = self._estimate_token_rate()
            summary = (
                f"DB: {metrics.db_path}\n"
                f"Records={metrics.total_records} Vectors={metrics.vector_entries} Packs={metrics.pack_entries} Mode={metrics.execution_mode}\n"
                f"Adapter={metrics.vector_adapter_name} | Tab={self.controller.active_tab}\n"
                f"Token rate: {token_rate:.1f} tok/s\n"
                f"Compressed tokens: {compressed} (source={source_tokens}, machine={machine_tokens})\n"
                f"DB size bar      {self._bar(db_ratio)}\n"
                f"Compression bar  {self._bar(savings_ratio)}"
            )
            self.query_one("#metrics", Static).update(summary)

        def _refresh_tab_bar(self) -> None:
            runtime = "[Runtime]" if self.controller.active_tab == "runtime" else "Runtime"
            benchmark = "[Benchmark]" if self.controller.active_tab == "benchmark" else "Benchmark"
            self.query_one("#tab-bar", Static).update(
                f"Tabs: {runtime}  {benchmark} | Input mode: {self.input_mode} | /model /cmd /hybrid /savechat /help"
            )

        def _refresh_input_placeholder(self) -> None:
            widget = self.query_one("#command-input", Input)
            if self.input_mode == "model":
                widget.placeholder = "Model mode: type to chat | !<command> to run dashboard commands | /help"
            elif self.input_mode == "command":
                widget.placeholder = "Command mode: type command | ?<message> to chat | /help"
            else:
                widget.placeholder = "Hybrid mode: commands auto-detect, otherwise chat | /help"

        def _refresh_logo(self) -> None:
            chat_status = "configured" if self.chat_client.configured else "offline"
            logo = (
                "  _____  ______          __  \n"
                " / ____|/ __ \\ \\        / /  \n"
                "| (___ | |  | \\ \\  /\\  / /   \n"
                " \\___ \\| |  | |\\ \\/  \\/ /    \n"
                " ____) | |__| | \\  /\\  /     \n"
                "|_____/ \\____/   \\/  \\/      \n"
                f"SEAM Glassbox Dashboard | Model: {self.chat_client.model} ({chat_status})"
            )
            self.query_one("#logo-header", Static).update(logo)

        def _handle_chat_message(self, message: str) -> None:
            if not message:
                self._push_result("Chat", "Enter a message after '?' or switch to /model mode and type normally.")
                self._record_command("error", "empty chat input")
                return
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.chat_history.append({"role": "user", "content": message})
            context_prompt = self._build_chat_context_prompt(message)
            assistant = self.chat_client.complete(self.chat_history, context_prompt)
            self.chat_history.append({"role": "assistant", "content": assistant})
            self.chat_lines.extend(
                [
                    f"{timestamp} user: {message}",
                    f"{timestamp} seam: {assistant}",
                    "",
                ]
            )
            self.query_one("#chat-panel", _TextualPanel).set_lines(self.chat_lines)
            self._push_result("Chat", assistant)
            self._record_command("chat", message)

        def _build_chat_context_prompt(self, message: str) -> str:
            try:
                rag = self.controller.orchestrator.rag(message, budget=5, pack_budget=384, lens="rag", mode="context").to_dict()
                prompt_view = build_context_payload(rag, view="prompt")
                if isinstance(prompt_view, dict):
                    return json.dumps(prompt_view, indent=2)[:4000]
                return str(prompt_view)[:4000]
            except Exception as exc:
                return f"(context retrieval failed: {exc})"

        def _record_command(self, phase: str, text: str) -> None:
            badge = {
                "run": "[RUN]",
                "ok": "[OK]",
                "err": "[ERR]",
                "mode": "[MODE]",
                "chat": "[CHAT]",
                "help": "[HELP]",
                "state": "[STATE]",
                "error": "[ERR]",
            }.get(phase, f"[{phase.upper()}]")
            self.command_history_lines.append(f"{datetime.now().strftime('%H:%M:%S')} {badge} {text}")
            self.query_one("#command-history-panel", _TextualPanel).set_lines(self.command_history_lines)

        def _trigger_mirl_animation(self, label: str, body: str) -> None:
            self._anim_label = label
            self._anim_until = time.monotonic() + 4.0
            compact = body.replace("\n", " ").replace("\r", " ")
            self._anim_preview = compact[:120]

        def _tick_mirl_animation(self) -> None:
            self._animation_phase = (self._animation_phase + 1) % 8
            if time.monotonic() > self._anim_until:
                lines = [
                    "Idle. Run compile/compress/benchmark for live machine animation.",
                    "Pipeline: DSL -> MIRL -> SEAM-LX/1",
                ]
                self.query_one("#mirl-panel", _TextualPanel).set_lines(lines)
                return
            frames = ["[=   ]", "[==  ]", "[=== ]", "[ ===]", "[  ==]", "[   =]", "[ == ]", "[=== ]"]
            frame = frames[self._animation_phase]
            pseudo = f"{self._anim_label.upper()} :: dsl::tokenize -> mirl::graph -> lx1::machine_stream"
            machine_line = (self._anim_preview or "emit 01011001|clm|ent|sym|ctx")[:120]
            self.query_one("#mirl-panel", _TextualPanel).set_lines(
                [
                    f"{frame} MIRL compression live",
                    pseudo,
                    machine_line,
                ]
            )

        def _tick_metrics(self) -> None:
            self._refresh_metrics()

        def _capture_token_metrics_from_command(self, command: str) -> None:
            token = command.split()[0].lower()
            source_tokens: int | None = None
            machine_tokens: int | None = None
            if token == "benchmark" and self.controller.last_benchmark_payload:
                artifact = self.controller.last_benchmark_payload.get("artifact", {})
                source_tokens = int(artifact.get("source_tokens", 0) or 0)
                machine_tokens = int(artifact.get("machine_tokens", 0) or 0)
            elif token in {"compress-doc", "lossless-compress"}:
                try:
                    payload = json.loads(self.controller.result_body)
                    source_tokens = int(payload.get("source_tokens", 0) or 0)
                    machine_tokens = int(payload.get("machine_tokens", 0) or 0)
                except Exception:
                    pass
            if source_tokens is not None and machine_tokens is not None and source_tokens > 0:
                self._token_source_total += source_tokens
                self._token_machine_total += machine_tokens
                self._token_events.append((time.monotonic(), source_tokens))

        def _estimate_token_rate(self) -> float:
            if len(self._token_events) < 2:
                return 0.0
            first_t, _ = self._token_events[0]
            last_t, _ = self._token_events[-1]
            elapsed = max(1e-6, last_t - first_t)
            total = sum(tokens for _, tokens in self._token_events)
            return total / elapsed

        @staticmethod
        def _bar(ratio: float, width: int = 24) -> str:
            clamped = max(0.0, min(1.0, ratio))
            filled = int(round(clamped * width))
            return f"[{'#' * filled}{'-' * (width - filled)}] {clamped * 100:5.1f}%"

        @staticmethod
        def _format_elapsed(seconds: float) -> str:
            if seconds < 1.0:
                return f"{int(round(seconds * 1000))}ms"
            return f"{seconds:.2f}s"

        def _default_chat_export_path(self) -> Path:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            return self.transcript_dir / f"chat-{stamp}.jsonl"

        def _save_chat_transcript(self, destination: Path) -> tuple[Path, int]:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("w", encoding="utf-8") as handle:
                for idx, message in enumerate(self.chat_history, start=1):
                    row = {
                        "index": idx,
                        "role": str(message.get("role", "")),
                        "content": str(message.get("content", "")),
                    }
                    handle.write(json.dumps(row, sort_keys=True))
                    handle.write("\n")
            return destination.resolve(), len(self.chat_history)
else:
    class TextualDashboardApp:  # pragma: no cover - exercised when textual is missing
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _ensure_textual()


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
        self.last_command_ok = True
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
            self.last_command_ok = False
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
            self.last_command_ok = True
            return True
        if args.command == "help":
            self.result_title = "Dashboard Help"
            self.result_body = self._help_text()
            self._log("help", "Displayed interactive command help.")
            self.last_command_ok = True
            return False
        if args.command == "tab":
            self.active_tab = args.view
            self.result_title = "Dashboard Tab"
            self.result_body = f"Switched to the {args.view} tab."
            self._log("system", f"Switched dashboard tab to {args.view}.")
            self.last_command_ok = True
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
        self.last_command_ok = True
        self._log(title.lower(), log_message)

    def _fail(self, title: str, message: str) -> None:
        self.result_title = title
        self.result_body = message
        self.last_command_ok = False
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
    if _TEXTUAL_IMPORT_ERROR is None:
        textual_app = TextualDashboardApp(
            runtime,
            vector_backend=vector_backend,
            vector_path=vector_path,
            vector_collection=vector_collection,
        )
        textual_app.run()
        return
    app.run_interactive()


def _ensure_rich() -> None:
    if _RICH_IMPORT_ERROR is not None:  # pragma: no cover - environment-dependent path
        raise SystemExit(
            "The dashboard requires 'rich'. Install dependencies with:\n"
            "  .\\.venv\\Scripts\\python -m pip install -r requirements.txt"
        ) from _RICH_IMPORT_ERROR


def _ensure_textual() -> None:
    if _TEXTUAL_IMPORT_ERROR is not None:  # pragma: no cover - environment-dependent path
        raise SystemExit(
            "The interactive dashboard requires 'textual'. Install optional dependencies with:\n"
            "  pip install seam-runtime[dash]"
        ) from _TEXTUAL_IMPORT_ERROR


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Launch the SEAM interactive dashboard")
    parser.add_argument("--db", default=default_runtime_db_path(), help="SQLite database path")
    parser.add_argument("--snapshot", action="store_true", help="Render one Rich dashboard frame and exit")
    parser.add_argument("--run", dest="dashboard_commands", action="append", default=[], help="Run a dashboard command non-interactively")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear the terminal in Rich snapshot/script mode")
    parser.add_argument("--vector-backend", "--semantic-backend", dest="vector_backend", choices=["seam", "chroma"], default="seam")
    parser.add_argument("--vector-path", "--chroma-path", dest="vector_path", default=".seam_chroma")
    parser.add_argument("--vector-collection", "--chroma-collection", dest="vector_collection", default="seam_hybrid")
    args = parser.parse_args(argv)

    if not args.snapshot and not args.dashboard_commands:
        _ensure_textual()

    runtime = SeamRuntime(args.db)
    run_dashboard(
        runtime,
        vector_backend=args.vector_backend,
        vector_path=args.vector_path,
        vector_collection=args.vector_collection,
        snapshot=args.snapshot,
        commands=args.dashboard_commands,
        no_clear=args.no_clear,
    )
