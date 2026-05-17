# SOP: SEAM LoCoMo Adapter (External Memory Benchmark — Phase 3)

Handoff target: DeepSeek (or any contributor)
Track: I — External Memory Benchmarks
Canonical spec: `docs/roadmap/MEMORY_BENCHMARKS.md`
Sequence: **SOP 1 of 5.** Prereq: SOP 0 (`SOP_EXTERNAL_BENCH_PHASE1_REGISTRY.md`). Follow-ups: SOP 2 (LLM-judge), SOP 3 (Mem0 comparator), SOP 4 (Zep comparator).

This SOP defines exactly what to build for the first real external memory benchmark adapter: SEAM running LoCoMo with string-match scoring (EM + F1) and a 60-second quickstart path.

## 1. Goal

After this PR, a clean install must be able to run:

```bash
seam bench external --quickstart locomo
```

and produce a JSON report with SEAM's EM and F1 scores on a small bundled LoCoMo-format fixture, end to end, in under 60 seconds, with no manual dataset download required.

A second flag must allow the full LoCoMo run when the dataset is present locally:

```bash
seam bench external locomo --dataset /path/to/locomo.json --output run.json
```

## 2. Scope (what is and is not in this PR)

In:
- Shared adapter scaffold under `benchmarks/external/common/`
- LoCoMo dataset loader (LoCoMo JSON schema → internal `BenchmarkCase` records)
- SEAM adapter that ingests conversations through SEAM runtime and answers questions through SEAM retrieval
- String-match scoring (EM, token F1, context recall)
- Quickstart fixture: 5–10 synthetic LoCoMo-format cases bundled in-repo
- CLI: `seam bench external --quickstart locomo` and `seam bench external locomo --dataset <path>`
- Wires `SEAM_BENCH_LOCOMO_COMMAND` default to invoke this adapter
- Tests
- HISTORY entry + PROJECT_STATUS update

Out (separate SOPs):
- LLM-as-judge scoring (`SOP_EXTERNAL_BENCH_LLM_JUDGE.md`)
- Mem0 comparator (`SOP_EXTERNAL_BENCH_MEM0_COMPARATOR.md`)
- Zep comparator (`SOP_EXTERNAL_BENCH_ZEP_COMPARATOR.md`)

## 3. Files to create

```
benchmarks/external/
  __init__.py
  README.md
  common/
    __init__.py
    types.py            # BenchmarkCase, AdapterAnswer, RunReport
    dataset.py          # LoCoMo loader, quickstart fixture loader
    scoring.py          # exact_match, token_f1, context_recall, aggregate
    runner.py           # generic run loop (adapter × dataset → report)
  locomo/
    __init__.py
    run.py              # CLI entrypoint
    adapters/
      __init__.py
      base.py           # MemorySystemAdapter protocol
      seam.py           # SEAM adapter
    fixtures/
      quickstart.json   # 5–10 synthetic LoCoMo-shaped cases, in-repo
```

Tests:
```
test_seam_all/
  test_locomo_dataset.py
  test_locomo_scoring.py
  test_locomo_seam_adapter.py
  test_locomo_runner_cli.py
```

## 4. Shared adapter contract

`benchmarks/external/common/types.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol

@dataclass(frozen=True)
class ConversationTurn:
    speaker: str
    text: str
    timestamp: str | None = None  # ISO 8601 when present

@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    conversation: tuple[ConversationTurn, ...]
    question: str
    gold_answer: str
    category: str | None = None  # LoCoMo question category if present

@dataclass(frozen=True)
class AdapterAnswer:
    retrieved_context: str           # joined retrieved text (always populated)
    generated_answer: str | None     # only if the adapter generates an answer
    retrieval_latency_ms: float = 0.0
    answer_latency_ms: float = 0.0

class MemorySystemAdapter(Protocol):
    name: str
    def reset(self, scope_id: str) -> None: ...
    def ingest_turn(self, scope_id: str, turn: ConversationTurn) -> None: ...
    def answer(self, scope_id: str, question: str) -> AdapterAnswer: ...
```

Rule: every adapter (SEAM, Mem0, Zep, future) implements this exact protocol. No adapter sees the gold answer.

## 5. LoCoMo dataset shape

LoCoMo cases on HuggingFace (`snap-research/locomo`) have the schema:

```json
{
  "sample_id": "conv-42",
  "conversation": {
    "speaker_a": "Alice",
    "speaker_b": "Bob",
    "sessions": [
      {
        "date_time": "2023-04-12 09:14",
        "dia_id": 1,
        "dialogs": [
          {"speaker": "Alice", "text": "..."},
          {"speaker": "Bob", "text": "..."}
        ]
      }
    ]
  },
  "qa": [
    {"question": "...", "answer": "...", "category": 1, "evidence": ["D1:5"]}
  ]
}
```

