"""Seed HISTORY.md from REPO_LEDGER.md + PLAN_LOG.md.

This is a one-shot migration helper for Plan v3.
It:
1. Parses Milestone Log entries from REPO_LEDGER.md.
2. Parses status entries from PLAN_LOG.md.
3. Deduplicates overlapping plan entries against richer milestone entries.
4. Assigns sequential IDs in chronological order.
5. Infers topic tags from the controlled AGENTS.md vocabulary.
6. Writes HISTORY.md using binary LF output, then rebuilds index + verifies integrity.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from tools.history.history_lib import HISTORY_PATH, format_entry
from tools.history.rebuild_index import rebuild
from tools.history.verify_integrity import verify

REPO_ROOT = HISTORY_PATH.parent
LEDGER_PATH = REPO_ROOT / "REPO_LEDGER.md"
PLAN_LOG_PATH = REPO_ROOT / "PLAN_LOG.md"
AGENTS_PATH = REPO_ROOT / "AGENTS.md"

STATUS_MAP = {
    "PLANNED": "planned",
    "IN PROGRESS": "in-progress",
    "DONE": "done",
    "CHANGED": "changed",
    "DEFERRED": "deferred",
    "ABANDONED": "abandoned",
}

DEFAULT_TOPICS = {
    "compile",
    "mirl",
    "persist",
    "verify",
    "retrieval",
    "search",
    "rank",
    "vector",
    "sbert",
    "chroma",
    "pgvector",
    "lexical",
    "compress",
    "lx1",
    "roundtrip",
    "codec",
    "benchmark",
    "holdout",
    "bundle",
    "fixture",
    "diff",
    "gold-standard",
    "dashboard",
    "tui",
    "textual",
    "animation",
    "graph",
    "chat",
    "installer",
    "windows",
    "linux",
    "wsl2",
    "pyproject",
    "extras",
    "command",
    "doctor",
    "demo",
    "naming",
    "alias",
    "readme",
    "ledger",
    "roadmap",
    "plan",
    "status",
    "history",
    "session",
    "handoff",
    "snapshot",
    "mcp",
    "multi-agent",
    "protocol",
    "integrity",
}


@dataclass
class SeedEvent:
    date: str
    title: str
    status: str
    body: str
    source: str
    source_order: int
    refs: str
    commits: str = "none"
    topics: list[str] | None = None
    supersedes_index: int | None = None
    timestamp: str | None = None


def _clean_lines(lines: list[str]) -> str:
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines).strip()


def _norm_title(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    stop = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "into",
        "pass",
        "step",
        "session",
        "core",
        "runtime",
    }
    toks = [t for t in text.split() if t and t not in stop]
    return " ".join(toks)


def _title_similarity(a: str, b: str) -> float:
    na = _norm_title(a)
    nb = _norm_title(b)
    if not na or not nb:
        return 0.0
    ratio = difflib.SequenceMatcher(a=na, b=nb).ratio()
    sa = set(na.split())
    sb = set(nb.split())
    if not sa or not sb:
        return ratio
    jaccard = len(sa & sb) / len(sa | sb)
    return max(ratio, jaccard)


def _extract_commit_hash(text: str) -> str:
    m = re.search(r"(?im)^\s*Commit:\s*`?([0-9a-f]{7,40})`?\s*$", text)
    return m.group(1) if m else "none"


def parse_milestone_events(ledger_text: str) -> list[SeedEvent]:
    lines = ledger_text.splitlines()
    events: list[SeedEvent] = []
    in_milestones = False
    current_date: str | None = None
    source_order = 0
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped == "## Milestone Log":
            in_milestones = True
            i += 1
            continue
        if in_milestones and stripped.startswith("## Handoff Block"):
            break
        if not in_milestones:
            i += 1
            continue

        m_date = re.match(r"^###\s+(\d{4}-\d{2}-\d{2})\s*$", stripped)
        if m_date:
            current_date = m_date.group(1)
            i += 1
            continue

        if current_date and stripped.startswith("#### "):
            title = stripped[5:].strip()
            i += 1
            body_lines: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                nxt_stripped = nxt.strip()
                if re.match(r"^###\s+\d{4}-\d{2}-\d{2}\s*$", nxt_stripped):
                    break
                if nxt_stripped.startswith("#### "):
                    break
                if nxt_stripped.startswith("## "):
                    break
                body_lines.append(nxt.rstrip("\n"))
                i += 1
            body = _clean_lines(body_lines)
            if body:
                events.append(
                    SeedEvent(
                        date=current_date,
                        title=title,
                        status="done",
                        body=body,
                        source="ledger",
                        source_order=source_order,
                        refs="REPO_LEDGER.md#milestone-log",
                        commits=_extract_commit_hash(body),
                    )
                )
                source_order += 1
            continue

        i += 1

    return events


def parse_plan_events(plan_text: str) -> list[SeedEvent]:
    lines = plan_text.splitlines()
    events: list[SeedEvent] = []
    current_date: str | None = None
    source_order = 0
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        m_date = re.match(r"^###\s+(\d{4}-\d{2}-\d{2})(?:\s+\(.*\))?\s*$", line)
        if m_date:
            current_date = m_date.group(1)
            i += 1
            continue

        m_entry = re.match(r"^####\s+\[([A-Z ]+)\]\s+(.+)$", line)
        if current_date and m_entry:
            raw_status = m_entry.group(1).strip()
            title = m_entry.group(2).strip()
            status = STATUS_MAP.get(raw_status)
            if status is None:
                i += 1
                continue
            i += 1
            body_lines: list[str] = []
            while i < len(lines):
                nxt = lines[i].strip()
                if re.match(r"^###\s+\d{4}-\d{2}-\d{2}(?:\s+\(.*\))?\s*$", nxt):
                    break
                if re.match(r"^####\s+\[[A-Z ]+\]\s+.+$", nxt):
                    break
                body_lines.append(lines[i].rstrip("\n"))
                i += 1
            body = _clean_lines(body_lines)
            if body:
                events.append(
                    SeedEvent(
                        date=current_date,
                        title=title,
                        status=status,
                        body=body,
                        source="plan",
                        source_order=source_order,
                        refs="PLAN_LOG.md",
                        commits=_extract_commit_hash(body),
                    )
                )
                source_order += 1
            continue

        i += 1

    return events


def dedupe_plan_events(
    plan_events: list[SeedEvent], milestone_events: list[SeedEvent]
) -> list[SeedEvent]:
    kept: list[SeedEvent] = []
    for pe in plan_events:
        dup = False
        for me in milestone_events:
            sim = _title_similarity(pe.title, me.title)
            if sim >= 0.62:
                dup = True
                break
        if not dup:
            kept.append(pe)
    return kept


def load_topic_vocabulary(path: Path) -> set[str]:
    if not path.exists():
        return set(DEFAULT_TOPICS)
    text = path.read_text(encoding="utf-8")
    m = re.search(r"##\s*7\.\s*Topic Tag Vocabulary.*?```(.*?)```", text, re.DOTALL)
    if not m:
        return set(DEFAULT_TOPICS)
    block = m.group(1)
    topics: set[str] = set()
    for line in block.splitlines():
        if not line.strip():
            continue
        if ":" in line:
            _, rhs = line.split(":", 1)
        else:
            rhs = line
        for token in rhs.split(","):
            clean = token.strip().lower()
            clean = re.sub(r"[^a-z0-9\-]", "", clean)
            if clean:
                topics.add(clean)
    return topics or set(DEFAULT_TOPICS)


def infer_topics(text: str, vocabulary: set[str]) -> list[str]:
    low = text.lower()
    pairs: list[tuple[str, list[str]]] = [
        ("compile", ["compile", "compiler"]),
        ("mirl", ["mirl"]),
        ("persist", ["persist", "sqlite", "database", "db"]),
        ("verify", ["verify", "verification", "validated", "prove"]),
        ("retrieval", ["retrieval", "rag", "context pipeline"]),
        ("search", ["search", "find"]),
        ("rank", ["rank", "ranking"]),
        ("vector", ["vector", "embedding", "semantic"]),
        ("sbert", ["sbert", "sentence-transformer"]),
        ("chroma", ["chroma"]),
        ("pgvector", ["pgvector"]),
        ("lexical", ["lexical"]),
        ("compress", ["compress", "compression"]),
        ("lx1", ["seam-lx/1", "lx/1", "machine-text"]),
        ("roundtrip", ["roundtrip", "rebuild"]),
        ("codec", ["codec"]),
        ("benchmark", ["benchmark", "mteb", "beir", "ms-marco"]),
        ("holdout", ["holdout"]),
        ("bundle", ["bundle"]),
        ("fixture", ["fixture"]),
        ("diff", [" diff ", "delta"]),
        ("gold-standard", ["gold standard"]),
        ("dashboard", ["dashboard"]),
        ("tui", [" tui ", "terminal ui", "interactive ui"]),
        ("textual", ["textual"]),
        ("animation", ["animation", "animated"]),
        ("graph", ["graph", "sparkline"]),
        ("chat", ["chat"]),
        ("installer", ["installer", "install flow"]),
        ("windows", ["windows"]),
        ("linux", ["linux"]),
        ("wsl2", ["wsl2"]),
        ("pyproject", ["pyproject"]),
        ("extras", ["optional extras", "all-extras", "extras"]),
        ("command", ["command", "cli"]),
        ("doctor", ["doctor"]),
        ("demo", ["demo"]),
        ("naming", ["naming", "terminology"]),
        ("alias", ["alias"]),
        ("readme", ["readme"]),
        ("ledger", ["ledger"]),
        ("roadmap", ["roadmap"]),
        ("plan", ["plan"]),
        ("status", ["status"]),
        ("history", ["history"]),
        ("session", ["session"]),
        ("handoff", ["handoff"]),
        ("snapshot", ["snapshot"]),
        ("mcp", ["mcp"]),
        ("multi-agent", ["multi-agent", "cross-agent"]),
        ("protocol", ["protocol"]),
        ("integrity", ["integrity", "sha-256", "hash"]),
    ]
    out: list[str] = []
    for topic, needles in pairs:
        if topic not in vocabulary:
            continue
        for needle in needles:
            if needle in low:
                out.append(topic)
                break
    deduped: list[str] = []
    seen: set[str] = set()
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        deduped.append(t)
    if not deduped:
        if "history" in vocabulary:
            deduped = ["history"]
        else:
            deduped = [sorted(vocabulary)[0]]
    return deduped[:6]


def assign_timestamps(events: list[SeedEvent]) -> None:
    per_day_count: dict[str, int] = {}
    for ev in events:
        idx = per_day_count.get(ev.date, 0)
        per_day_count[ev.date] = idx + 1
        base = dt.datetime.strptime(ev.date, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
        stamp = base + dt.timedelta(minutes=idx)
        ev.timestamp = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")


def assign_supersedes(events: list[SeedEvent]) -> None:
    prior_candidates: list[int] = []
    terminal = {"done", "changed", "deferred", "abandoned"}
    for i, ev in enumerate(events):
        if ev.status in {"planned", "in-progress"}:
            prior_candidates.append(i)
            continue
        if ev.status not in terminal:
            continue
        best_idx = None
        best_score = 0.0
        for pidx in prior_candidates:
            prev = events[pidx]
            if prev.date > ev.date:
                continue
            score = _title_similarity(prev.title, ev.title)
            if score > best_score and score >= 0.68:
                best_score = score
                best_idx = pidx
        ev.supersedes_index = best_idx


def build_seed_events() -> list[SeedEvent]:
    ledger_text = LEDGER_PATH.read_text(encoding="utf-8")
    plan_text = PLAN_LOG_PATH.read_text(encoding="utf-8")

    milestones = parse_milestone_events(ledger_text)
    plans = parse_plan_events(plan_text)
    plans = dedupe_plan_events(plans, milestones)

    events = milestones + plans
    events.sort(key=lambda e: (e.date, 0 if e.source == "ledger" else 1, e.source_order))
    assign_timestamps(events)
    assign_supersedes(events)
    return events


def write_history(events: list[SeedEvent], *, agent: str) -> int:
    vocab = load_topic_vocabulary(AGENTS_PATH)
    chunks: list[str] = []
    for i, ev in enumerate(events, start=1):
        ev.topics = infer_topics(f"{ev.title}\n{ev.body}", vocab)
        supersedes = "none"
        if ev.supersedes_index is not None:
            supersedes = f"#{ev.supersedes_index + 1:03d}"
        body = f"{ev.title}\n\n{ev.body}".strip()
        entry_text = format_entry(
            id=i,
            date=ev.timestamp or f"{ev.date}T00:00:00Z",
            agent=agent,
            status=ev.status,
            topics=ev.topics,
            commits=ev.commits,
            refs=ev.refs,
            supersedes=supersedes,
            tokens=max(1, int(len(body.split()) * 1.3)),
            body=body,
        ).rstrip("\n")
        chunks.append(entry_text)

    payload = ("\n\n".join(chunks) + "\n").encode("utf-8")
    with open(HISTORY_PATH, "wb") as f:
        f.write(payload)
    return len(events)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Seed HISTORY.md from existing repo docs.")
    p.add_argument("--agent", default="legacy-log-import")
    p.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing non-empty HISTORY.md",
    )
    args = p.parse_args(argv)

    missing = [str(pth) for pth in (LEDGER_PATH, PLAN_LOG_PATH, AGENTS_PATH) if not pth.exists()]
    if missing:
        print("ERROR: missing required files:", file=sys.stderr)
        for m in missing:
            print(f"  - {m}", file=sys.stderr)
        return 2

    if HISTORY_PATH.exists() and HISTORY_PATH.stat().st_size > 0 and not args.force:
        print(
            "ERROR: HISTORY.md already exists and is non-empty. "
            "Use --force to reseed.",
            file=sys.stderr,
        )
        return 2

    events = build_seed_events()
    if not events:
        print("ERROR: no events were parsed from REPO_LEDGER.md / PLAN_LOG.md", file=sys.stderr)
        return 2

    count = write_history(events, agent=args.agent)
    rebuilt = rebuild()
    from tools.history import history_lib

    ok, errors = verify(history_lib.HISTORY_PATH, history_lib.INDEX_PATH)
    if not ok:
        print("Integrity FAILED after seeding:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"Seeded HISTORY.md entries: {count}")
    print(f"Rebuilt HISTORY_INDEX.md entries: {rebuilt}")
    print("Integrity OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
