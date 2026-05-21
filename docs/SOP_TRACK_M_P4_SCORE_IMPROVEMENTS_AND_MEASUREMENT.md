# SOP — Track M P4 Score-Improvement Pass + Baseline Measurement

Issued: 2026-05-21
Owner pattern: DeepSeek implements on its own branch; Claude reviews each diff
and commits per item; operator paste-relays. DeepSeek never commits or pushes.

## Scope

Two coupled goals in one SOP:

1. **Baseline measure** — run real LoCoMo with real answerer + real judge on
   current `main` so the impact of P0/P1/P2/P3 is quantified. The
   `run_a.json` numbers in scrollback are retrieval-only (no answerer); we have
   never produced a real EM/F1 number with the landed work.
2. **Land the 3 remaining "next-track" score-improvement items** the operator
   earmarked: temporal distance scoring, cross-encoder re-ranker, embedding
   model upgrade. (BEAM directory ingestion and LongMemEval haystack_date
   wiring already landed in commit `051778c`.)
3. **Final measure** — re-run real LoCoMo so the impact of the three new fixes
   is quantified vs the baseline.

This SOP exists because:

- The 5 P3 score-moving fixes (BM25, real embedding enforcement, multi-hop
  decomposition, temporal-token filter, abstention) are in code but
  empirically unmeasured.
- The 3 remaining "next-track" items are scoped against retrieval signal
  modes that the current adapter does not yet exploit.

## Branch

```bash
git switch main
git pull --ff-only origin main
git switch -c deepseek/track-m-p4-score-improvements
```

DeepSeek works in this branch and leaves diffs uncommitted between items so
the operator paste-relays each diff back to Claude for review and per-item
commit.

## Required first reads (in order)

1. `PROJECT_STATUS.md`
2. `REPO_LEDGER.md`
3. `HISTORY_INDEX.md`
4. `docs/CODE_LAYOUT.md`
5. `docs/DATA_ROUTING.md`
6. `docs/SOP_TRACK_M_P1_REAL_BENCHMARK_RUNS.md` (the dataset / judge / BIL-2
   protocol this SOP composes on top of)
7. `docs/SOP_TRACK_M_P2_LOCOMO_RETRIEVAL_WIRING.md` (what landed in P2)
8. `docs/SOP_TRACK_M_P3_LOCOMO_SCORE_IMPROVEMENTS.md` (what landed in P3)
9. `benchmarks/external/locomo/adapters/seam.py` (current adapter — read
   the ranking formula, the answerer wiring, and the temporal filter)
10. `seam_runtime/vector.py` (current INDEXABLE_KINDS + render_record_text)
11. `seam_runtime/models.py` (embedding settings + provider switching)

Do **not** read all of `HISTORY.md`. Use bounded context packs:

```bash
python -m tools.history.build_context_pack --topics retrieval,vector,benchmark --latest 12
```

## Inputs required from operator

The agent must not download datasets into the repo. The operator provides:

- `LOCOMO_DATASET_PATH` — full LoCoMo JSON (already set per
  `~/.config/seam/track_m.env`).
- `ANTHROPIC_API_KEY` and / or `OPENAI_API_KEY` — for both `--answerer` and
  `--judge`. Real-judge competitive evidence requires at least one.
- Optional: model selection envs (e.g. `OPENAI_EMBEDDING_MODEL`) if the
  embedding upgrade picks a non-default cloud model.

If an input is missing, run the relevant smoke or dry-run validator and
report the missing variable. Do not fake numbers.

## Hard rules

1. Each fix is **one focused commit** at review time. DeepSeek leaves the
   diff in the worktree; Claude reviews and commits.
2. Each fix has **at least one regression test** under `tests/audit/` that
   exercises the new behavior with a deterministic fixture (no network at
   test time).
3. **Quickstart smoke** (`seam bench external --quickstart locomo`) must
   continue to report `context_recall_mean >= 0.90` after every fix. Run it
   between fixes.
4. **Ranking weights** in the LoCoMo adapter must not be changed without an
   A/B comparison report attached to the handback (quickstart numbers
   before/after).
5. **No silent fallback**. P3 Fix 2's principle stands: if a cloud embedding
   provider is missing its API key, fail loudly. Do not pivot to a hash or
   "local" model without an explicit `--embedding-fallback` flag and an
   operator note in the run output.
6. **Do not commit downloaded datasets, result bundles, API responses, local
   `.env` values, SQLite test artifacts, provider session URLs, or private
   conversation links.** Real result bundles live outside the repo; the
   handback records command + path placeholder + result hash + fixture hash
   + BIL level + verification status only.