`dataset.py` flattens this to one `BenchmarkCase` per Q/A pair, sharing the conversation history. Preserve `sample_id`, `category`, and add `qa_index` to make `case_id` unique (`f"{sample_id}::q{qa_index}"`).

Quickstart fixture must use the same schema but with synthetic, short, in-repo content (~3 sessions, ~6 turns per session, 5–10 questions total). Keep it small enough that quickstart finishes in under 60 seconds on a cold cache.

## 6. SEAM adapter

`benchmarks/external/locomo/adapters/seam.py`:

```python
from seam_runtime.storage import open_storage
from seam_runtime.nl import compile_nl
from seam_runtime.search import search_ir
from seam_runtime.pack import pack_ir

class SeamLocomoAdapter:
    name = "seam"
    def __init__(self, db_path: str | None = None, budget: int = 8):
        # Use an isolated SQLite per scope_id. Default: temp dir under test_seam/.
        ...
    def reset(self, scope_id: str) -> None:
        # Drop/recreate the per-scope DB (or use a namespace filter).
        ...
    def ingest_turn(self, scope_id, turn):
        # Compile turn.text to MIRL, persist with scope=scope_id, namespace="locomo".
        # Include speaker in the compiled text so retrieval can disambiguate:
        #   "[Alice 2023-04-12 09:14] <text>"
        ...
    def answer(self, scope_id, question):
        # 1. search_ir with scope=scope_id, budget=self.budget
        # 2. pack_ir into a prompt-ready context string
        # 3. retrieved_context = packed text
        # 4. generated_answer = None  (no LLM call in this PR)
        ...
```

Key constraints:
- One SQLite per `scope_id` so cases do not leak into each other. Use `test_seam/locomo/<scope_id>.db` and clean it on `reset`.
- Compile each turn as its own NL ingest. Do not batch turns into a single compile — the adapter must mirror how a real long-running SEAM memory grows turn by turn.
- Do not call any external LLM. Generated answer stays `None`; scoring uses string-match against retrieved context plus optional later LLM-judge.

## 7. Scoring

`benchmarks/external/common/scoring.py`:

```python
import re, string
from collections import Counter

def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    text = "".join(ch for ch in text if ch not in string.punctuation)
    return " ".join(text.split())

def exact_match(pred: str, gold: str) -> float:
    return 1.0 if _normalize(pred) == _normalize(gold) else 0.0

def token_f1(pred: str, gold: str) -> float:
    pred_tokens = _normalize(pred).split()
    gold_tokens = _normalize(gold).split()
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)

def context_recall(retrieved: str, gold: str) -> float:
    # 1.0 if every token of the gold answer appears in the retrieved context.
    retrieved_tokens = set(_normalize(retrieved).split())
    gold_tokens = _normalize(gold).split()
    if not gold_tokens:
        return 1.0
    hits = sum(1 for tok in gold_tokens if tok in retrieved_tokens)
    return hits / len(gold_tokens)
```

When `generated_answer is None`, EM and F1 should be computed against `retrieved_context`. When it is present (later PRs), they should be computed against `generated_answer`. Report both `context_recall` and `answer_em` / `answer_f1` separately in the JSON so future adapters that generate answers do not look artificially better.

## 8. Runner

`benchmarks/external/common/runner.py` exposes one function:

```python
def run_benchmark(
    *,
    adapter: MemorySystemAdapter,
    cases: list[BenchmarkCase],
    progress: Callable[[int, int], None] | None = None,
) -> RunReport: ...
```

`RunReport` shape (target JSON):

```json
{
  "version": "SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/1",
  "benchmark": "locomo",
  "adapter": "seam",
  "dataset": {"source": "quickstart" | "file:<path>", "case_count": 10},
  "run_started_at": "ISO 8601",
  "elapsed_seconds": 12.3,
  "scores": {
    "context_recall_mean": 0.81,
    "answer_em_mean": 0.0,
    "answer_f1_mean": 0.0
  },
  "cases": [
    {
      "case_id": "...",
      "category": 1,
      "scores": {"context_recall": 0.83, "answer_em": 0.0, "answer_f1": 0.0},
      "retrieval_latency_ms": 14.0,
      "answer_latency_ms": 0.0
    }
  ],
  "integrity_hash": "<sha256 over cases + scores>"
}
```

Integrity hash: SHA-256 over a canonical JSON serialization of `cases` and `scores`. Document the canonicalization rule (sorted keys, no whitespace) in the module docstring.

