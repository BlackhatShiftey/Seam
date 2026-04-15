from __future__ import annotations

import argparse
import itertools
import sys
import time
from collections import deque
from dataclasses import dataclass

try:
    from rich import box
    from rich.align import Align
    from rich.columns import Columns
    from rich.console import Console, Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
except ImportError as exc:  # pragma: no cover - user-facing guard
    raise SystemExit(
        "The terminal preview requires 'rich'. Install dependencies with:\n"
        "  .\\.venv\\Scripts\\python -m pip install -r requirements.txt"
    ) from exc


LOGO = [
    ("   ╭──────╮  ", "cyan"),
    ("╭──╯ ╭──╮ ╰──╮", "violet"),
    ("╰──╮ ╰──╯ ╭──╯", "cyan"),
    ("   ╰──────╯  ", "violet"),
]

WORDMARK = [
    (" ███████╗███████╗ █████╗ ███╗   ███╗", "blue"),
    (" ██╔════╝██╔════╝██╔══██╗████╗ ████║", "blue"),
    (" ███████╗█████╗  ███████║██╔████╔██║", "blue"),
    (" ╚════██║██╔══╝  ██╔══██║██║╚██╔╝██║", "blue"),
    (" ███████║███████╗██║  ██║██║ ╚═╝ ██║", "blue"),
    (" ╚══════╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝", "blue"),
]


@dataclass
class DashboardState:
    mode: str
    model: str
    reasoning: str
    embedding_backend: str
    query_status: str
    command: str
    launch_path: str
    db_size: str
    vector_size: str
    packs_size: str
    objects_stored: str
    sync_health: str
    sync_lag: str
    recall_quality: str
    freshness: str


def build_logo() -> Panel:
    logo_rows = []
    for (icon, icon_style), (word, word_style) in zip(LOGO, WORDMARK[:4], strict=False):
        line = Text()
        line.append(icon, style=icon_style)
        line.append("  ")
        line.append(word, style=f"bold {word_style}")
        logo_rows.append(line)
    for word, word_style in WORDMARK[4:]:
        line = Text()
        line.append(" " * 16)
        line.append(word, style=f"bold {word_style}")
        logo_rows.append(line)
    return Panel(
        Group(*logo_rows),
        title="[cyan]SEAM[/cyan]",
        border_style="bright_blue",
        box=box.ROUNDED,
        padding=(0, 1),
    )


def build_launch_panel(state: DashboardState) -> Panel:
    lines = Group(
        Text.assemble(":: ", ("SEAM", "bold cyan"), " :: v0.1.0 :: MIRL Interpreter & Persistence Engine ::"),
        Text.assemble("Launched from: ", (state.launch_path, "bold cyan")),
        Text.assemble("Execution mode: ", (state.mode, "bold green"), " / command shell live"),
    )
    return Panel(lines, border_style="bright_blue", box=box.ROUNDED)


def metric_panel(title: str, rows: list[tuple[str, str]], footer: str | None = None) -> Panel:
    table = Table.grid(expand=True)
    table.add_column(ratio=1)
    for label, value in rows:
        table.add_row(Text.from_markup(f"{label} [bold]{value}[/bold]"))
    if footer:
        table.add_row(Text.from_markup(footer))
    return Panel(table, title=f"[cyan]{title}[/cyan]", border_style="bright_blue", box=box.ROUNDED)


def build_cards(state: DashboardState) -> Columns:
    return Columns(build_cards_stack(state), expand=True)


def build_interpreter() -> Panel:
    lines = Group(
        Text.from_markup('[blue][MIRL][/blue]>>pack(src:[gold]"./config/"[/gold], dest:[gold]"conf.seam"[/gold], codec:[gold]MIRL-LZ[/gold])'),
        Text.from_markup('[blue][MIRL][/blue]>>db.store([gold]"conf.seam"[/gold], tags:[[gold]"config"[/gold], [gold]"v1"[/gold]])'),
        Text.from_markup('[blue][MIRL][/blue]>>retrieve(query:[gold]"translator natural language"[/gold], budget:[violet]6[/violet], mode:[gold]hybrid[/gold])'),
        Text.from_markup('[blue][MIRL][/blue]>>improve(ref:[gold]"db/conf.seam"[/gold], goal:[violet]0.95[/violet])'),
        Text.from_markup("[green][SEAM_OK: pack success][/green] -> conf.seam"),
        Text.from_markup("[cyan][SEAM_INFO: DB store success][/cyan] -> object_id:77a1bc"),
        Text.from_markup("[green][SEAM_IMPROVE: refinement started][/green] -> agent:4, target:77a1bc"),
    )
    return Panel(lines, title="[cyan]MIRL Live Interpreter[/cyan]", border_style="bright_blue", box=box.ROUNDED)