7. **Stub judge results remain smoke-only.** Real evidence requires
   `--judge claude` or `--judge openai`.

## Step 0 — Baseline measurement (mandatory before any code change)

Establish a baseline of the current state so the three fixes can be
attributed to score deltas:

```bash
# Quickstart baseline (10 cases, deterministic fixture)
seam bench external --quickstart locomo --judge openai --answerer openai \
  --judge-model gpt-5-nano > /tmp/p4_baseline_quickstart.json

# Full real LoCoMo (1,542 answerable cases) — operator-gated, expensive
seam bench external locomo \
  --dataset-path "$LOCOMO_DATASET_PATH" \
  --judge openai --answerer openai --judge-model gpt-5-nano \
  --output /tmp/p4_baseline_locomo.json
```

Then seal both as BIL-2:

```bash
seam bench seal --level BIL-2 /tmp/p4_baseline_quickstart.json
seam bench seal --level BIL-2 /tmp/p4_baseline_locomo.json
```

Record in the handback:

- bundle hashes for both sealed runs
- `scores.context_recall_mean`, `scores.answer_em_mean`, `scores.answer_f1_mean`
- per-category breakdown
- fixture hash
- elapsed seconds
- judge model used

If the baseline already exceeds publication-readiness thresholds, surface
that fact — the score-improvement work may be partially or entirely
unnecessary.

## Step 1 — Temporal distance scoring

**Current state.** P3 Fix 4 added a temporal-token filter that boosts
candidates whose timestamp tokens *match* date strings extracted from the
question. It is a binary boost: match or no match.

**Goal.** Replace (or supplement) the binary filter with a calendar-distance
score so questions like *"what happened last summer"* boost candidates
within a temporal window, with the score decaying monotonically with
distance.

**Implementation sketch.**

1. Add `temporal_distance_score(question_date_ref: datetime,
   candidate_timestamp: datetime) -> float` to
   `benchmarks/external/locomo/adapters/seam.py` (or a new helper module).
   Score: `1.0 / (1.0 + days_apart / decay_constant)` with
   `decay_constant=30`.
2. Question date-ref extraction: extend the existing date-token parser to
   also produce a reference `datetime` for relative phrases ("yesterday",
   "last week", "two months ago"). Anchor relative phrases to the
   conversation's earliest turn timestamp (not "now") so adversarial rows
   without dates fall back to the existing token-match path.