## 9. CLI wiring

`benchmarks/external/locomo/run.py`:

```bash
python -m benchmarks.external.locomo.run --quickstart
python -m benchmarks.external.locomo.run --dataset /path/to/locomo.json --output run.json
python -m benchmarks.external.locomo.run --dataset /path/to/locomo.json --limit 20 --adapter seam
```

Update `seam_runtime/cli.py` so `seam bench external --quickstart locomo` resolves to the above. Update the registry default so `SEAM_BENCH_LOCOMO_COMMAND`, when unset, falls back to `python -m benchmarks.external.locomo.run --quickstart`. Document this in `benchmarks/external/README.md`.

## 10. Tests (required before merge)

`test_locomo_dataset.py`:
- loads `fixtures/quickstart.json` and asserts case count, conversation length, Q/A pairing
- accepts a real LoCoMo-shaped sample file and asserts schema parsing

`test_locomo_scoring.py`:
- EM: identical strings = 1.0, normalized variants ("The cat" vs "cat") = 1.0, different = 0.0
- F1: known fixtures
- context_recall: gold contained = 1.0, partial = fraction, none = 0.0

`test_locomo_seam_adapter.py`:
- ingest two turns, query for a fact in one turn, assert context_recall == 1.0
- reset clears state between scopes
- uses a temp DB under `tmp_path`, never writes to repo root

`test_locomo_runner_cli.py`:
- runs `--quickstart` via subprocess, asserts exit 0, asserts JSON output validates, asserts `integrity_hash` is present and stable across two runs on the same fixture
- asserts the run completes in under 60 seconds on the CI runner

## 11. DeepSeek implementation checklist

Work through these in order. Tick each box in the PR description as you complete it.

- [ ] SOP 0 (Phase 1+2 registry/runner) is merged on `main`; pulled latest
- [ ] Created `benchmarks/external/common/{__init__,types,dataset,scoring,runner}.py`
- [ ] `types.py` exports the four dataclasses/protocol in section 4 verbatim
- [ ] `dataset.py` loads `fixtures/quickstart.json` and parses real LoCoMo JSON shape per section 5
- [ ] `scoring.py` implements `_normalize`, `exact_match`, `token_f1`, `context_recall` per section 7
- [ ] `runner.py` exposes `run_benchmark(*, adapter, cases, progress=None) -> RunReport`
- [ ] Created `benchmarks/external/locomo/{__init__,run}.py` and `adapters/{__init__,base,seam}.py`
- [ ] `adapters/base.py` re-exports `MemorySystemAdapter` from `common.types`
- [ ] `adapters/seam.py` implements the contract in section 6, under 250 lines
- [ ] Per-scope SQLite isolation: each case opens/drops its own DB under `test_seam/locomo/<scope_id>.db`
- [ ] No LLM calls; `generated_answer` stays `None`
- [ ] Created quickstart fixture at `benchmarks/external/locomo/fixtures/quickstart.json` with 5-10 synthetic LoCoMo-shape cases
- [ ] Quickstart completes in under 60 seconds on the dev machine (`time python -m benchmarks.external.locomo.run --quickstart`)
- [ ] CLI: `python -m benchmarks.external.locomo.run --quickstart` and `--dataset <path>` and `--limit N` all work
- [ ] Updated `seam bench external --quickstart locomo` in `seam_runtime/cli.py` to dispatch to the LoCoMo runner (replaces the SOP 0 reserved-flag stub)
- [ ] Registered default for `SEAM_BENCH_LOCOMO_COMMAND` when unset: documented in `benchmarks/external/locomo/__init__.py` and `benchmarks/external/README.md`
- [ ] Result JSON validates against `SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/1` shape per section 8
- [ ] `integrity_hash` is stable across two runs on the same fixture
- [ ] Wrote all four test files in section 10; all pass
- [ ] Full test suite still passes (`pytest test_seam_all -x`)
- [ ] Updated `PROJECT_STATUS.md`: bullet under "What Is Stable" mentioning `seam bench external --quickstart locomo`
- [ ] Appended HISTORY entry per template in section 13
- [ ] `python -m tools.history.verify_continuity` passes
- [ ] `python -m tools.history.verify_integrity` passes
- [ ] Pushed branch and opened **draft** PR titled `Phase 3: SEAM LoCoMo adapter (string-match scoring)`

## 12. Reviewer verification checklist

