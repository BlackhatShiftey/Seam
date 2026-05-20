# SOP — Critical Benchmarkability Fix

Date authored: 2026-05-20
Author: claude-opus-4-7 (audit pass)
Status: proposed; requires operator approval before execution
Scope: smallest viable patch that makes SEAM's external memory benchmarks
produce meaningful, non-stub deterministic numbers.

## Why this is P0 above every other open track

The single LoCoMo quickstart benchmark is the only external memory benchmark
currently wired end-to-end (Track I), and it returns:

```
context_recall_mean: 0.0
answer_em_mean:      0.0
answer_f1_mean:      0.0
judge_score_mean:    1.0   # stub always returns "correct"
```

Reproduce:

```
.venv/bin/python -m seam bench external --quickstart locomo \
  --adapter seam --judge stub --output /tmp/seam-locomo.json
.venv/bin/python -c "import json; d=json.load(open('/tmp/seam-locomo.json')); \
  print(d['aggregate'])"
```

This is a fake green: every deterministic metric is zero, and the only
"passing" number comes from a stub judge that always returns 1.0. Comparator
numbers against Mem0/Zep are meaningless until SEAM can actually score
non-zero on the standard memory-retrieval rubric.

## Root cause (reproduced)

`benchmarks/external/locomo/adapters/seam.py::SeamLocomoAdapter.answer()`
calls `runtime.search_ir(...)` then `runtime.pack_ir(..., lens="general",
budget=self.budget)` with no `mode` argument, so the pack defaults to
`mode="context"` in `seam_runtime/pack.py:11`.

In context mode (seam_runtime/pack.py:29-54), each entry is rendered as a
compact CLM/STA signal — predicate/subject/object — where the object field
is an underscore-joined entity hash like
`alice_2023-04-12_i_ve_always_wanted_visit_japan_cherry_blossoms`.

The original text lives in RAW records (`payload_json.attrs.content`,
schema confirmed in `seam_runtime/storage.py` table `ir_records` plus
`raw_docs`/`raw_spans`). RAW records are not pulled into the search result
candidates and not surfaced into the pack.

Downstream, `benchmarks/external/common/scoring.py::context_recall` does:

```python
retrieved_tokens = set(_normalize(retrieved).split())
hits = sum(1 for tok in gold if tok in retrieved_tokens)
```

`_normalize` lowercases, strips punctuation, splits on whitespace. The token
`japan` exists inside the compound string
`alice_2023-04-12_i_ve_always_wanted_visit_japan_cherry_blossoms` but never
as a whitespace-delimited token after normalization, so it never matches.
Result: zero recall, zero EM, zero F1, every case, every conversation.

Confirmed by manual reproduction on three conversations × four questions:
0/12 gold tokens hit retrieved-context tokens.

## Acceptance gate

The fix is correct when, on the unchanged `quickstart.json` fixture:

1. `seam bench external --quickstart locomo --adapter seam --judge stub`
   reports `context_recall_mean > 0.5` (at least half the gold answer tokens
   appear in retrieved context).
2. `answer_em_mean` and `answer_f1_mean` remain reportable numbers (may stay
   low without a generator — that's expected; this SOP does not add an LLM
   answerer). The acceptance is that they reflect real retrieval, not
   pack-format opacity.
3. The retrieved context still respects `budget` (token-bounded; no
   unbounded RAW dumps).
4. Existing `test_seam_all/`, `tools/streams/`, `tests/` suites still pass
   in full (currently 463 passed, 4 skipped).
5. BIL-2 seal/verify on the new run still passes — i.e. the result hash
   stays deterministic across reruns.
6. All four SEAM verify gates green (integrity, continuity, routing,
   streams).

## Operator decision point (sign off before execution)

This SOP chooses to make SEAM testable by having the **adapter** materialize
the readable evidence text that the **pack** elides. The alternative
interpretation is "the pack IS SEAM's answer; if scoring sees zero, the
pack should change." This SOP rejects that alternative because:

- `pack.py` context-mode is consumed by REST `/context`, MCP `seam_context`,
  the dashboard chat panel, and the surface library. Changing its default
  shape has a wide blast radius and would mask the actual SEAM property
  (graph-first packs).
- The benchmarks measure retrieval, not pack format. Standardized scoring
  (LoCoMo / Mem0 / Zep) expects token-overlap on text; that is a property
  of the comparison surface, not of SEAM internals.

**If the operator disagrees and wants context-mode packs to embed evidence
text by default**, stop here and revise this SOP before any code changes —
that is a different, larger patch.

## Recommended fix (minimal patch surface)

Do NOT change pack semantics or runtime defaults. Change only the LoCoMo
adapter's retrieval surface.

### Step 1 — expand the evidence closure and pack as exact-mode

`SeamRuntime.store` is a public attribute (`SQLiteStore`, see
`seam_runtime/runtime.py:36`). `store.load_ir(ids=[...])` is the canonical
record lookup. We reuse those, plus the already-implemented
`pack_ir(..., mode="exact")` path, instead of writing SPAN-slicing helpers.

In `benchmarks/external/locomo/adapters/seam.py::SeamLocomoAdapter.answer`,
after the existing `search_ir` call, build the closure of records that
includes each candidate plus its referenced SPAN/PROV/RAW chain, then
pack that closure with `mode="exact"`:

