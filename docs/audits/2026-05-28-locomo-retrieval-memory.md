# LoCoMo / Retrieval / Memory Audit — 2026-05-28

Combined audit: SEAM retrieval scoring + memory pipeline + code-quality pass over HISTORY#268. Findings ordered by expected impact on LoCoMo `context_recall_mean`.

Baseline at audit time: **0.528** at `search_top_k=20`, 100-case no-paid slice (HISTORY#242). Per-category breakdown: cat1=0.374 (single-hop), cat2=0.634 (temporal), cat3=0.242 (multi-hop), cat4=0.605 (open-domain).

## P0 — Retrieval scoring (direct LoCoMo lift)

### P0-1: Semantic fallback collapses to lexical when no vector scores supplied
- **File:** `seam_runtime/retrieval.py:36`
- **Symptom:** `_semantic_score` is a `Counter`-cosine over the same tokens as lexical. When `vector_scores={}`, the 35% "semantic" weight is a second lexical channel, giving ~75% effective lexical weight.
- **Fix:** make `_semantic_score` return `0.0` when no vector scores were passed, OR raise so callers that bypass `rt.search_ir` are caught.
- **Expected lift:** +0.03–0.06 on cat-1 and cat-3 (paraphrase-heavy).
- **Reference:** Mem0 README — multi-signal fusion (semantic + BM25 + entity) in parallel, not stacked-lexical.

### P0-2: BM25 only fires on RAW records
- **File:** `seam_runtime/retrieval.py:34`
- **Symptom:** CLM/STA/EVT/REL records use only naive Jaccard `_lexical_score` with no length normalization. Causes the ENT/CLM-displaces-RAW failure mode confirmed in HISTORY#240.
- **Fix:** index ALL record kinds in `BM25Index`, OR switch the four channels to Reciprocal Rank Fusion (RRF, k≈60) instead of weighted sum.
- **Expected lift:** +0.02–0.04; unblocks future ingest format changes without RAW displacement regression.

### P0-3: `parse_temporal_reference` fires 0/1542 LoCoMo questions
- **Files:** `seam_runtime/temporal.py:54-66`, `benchmarks/external/locomo/adapters/seam.py:364`
- **Symptom:** Per HISTORY#241 audit: regex misses LoCoMo's actual question phrasings ("how long ago", "when did X happen", "before/after Y").
- **Fix:** broaden `detect_temporal_tokens` patterns; add an entity-anchored fallback so a known scope entity sets `temporal_reference`.
- **Expected lift:** cat-2 (temporal) currently 0.634 *despite* parse never firing — closing the gap could push cat-2 to 0.75+.

## P0 — Production correctness (from CodeRabbit)

### P0-4: `signal_handler` bypasses `ShutdownState` and conflicts with uvicorn
- **File:** `seam_runtime/server.py:537-548`
- **Symptom:** `run_server` registers a custom `signal.signal()` handler that raises `SystemExit(0)`. Uvicorn has its own graceful SIGTERM/SIGINT handlers; the SEAM handler overrides them and short-circuits drain. `ShutdownState.trigger_shutdown()` (just landed in HISTORY#268) is never invoked from production.
- **Fix:** remove the `signal.signal()` registrations OR replace the body with `shutdown_state.trigger_shutdown()` + `_cleanup_runtime(runtime)`. Don't raise `SystemExit`.

## P1 — Architecture (compounding)

### P1-1: Hard-coded weights with no normalization
- **File:** `seam_runtime/retrieval.py:48` — `0.4*lex + 0.35*sem + 0.15*graph + 0.10*temp`
- **Fix:** switch to Reciprocal Rank Fusion across channels. No per-channel weight tuning needed.
- **Reference:** [Azure RRF for hybrid search](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking)

### P1-2: Cross-encoder reranker is off by default
- **File:** `benchmarks/external/locomo/adapters/seam.py:47-50` — `rerank=None`
- **Fix:** default `rerank="cross-encoder"` when `sentence-transformers` is installed. Cost ≈ 50ms per question.
- **Expected lift:** strongest on cat-3 multi-hop (currently 0.242). Likely +0.04–0.08 on that slice.

### P1-3: `_cleanup_runtime` is dead code in production
- **File:** `seam_runtime/server.py:69-79` (CodeRabbit M1)
- **Fix:** wire into the shutdown path or the lifespan shutdown hook.

### P1-4: `_shutdown_timeout_from_env` is unused
- **File:** `seam_runtime/server.py:60-66` (CodeRabbit m1)
- **Fix:** call from the shutdown flow and pass into `wait_drain(timeout)`.

### P1-5: Silent-skip pattern in `TestShellIntegration`
- **File:** `tests/audit/test_shell_security.py:234-313` (CodeRabbit m3)
- **Symptom:** `if hasattr(TextualDashboardApp, "_run_shell_subprocess"):` silently skips assertions when Textual is missing. **Violates the operator's "NEVER SKIP TEST" rule.**
- **Fix:** replace with `pytest.importorskip("textual")` at the class level or `pytest.mark.skipif` with reason.

## P2 — Polish

### P2-1: Pool blocking-get bypasses validation
- **File:** `seam_runtime/pool.py:84-92` (CodeRabbit m2 + my audit P1 #6)
- **Fix:** validate connection from blocking `get()` the same as the fast path; loop until validation passes or timeout.

### P2-2: Pool validation held under checkout lock
- **File:** `seam_runtime/pool.py` — serializes all checkouts on `SELECT 1`
- **Fix:** drop the lock during `_validate_connection`.

### P2-3: `_lexical_score` no record-length normalization
- **File:** `seam_runtime/retrieval.py:96-97`
- **Fix:** subsumed by P0-2 if RRF lands; otherwise add BM25-style `(k+1)*tf / (k*(1-b+b*|d|/avgdl) + tf)`.

### P2-4: `_temporal_score` is a 1.0/0.2 toggle
- **File:** `seam_runtime/retrieval.py:113-114` — 10% of every score is near-constant.
- **Fix:** decay against scope anchor with `temporal_distance_score`.

### P2-5: `_graph_score` matches neighbor IDs via substring
- **File:** `seam_runtime/retrieval.py:108-109`
- **Fix:** real graph traversal: BFS one hop, score neighbors by their own `_lexical_score` against the query.

### P2-6: HISTORY#268 used non-vocab topic `hardening`
- **File:** `HISTORY.md:5707` (CodeRabbit M2)
- **Caveat:** HISTORY is append-only per CLAUDE.md. **Do not edit #268.** Use `harden` in future entries.

### P2-7: Storage retry-block duplication
- 4 copies of the same `for attempt in range(3): try: ... except sqlite3.OperationalError` block. Replace with `@retry_db_operation` from `seam_runtime/retry.py`.

## Recommended next slice

**Bundle into one follow-up PR (HISTORY#269):**
- P0-4 (signal handler) + P1-3 + P1-4 + P1-5 — mechanical, ~50 lines, fixes production correctness gap from HISTORY#268.
- P0-1 + P0-2 — retrieval scoring fixes, testable in one warm-DB sweep against the 100-case baseline.

That keeps the production-correctness debt and the LoCoMo lift in one cohesive landing. Defer P0-3 (temporal parsing) to its own PR since it needs more diagnostic work to pick the right phrasings.

## Verification command

```bash
source .venv/bin/activate
LOCOMO_PATH=/home/terrabyte/seam_benchmarks/track_m/locomo/locomo10.json
DB=/tmp/seam-track-m/iter_db
.venv/bin/python -m benchmarks.external.locomo.run \
  --dataset "$LOCOMO_PATH" --adapter seam \
  --limit 100 --answerer none --judge none \
  --keep-db --db-path "$DB" \
  --output /tmp/seam-track-m/post_269_audit.json
.venv/bin/python -m benchmarks.external.locomo.audit \
  --result /tmp/seam-track-m/post_269_audit.json \
  --dataset-path "$LOCOMO_PATH" \
  --output /tmp/seam-track-m/post_269_audit_summary.json
# Compare context_recall_mean and per-category breakdown against 0.528 baseline
```

## Pitfalls

1. **Tuning on the full LoCoMo set then claiming improvement** — always run scoring changes against the dev partition only (`tools/h2/holdout_split.py`); reserve holdout for publish-time. Triggers on any search_top_k or fusion-K sweep.
2. **Format changes silently displace RAW at fixed `search_top_k`** — HISTORY#240's reverted speaker-format change went 0.495 → 0.461. Before any ingest-format change, re-run the 100-case warm-DB slice AND check per-category breakdown.
3. **Paid LoCoMo runs without explicit operator approval** — `--answerer openai`/`--judge openai` always need operator confirmation per memory rule. The 325 "high-recall unknown" diagnostic in HISTORY#241 requires paid answerer; ask first.

## Source references

- [LoCoMo paper (arXiv:2402.17753)](https://arxiv.org/abs/2402.17753) — 4 question categories, 300 turns / 9K tokens per conversation
- [Mem0 paper (arXiv:2504.19413)](https://arxiv.org/abs/2504.19413) — fused semantic + BM25 + entity scoring, +26% over OpenAI memory
- [Mem0 README](https://github.com/mem0ai/mem0) — multi-signal retrieval, LoCoMo 91.6
- [Azure RRF](https://learn.microsoft.com/en-us/azure/search/hybrid-search-ranking) — scale-free fusion across heterogeneous channels
- SEAM HISTORY#240 — k=20 baseline 0.495, ENT/CLM-displaces-RAW failure mode
- SEAM HISTORY#241 — `parse_temporal_reference` fires 0/1542 questions
- SEAM HISTORY#242 — SQLite load-order fix; baseline lifted to 0.528 at k=20
- SEAM HISTORY#268 — ShutdownState API landed; production wiring gap discovered in this audit