- [ ] `time seam bench external --quickstart locomo` exits 0 in under 60 seconds on a clean Linux/WSL machine
- [ ] Output JSON has `version: SEAM-EXTERNAL-MEMORY-BENCHMARK-RESULT/1`, `benchmark: locomo`, `adapter: seam`, non-empty `cases`, populated `scores.context_recall_mean`, and a `integrity_hash` field
- [ ] Two consecutive `--quickstart` runs produce identical `integrity_hash`
- [ ] `seam bench external --quickstart locomo --output /tmp/run.json` writes a JSON file with the same shape
- [ ] `python -m benchmarks.external.locomo.run --dataset <path> --limit 3` works against any real LoCoMo JSON sample (reviewer supplies one if available; skip otherwise with a note)
- [ ] `pytest test_seam_all/test_locomo_dataset.py test_seam_all/test_locomo_scoring.py test_seam_all/test_locomo_seam_adapter.py test_seam_all/test_locomo_runner_cli.py -v` passes
- [ ] `pytest test_seam_all -x` passes (full suite)
- [ ] No network call observed during `--quickstart` (run with `strace -f -e trace=connect` or equivalent and confirm only loopback)
- [ ] No writes outside `test_seam/`, the per-run output path, and stdout: `find . -newer <pre-run-timestamp> -type f -not -path './test_seam/*' -not -path './.git/*'` should be empty
- [ ] `python -m tools.history.verify_continuity` passes
- [ ] `seam doctor` still returns PASS
- [ ] Adapter file `benchmarks/external/locomo/adapters/seam.py` is under 250 lines
- [ ] Scoring file `benchmarks/external/common/scoring.py` has zero third-party imports
- [ ] `grep -RE "(sk-[A-Za-z0-9]{20,}|anthropic|openai|claude\.ai/(chat|share))" benchmarks/external/` returns nothing (no LLM client, no API key leak)
- [ ] Quickstart fixture is synthetic, not derived from the real LoCoMo dataset (verify by reading 2-3 cases — text should be clearly invented)
- [ ] PR description ticks every box in section 11

## 13. Acceptance commands (single block — copy and run)

```bash
pip install -e .

# Quickstart timing
time seam bench external --quickstart locomo --output /tmp/locomo_quickstart.json
jq '.version, .benchmark, .adapter, .scores, .integrity_hash' /tmp/locomo_quickstart.json

# Stable integrity hash
seam bench external --quickstart locomo --output /tmp/run_a.json
seam bench external --quickstart locomo --output /tmp/run_b.json
diff <(jq .integrity_hash /tmp/run_a.json) <(jq .integrity_hash /tmp/run_b.json)

# Module-direct invocation
python -m benchmarks.external.locomo.run --quickstart --output /tmp/direct.json

# Tests
pytest test_seam_all/test_locomo_dataset.py \
       test_seam_all/test_locomo_scoring.py \
       test_seam_all/test_locomo_seam_adapter.py \
       test_seam_all/test_locomo_runner_cli.py -v
pytest test_seam_all -x

# Continuity
python -m tools.history.verify_continuity
python -m tools.history.verify_integrity
seam doctor
```

## 14. Pitfalls and notes

- **Do not bundle the real LoCoMo dataset in the repo.** It is gated on HF. The quickstart fixture is synthetic LoCoMo-shaped data. Document where to download the real dataset in `benchmarks/external/README.md`.
- **Do not call out to any LLM.** This PR is string-match only. LLM-judge is the next SOP.
- **Scope isolation matters.** Each LoCoMo case is a separate long conversation. Cases must not leak into each other. Use one SQLite per scope_id and drop it on reset.
- **Keep the adapter under 250 lines.** If you find yourself building a full retrieval pipeline inside the adapter, push that complexity back into `seam_runtime` instead.
- **Tokenizer-free F1.** Use whitespace split + lowercase + punctuation strip. Do not import tiktoken or any tokenizer here. The benchmark must run with zero ML deps.

## 15. HISTORY entry template

```yaml
id: NNN
date: <ISO date>
agent: deepseek
status: done
topics: [benchmark, fixture, retrieval]
commits: [<sha>]
refs:
  - benchmarks/external/common/*
  - benchmarks/external/locomo/*
  - test_seam_all/test_locomo_*.py
  - docs/SOP_EXTERNAL_BENCH_LOCOMO_SEAM_ADAPTER.md
supersedes: <last bench entry id>
tokens: ~<count>
body: |
  Implemented SEAM LoCoMo adapter (Phase 3) per SOP. Quickstart fixture, EM/F1
  scoring, and CLI wiring. seam bench external --quickstart locomo runs in <N>s
  on local machine. No comparator adapters yet; next: Mem0 (SOP_EXTERNAL_BENCH_MEM0_COMPARATOR.md).
```

## 16. Estimated scope

~1200–1800 lines net. One review cycle. No dependencies added beyond what SEAM already ships.
