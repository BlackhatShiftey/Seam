# cat1 / cat3 Multi-hop Retrieval — Scope

Date: 2026-06-15. Baseline: HISTORY#317 (clean ingest, regex enrichment off).

## 1. The problem, diagnosed (measured, not assumed)

Paid judged LoCoMo (100 cases, gpt-4o-mini answerer+judge) gives **judge_score 0.40**
(23 correct / 34 partial / 43 incorrect). The two weak categories, bucketed by
*why* each wrong case failed (low context-recall = retrieval missed the evidence;
high recall = retrieval found it but the answerer failed):

| cat | n | correct | wrong: **retrieval-miss** | wrong: answerer-miss | avg recall | judge |
|-----|---|---------|---------------------------|----------------------|------------|-------|
| 1 multi-hop   | 32 | 0 | **12** | 6 | 0.372 | 0.219 |
| 3 open-domain | 13 | 1 | **8**  | 1 | 0.261 | 0.192 |
| 2 temporal    | 37 | 13 | 3 | 10 | 0.663 | 0.500 |
| 4 single-hop  | 18 | 9 | 1 | 2 | 0.772 | 0.667 |

**Conclusion: cat1 and cat3 are RETRIEVAL-bound.** The dominant failure is the
evidence never reaching the context. The answerer is honest — it returns
`"unknown"` rather than hallucinating when context is insufficient (judge: "the
system answer does not provide any information about X"). So the lever is
**getting the evidence into context**, NOT the answerer.

(cat2 is the opposite — high-recall answerer misses = temporal reasoning. Out of
scope here; a separate answerer/temporal lever.)

## 2. Why single-shot retrieval misses

`runtime.search_ir(query, budget=k)` is **single-shot**: one query embedding/BM25
pass returns the top-k for ONE query. cat1 answers need evidence spread across
multiple turns/sessions that a single query vector doesn't surface together;
cat3 (open-domain) questions are broad/abstract and a single query misses.

## 3. Existing assets (build on, don't reinvent)

- **Query decomposition EXISTS but is dormant + benchmark-only.** `adapters/seam.py:_decompose`
  uses an LLM to split a question into 1-3 atomic sub-questions; `answer()` then
  retrieves each sub-query + the original and unions the results. It is gated on
  `--decomposer` (openai|claude) and was **OFF** in the 0.40 baseline. It lives in
  the LoCoMo adapter, NOT the core runtime.
- **Closure expansion is shallow.** `_collect_closure_ids` follows each candidate to
  its own `evidence`/`prov` ids (→ SPAN→RAW text). It does **NOT** traverse
  `ir_edges` (the relational graph). So related claims connected by
  `supported_by`/`derived_from`/`supersedes` are never pulled in.
- **The graph exists but is only SCORED, never TRAVERSED for retrieval.**
  `ir_edges` (storage.py) holds the relations; `retrieval.py:_graph_score` uses a
  record's neighbors to *rank*, but nothing expands retrieval *along* edges.
- **Core runtime has neither decomposition nor edge-traversal multi-hop.**

## 4. The levers

- **L1 — Query decomposition (multi-query).** LLM splits the question → retrieve each
  sub-query → union closures. Targets cat1 (multi-fact) + some cat3. Model-independent:
  default to the **local Ollama** decomposer (free, private, fits SEAM's local-first
  ethos; reuse the #313 Ollama infra), with a deterministic conjunction/entity split
  as the zero-dependency fallback and openai/claude as opt-in.
- **L2 — Graph-edge closure expansion (FREE, no LLM).** From the top retrieved
  candidates, traverse `ir_edges` (bounded depth, e.g. 1-2 hops) to pull in
  relationally-connected records, then merge into context. Targets cat1 where the
  answer's facts are edge-connected. Zero model cost; bound hop-depth + budget to
  avoid dilution at fixed top-k.
- **L3 — Query expansion / reformulation (cat3).** Broaden the single query
  (lexical synonyms = free; or HyDE-style LLM reformulation = opt-in) so open-domain
  questions surface more candidates.

## 5. Plan

**Phase 0 — validate cheaply, change nothing in core.** In the benchmark adapter:
(a) turn L1 on (local Ollama decomposer = free), (b) prototype L2 (edge traversal in
`_collect_closure_ids`, free), measure cat1/cat3 **free context-recall** vs the
0.372 / 0.261 baseline. Decide which lever(s) actually move the number BEFORE building.
Free recall is the cheap inner loop; confirm the winner once with the cheap paid judge
(~$0.05/100 cases) against the 0.40 baseline.

**Phase 1 — productize the winner into the CORE runtime.** Promote multi-hop from the
LoCoMo adapter into `seam_runtime/retrieval.py` + `runtime.search_ir` as a retrieval
**mode/flag** (model-independent decomposer; bounded edge-traversal closure), so every
surface (CLI / REST / MCP / agents) gets multi-hop — not just LoCoMo. Add it to the
`RetrievalFlags` lever set so the **self-improvement loop can tune it** (it currently
can't — the 11 existing levers are all single-shot-retrieval knobs and are tapped out
at 0.627).

**Phase 2 — cat3 query expansion (L3)** if Phase 0 shows decomposition alone doesn't
close open-domain.

## 6. Risks / guards

- Decomposition adds latency + (if remote-LLM) cost per query → opt-in / flagged;
  local Ollama keeps it free + private.
- Edge-closure can over-expand and dilute at fixed budget → bound hop-depth and
  candidate budget; the §24-style no-regression gate (free recall watchdog) protects
  against shipping a regression.
- Determinism: an LLM decomposer is best-effort deterministic only (temp 0); the
  deterministic split stays the floor, mirroring the #313 extractor design.

## 7. Non-goals

Not the answerer (it abstains honestly). Not cat2 (temporal reasoning = separate).
Not a full query-planning engine (see the separate SEAM Query Engine note) — though
that typed-plan could later be the declarative home for expressing these hops.