3. Wire into the ranking formula at the same weight slot as the current
   temporal channel (`0.10` per the P3 SOP's `0.40 lex + 0.35 sem + 0.15
   graph + 0.10 temporal` weights). Do **not** change the weights.

**Test.** `tests/audit/test_temporal_distance_score.py`:

- Synthetic case: question "what happened three weeks ago" with
  conversation anchor `2024-01-01`. Candidates timestamped 21, 30, 60, 180,
  365 days from anchor. Assert scores are monotonically decreasing.
- Synthetic case: question with no date reference. Assert
  `temporal_distance_score` returns `0.0` (fall through to the existing
  token-match path).
- Synthetic case: candidate with no timestamp. Assert
  `temporal_distance_score` returns `0.0`.

**Verification.** Quickstart smoke holds `context_recall_mean >= 0.90`.

## Step 2 — Cross-encoder re-ranker

**Current state.** The LoCoMo adapter ranks candidates with a bi-encoder
cosine over independent query/candidate embeddings. Bi-encoders are fast
but lose joint query-candidate signal.

**Goal.** After initial retrieval narrows to top-K (default `K=20`),
re-rank with a cross-encoder model that reads `(query, candidate)` jointly
and produces a relevance score. The cross-encoder is too expensive for
full-corpus search but cheap on top-K.

**Implementation sketch.**

1. Add a `--rerank cross-encoder` flag to
   `benchmarks/external/locomo/run.py`. Default: off (no behavior change
   without the flag).
2. New module `benchmarks/external/locomo/rerank.py` exposing
   `cross_encoder_rerank(query: str, candidates: list[str],
   model: str = "cross-encoder/ms-marco-MiniLM-L6-v2") -> list[float]`.
   Use `sentence_transformers` if installed; raise a clear `RuntimeError`
   with install hint otherwise.
3. In the adapter's search path: if rerank is enabled, take the top-K
   bi-encoder results, run cross-encoder, and re-sort by the new scores.

**Test.** `tests/audit/test_cross_encoder_rerank.py`:

- Mock cross-encoder via a stub function. Verify the adapter reorders
  candidates per stub scores.
- Verify the flag is off by default and the existing ranking is unchanged
  when the flag is absent.
- Verify a clear error message is raised when `sentence_transformers` is
  not installed.

**Verification.**

- Quickstart smoke with `--rerank cross-encoder` (operator must have
  `sentence_transformers` installed) holds `context_recall_mean >= 0.90`.
- Quickstart smoke without the flag is byte-equivalent to the baseline.

## Step 3 — Embedding model upgrade

**Current state.** P3 Fix 2 added enforcement that benchmark runs reject
hash / deterministic embedding models, requiring a real provider. But the
default embedding model in `seam_runtime/models.py` is still the hash
provider for non-benchmark paths. The "next-track" upgrade is to make a
real embedding model the **library default** for new SEAM installs (with
the hash model retained for tests + offline operation).

**Implementation sketch.**

1. Default `SeamRuntime.embedding_model` to a real SBERT model
   (`sentence-transformers/all-MiniLM-L6-v2`) when
   `sentence_transformers` is importable.
2. Fall back to the hash model **only when** `sentence_transformers` is
   missing **and** an explicit `SEAM_EMBEDDING_FALLBACK_HASH=1` env var is
   set. Otherwise raise a clear error pointing at the optional extra.
3. Update `seam_runtime/installer.py` to install
   `sentence-transformers` as part of `seam[dev]` (and possibly the
   default install — operator call).
4. Document in `README.md`: real embeddings are now the default; offline
   workflows must set `SEAM_EMBEDDING_FALLBACK_HASH=1`.

**Test.** `tests/audit/test_default_embedding_real_when_sbert_present.py`:

- With `sentence_transformers` importable: `SeamRuntime()` uses SBERT.
- With `sentence_transformers` import patched to raise: `SeamRuntime()`
  raises a clear error.
- With `SEAM_EMBEDDING_FALLBACK_HASH=1` and `sentence_transformers`
  patched: `SeamRuntime()` falls back to hash with a stderr warning.

**Verification.**

- Quickstart smoke with default config holds `context_recall_mean >= 0.90`
  (better than baseline because semantic channel is no longer collapsed).
- Existing test suite (`pytest test_seam_all/test_seam.py`) passes with
  `SEAM_EMBEDDING_FALLBACK_HASH=1` set globally (tests are
  deterministic-fixture and should keep using hash).

## Step 4 — Final measurement

Re-run both the quickstart and the full LoCoMo with all three fixes
applied:

```bash
# Quickstart final
seam bench external --quickstart locomo --judge openai --answerer openai \
  --judge-model gpt-5-nano --rerank cross-encoder \
  > /tmp/p4_final_quickstart.json

# Full real LoCoMo final
seam bench external locomo \
  --dataset-path "$LOCOMO_DATASET_PATH" \
  --judge openai --answerer openai --judge-model gpt-5-nano \
  --rerank cross-encoder \
  --output /tmp/p4_final_locomo.json
```

Seal both as BIL-2 and produce a baseline-vs-final diff:

```bash
seam bench seal --level BIL-2 /tmp/p4_final_quickstart.json
seam bench seal --level BIL-2 /tmp/p4_final_locomo.json

seam benchmark diff /tmp/p4_baseline_quickstart.json /tmp/p4_final_quickstart.json
seam benchmark diff /tmp/p4_baseline_locomo.json /tmp/p4_final_locomo.json
```

## Handback format

DeepSeek's final handback (paste-relayed back to Claude) must include:

```
Fix N: <name>
File(s) changed: <paths>
Test: <test file> — N passed
Quickstart smoke: context_recall_mean = X
Diff vs baseline (per fix): EM ΔX, F1 ΔY
────────────────────────────────────────
```

Plus:

- **Baseline run summary**: command, bundle hash, fixture hash, score
  triplet (EM, F1, recall), elapsed seconds, judge model.
- **Final run summary**: same fields.
- **Per-fix attribution** if possible (run quickstart between fixes).
- **BIL-2 bundle hashes** for both runs.
- **Any rejected approaches** with reasoning.

## What "done" looks like

1. Three commits land on `main` (one per fix), each with a passing
   `tests/audit/` regression.
2. Quickstart smoke remains `context_recall_mean >= 0.90` at every step.
3. Final real LoCoMo run has materially better EM and F1 than baseline,
   sealed BIL-2, recorded in HISTORY with bundle hashes.
4. `validate_publication_readiness()` returns publication-ready for the
   final bundle.
5. HISTORY entry documents baseline scores, final scores, per-fix
   attribution, and BIL-2 evidence.

If any fix regresses the quickstart below `0.90` or fails to move the
final benchmark forward, hold the commit and report the regression instead
of pushing through.