```python
# After: result = rt.search_ir(question, scope=..., budget=self.budget)
closure_ids: set[str] = set()
for cand in result.candidates:
    closure_ids.add(cand.record.id)
    closure_ids.update(cand.record.evidence or [])
    closure_ids.update(cand.record.prov or [])

# First load: pull SPAN records so we can chase their raw_id refs
first_batch = rt.store.load_ir(ids=list(closure_ids)) if closure_ids else None
if first_batch is not None:
    for rec in first_batch.records:
        if rec.kind.value == "SPAN":
            raw_id = rec.attrs.get("raw_id")
            if raw_id:
                closure_ids.add(raw_id)

if not closure_ids:
    return AdapterAnswer(retrieved_context="",
                        retrieval_latency_ms=retrieval_latency_ms)

pack = rt.pack_ir(sorted(closure_ids), lens="general",
                  budget=self.budget, mode="exact")
retrieved_context = json.dumps(pack.to_dict(), sort_keys=True, indent=2)
```

Why exact-mode: it preserves full `attrs`, which for RAW records means
`attrs.content` (the original text). That makes `_normalize().split()` in
`scoring.py` actually find gold tokens. Reproduced manually on the
quickstart fixture: with closure expansion, "japan", "cherry", "osaka"
all appear as whitespace-delimited tokens; without it (context mode),
zero hits.

Trade-off: exact-mode packs are larger. Mitigation: keep
`budget=self.budget` (default 2000 tokens) and rely on `pack_ir`'s own
budget enforcement to cap closure size. Document in the adapter that
`budget` is a token budget on the packed output, not on raw text bytes.

### Step 2 — make the change an adapter-level switch, not a runtime change

Add a constructor flag `include_evidence_closure: bool = True` so the
behavior is opt-out for any future micro-benchmark that wants to measure
pure-CLM/STA retrieval. Default ON because the benchmarks SOP gate
requires text surfacing. When False, fall back to today's
`mode="context"` pack call (the current behavior).

Cross-check: confirm `pack_ir(mode="exact")` does not produce records
that fail validation when the closure is incomplete (e.g. CLM without
its PROV). The reproduction in this audit showed `missing_provenance`
errors when CLM was packed alone; the closure step above resolves that
because PROV and SPAN ids are included before pack_ir runs. Add an
assertion: if `pack_ir` raises ValueError on the closure, log the
issue ids and fall back to context-mode for that one case rather than
crashing the bench run.

### Step 3 — refresh quickstart score baseline

Re-run `seam bench external --quickstart locomo --adapter seam --judge stub`
and re-seal with `seam bench seal --level BIL-2 --allow-stub-seal` (stub
judge still requires the override per HISTORY#217). Confirm
`seam bench verify` reports 4/4 checks.

### Step 4 — add regression test

`tests/audit/test_locomo_adapter_evidence_text.py`:

- Ingests two short turns containing "Tokyo" and "Kyoto" via the adapter.
- Calls `adapter.answer(scope_id, "Where did Alice go in Japan?")`.
- Asserts `"tokyo"` or `"kyoto"` appears as a whitespace-delimited token in
  `_normalize(answer.retrieved_context).split()`.
- Asserts retrieved_context length stays under `budget * 4` chars.

This pins the contract: SEAM adapter retrieval is queryable in plain
tokens, regardless of pack representation.

### Step 5 — non-goals (explicitly deferred, do not bundle)

- Do NOT change `pack.py` default mode. The pack stays graph-first; that's
  a SEAM design property.
- Do NOT change `scoring.py` to do fancy matching against
  underscore-joined entity hashes. Scoring stays consistent with how Mem0,
  Zep, and the LoCoMo paper match tokens.
- Do NOT switch the default judge from stub to claude/openai in this SOP.
  That is a separate decision with key/cost implications; see
  `SOP_BENCHMARKABLE_STATE_ROADMAP.md` Step 3.
- Do NOT add a generator LLM that produces `generated_answer`. EM/F1 will
  stay informational until a separate SOP adds that. Recall is the one
  metric we MUST unblock here.

## Verify chain after landing

Per AGENTS.md and `tools/claude/preflight_protocol.sh`:

```
.venv/bin/python -m pytest test_seam_all/ tools/history/test_history_tools.py \
                          tools/streams/ tests/ -q
.venv/bin/python -m tools.history.verify_integrity
.venv/bin/python -m tools.history.verify_continuity
.venv/bin/python -m tools.history.verify_routing
.venv/bin/python -m tools.streams.verify_streams
```

Then append a HISTORY.md entry with refs covering
`benchmarks/external/locomo/adapters/seam.py`,
`tests/audit/test_locomo_adapter_evidence_text.py`, the new sealed bundle
path under `benchmarks/runs/`, and `supersedes: 218`.

## Estimated cost

- Adapter change: ~60 lines.
- Regression test: ~40 lines.
- Re-seal + verify: 1 command pair.
- Documentation update (`benchmarks/external/README.md`): 1 paragraph
  noting the new evidence_text field.
- Risk surface: adapter-only; runtime/REST/MCP/dashboard untouched.