def build_command_panel(state: DashboardState, cursor_on: bool) -> Panel:
    cursor = "[bold green]▉[/bold green]" if cursor_on else " "
    line = Text.from_markup(
        f"seam[[green]{state.mode}[/green]@[cyan]project_alpha/data[/cyan]]> {state.command}"
    )
    command_group = Group(
        Text.from_markup("[cyan]Command Line[/cyan]"),
        Text.assemble(line, " ", Text.from_markup(cursor)),
    )
    return Panel(command_group, border_style="bright_blue", box=box.ROUNDED)


def build_runtime_profile(state: DashboardState) -> Panel:
    grid = Table.grid(expand=True)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    entries = [
        ("Primary Model", f"{state.model} / reasoning {state.reasoning}"),
        ("Execution Mode", f"[green]{state.mode} retrieval[/green] + local persistence"),
        ("Embedding Backend", f"{state.embedding_backend} / [violet]chroma+sqlite[/violet]"),
        ("Persistence Footprint", f"db {state.db_size} / vectors {state.vector_size} / packs {state.packs_size}"),
        ("Vector Sync Health", f"[green]{state.sync_health}[/green] indexed / lag {state.sync_lag}"),
        ("Recall Quality", f"hit@5 [violet]{state.recall_quality}[/violet] / freshness {state.freshness}"),
    ]
    pairs = [entries[index:index + 2] for index in range(0, len(entries), 2)]
    for pair in pairs:
        cells = []
        for title, value in pair:
            cells.append(
                Panel(
                    Group(
                        Text(title.upper(), style="dim"),
                        Text.from_markup(value),
                    ),
                    box=box.SQUARE,
                    border_style="blue",
                    padding=(0, 1),
                )
            )
        if len(cells) == 1:
            cells.append("")
        grid.add_row(*cells)
    return Panel(grid, title="[cyan]Runtime Profile[/cyan]", border_style="bright_blue", box=box.ROUNDED)


def build_log_panel(events: deque[tuple[str, str, str]]) -> Panel:
    table = Table.grid(expand=True)
    table.add_column(width=8, style="dim")
    table.add_column(width=8)
    table.add_column(ratio=1)
    for timestamp, kind, message in list(events)[-6:]:
        style = {
            "store": "green",
            "index": "violet",
            "query": "cyan",
            "pack": "green",
            "agent": "gold1",
            "trace": "violet",
        }.get(kind, "cyan")
        table.add_row(timestamp, f"[{style}]{kind.upper()}[/{style}]", message)
    return Panel(table, title="[cyan]Runtime Log[/cyan]", border_style="bright_blue", box=box.ROUNDED)


def build_dashboard(state: DashboardState, cursor_on: bool, events: deque[tuple[str, str, str]], width: int):
    header = (
        Columns([build_logo(), build_launch_panel(state)], expand=True, equal=True)
        if width >= 120
        else Group(build_logo(), build_launch_panel(state))
    )

    cards = build_cards(state) if width >= 120 else Group(*build_cards_stack(state))

    workspace = (
        Columns(
            [
                Group(build_interpreter(), build_command_panel(state, cursor_on)),
                Group(build_runtime_profile(state), build_log_panel(events)),
            ],
            expand=True,
            equal=True,
        )
        if width >= 120
        else Group(
            build_interpreter(),
            build_command_panel(state, cursor_on),
            build_runtime_profile(state),
            build_log_panel(events),
        )
    )

    return Group(
        header,
        Align.center(Text("SEAM ENGINE DASHBOARD", style="bold cyan")),
        cards,
        workspace,
    )


def build_cards_stack(state: DashboardState) -> list[Panel]:
    compression = metric_panel(
        "Compression & Packaging",
        [
            ("[gold]•[/gold] Active Codecs:", "[gold][MIRL-LZ, ZSTD-M][/gold]"),
            ("[gold]•[/gold] Current Archive:", "[gold][app_data.seam][/gold]"),
            ("[gold]•[/gold] Ratio:", "[violet]12.4x (21GB -> 1.6GB)[/violet]"),
        ],
        footer="[cyan][[/cyan][bright_blue]██████████████[/bright_blue][dim]····[/dim][cyan]][/cyan] [cyan]75%[/cyan]",
    )
    persistence = metric_panel(
        "Persistence DB",
        [
            ("[gold]•[/gold] Objects Stored:", f"[violet]{state.objects_stored}[/violet]"),
            ("[gold]•[/gold] DB Size:", f"[violet]{state.db_size}[/violet]"),
            ("[gold]•[/gold] Read/Write:", "[violet]4.1k/2.3k[/violet] op/s"),
            ("[gold]•[/gold] MIRL Query Status:", f"[green]{state.query_status}[/green]"),
        ],
    )
    improvement = metric_panel(
        "Improvement Loop",
        [
            ("[gold]•[/gold] Refinement Agents:", "[green]14[/green]"),
            ("[gold]•[/gold] Pending Improvements:", "[violet]3[/violet]"),
            ("[gold]•[/gold] Current Task:", '[gold][refining "model_v3"][/gold]'),
            ("[gold]•[/gold] Overall Gain:", "[green]+8.9%[/green]"),
        ],
    )
    return [compression, persistence, improvement]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SEAM terminal dashboard preview.")
    parser.add_argument("--mode", choices=["cloud", "local", "hybrid"], default="cloud")
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--reasoning", default="medium")
    parser.add_argument("--embedding-backend", default="text-embedding-3-small")
    parser.add_argument("--query-status", default="Idle")
    parser.add_argument("--command", default='retrieve "translator natural language" --budget 6 --trace')
    parser.add_argument("--launch-path", default="/home/user/project_alpha")
    parser.add_argument("--db-size", default="2.2GB")
    parser.add_argument("--vector-size", default="860MB")
    parser.add_argument("--packs-size", default="126MB")
    parser.add_argument("--objects-stored", default="1.4M")
    parser.add_argument("--sync-health", default="99.2%")
    parser.add_argument("--sync-lag", default="12s")
    parser.add_argument("--recall-quality", default="0.91")
    parser.add_argument("--freshness", default="4m")
    parser.add_argument("--seconds", type=float, default=0.0, help="Run for N seconds, 0 for until Ctrl+C.")
    parser.add_argument("--snapshot", action="store_true", help="Render one frame and exit.")
    return parser.parse_args()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parse_args()
    state = DashboardState(
        mode=args.mode,
        model=args.model,
        reasoning=args.reasoning,
        embedding_backend=args.embedding_backend,
        query_status=args.query_status,
        command=args.command,
        launch_path=args.launch_path,
        db_size=args.db_size,
        vector_size=args.vector_size,
        packs_size=args.packs_size,
        objects_stored=args.objects_stored,
        sync_health=args.sync_health,
        sync_lag=args.sync_lag,
        recall_quality=args.recall_quality,
        freshness=args.freshness,
    )
    events = deque(
        [
            ("10:42:11", "store", "Persisted `conf.seam` into canonical sqlite store."),
            ("10:42:13", "index", "Chroma sync completed for 148 records, lag window dropped to 12s."),
            ("10:42:18", "query", "Retrieve pass scored 6 candidates across lexical, vector, and graph legs."),
            ("10:42:19", "pack", "Context pack emitted with 4 entries and 1 symbol expansion."),
            ("10:42:27", "agent", 'Refinement agent 4 requested review on `model_v3` contradiction cluster.'),
            ("10:42:31", "trace", "Provenance walk found 3 raw spans and 1 derived relation chain."),
        ],
        maxlen=12,
    )
    console = Console(legacy_windows=False)

    if args.snapshot:
        console.print(build_dashboard(state, cursor_on=True, events=events, width=console.size.width))
        return

    spinner = itertools.cycle([True, False])
    live = Live(
        build_dashboard(state, cursor_on=True, events=events, width=console.size.width),
        console=console,
        refresh_per_second=4,
        screen=True,
    )
    start = time.time()
    with live:
        try:
            while True:
                cursor_on = next(spinner)
                live.update(build_dashboard(state, cursor_on=cursor_on, events=events, width=console.size.width))
                time.sleep(0.35)
                if args.seconds and (time.time() - start) >= args.seconds:
                    break
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
