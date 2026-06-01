# Cat4 Single-Hop Recall — Miss Attribution Diagnostic (2026-05-31)

No-paid, SQLite vector backend, local bge-small embeddings, deterministic
(`--workers 1`). Resolves the open `HISTORY#274` question: is the cat4
single-hop recall gap **ranking-miss** or **packing-displacement** — and is the
operator's "conversational capture adapter" (abstract CLM/ENT records crowd RAW
out of retrieval) the right lever?

## Verified baseline (full 10-conv, n=1542)

`context_recall_mean = 0.6237` — matches the HISTORY#274 SQLite-isolated oracle
`0.623668`; harness sound. Per-category:

| cat | meaning | n | recall |
|---|---|---|---|
| 1 | multi-hop | 282 | 0.4231 |
| 2 | temporal | 321 | 0.6318 |
| 3 | open-domain | 96 | 0.2687 |
| **4** | **single-hop** | **841** | **0.7298** |
| 5 | adversarial | 2 | 0.0000 |

cat4 baseline 0.7298 confirms the remembered ~0.73; headroom is real.

## Method

Counterfactual probe (`cat4_counterfactual.py` in the local artifact bundle)
replays the REAL
`search_ir` + `_build_evidence_context_from_ids` packing path for each of the
841 single-hop cases under conditions, classifying each non-HIT by *what would
recover it*:

- `base`   : production — top_k=20 candidates, RAW-only pack, 2000-char budget
- `raw20`  : top_k=20 but candidates filtered to RAW before packing
- `k100`   : top_k=100 candidates
- `char8k` : pack char budget 2000 → 8000
- `raw100` : top_k=100 AND RAW-only (upper bound of retrieval recoverability)

## Result — buckets (841 cases)

| bucket | n | recoverable by | lever |
|---|---|---|---|
| HIT (base ≥ 1.0) | 444 | — | — |
| **crowding** (raw20 fixes) | **0** | RAW-only @ k=20 | **capture adapter** |
| ranking_depth | 24 | k=100 only | scoring/ranking |
| packing_trim | 31 | char 8k only | packing budget/order |
| matching_weak | 56 | RAW + deep-k together | matching |
| scorer_ceiling | 286 | nothing reaches 1.0 | token-metric ceiling |

## The capture-adapter hypothesis is empirically FALSE

The operator's hypothesis: each turn compiles to 1 RAW + many abstract records
(CLM/ENT/SPAN/PROV/SYM); those abstract records compete for the fixed top-20
slots and the 2000-char pack budget, displacing the RAW turn the scorer reads
(the HISTORY#240 mode). A capture adapter emitting cleaner RAW with fewer
abstract records would let RAW dominate.

The hypothesis has two distinct forms; both fail:

1. **Pack-crowding (abstract text in the packed context) — dead by
   construction.** `_build_evidence_context_from_ids` already filters the pack to
   `RecordKind.RAW` (adapters/seam.py:461-467), so the scorer never sees CLM/ENT
   text regardless. Confirmed: `raw20 == base` exactly for all 397 non-HIT cases
   (dropping abstract candidates before packing changes recall by 0.0000). This
   re-confirms the packer ignores abstract text; it does NOT by itself test the
   stronger slot-crowding claim below.

2. **Slot-crowding (abstract records occupy top-20 candidate slots, pushing the
   gold RAW turn past the rank cutoff) — measured false.** This is the real form
   of the hypothesis, tested on the 80 cases where the rank-20 cutoff actually
   matters (the `ranking_depth` + `matching_weak` buckets — gold turn at rank
   21–100). The top-20 candidate slots are **19.46/20 RAW** (mean 0.54 abstract;
   **0/80 cases abstract-majority**). The missed gold turn sits at candidate rank
   2–71 (median 27) **among other RAW turns** — it is edged out by competing RAW
   turns and candidate-pool-size effects, not by abstract records. (`packing_trim`
   is excluded from this check: char8k-at-k20 recovers it, so its gold turn is
   already inside the top-20 — slot-crowding cannot apply.)

Why the HISTORY#240 displacement intuition doesn't apply here: that regression
was an *ingest-format* change altering RAW text/embeddings; the abstract records
never reach the packed context under the current evidence-closure packer. There
is no RAW-vs-abstract competition to win back. **A capture adapter would not move
cat4 recall on this metric** — and rewriting ingest format is the repo's
highest-regression-risk change. Do not build it for this purpose.

## What the gap actually is

- **286/397 misses (72%) are scorer-ceiling** — no retrieval condition reaches
  recall 1.0 because the gold answer is a paraphrase/abstraction not verbatim in
  any turn ("me-time", "LGBTQ+", "researching adoption agencies"). This is a
  token-overlap metric artifact, NOT retrieval-fixable. It is also why a paid
  *judged* run scores higher than context_recall suggests.
- **111/397 (28%) are genuinely retrieval-recoverable** (raw100 → 1.0), max
  cat4 +0.0839 → global **+0.0457** if all fixed. Split:
  - matching_weak 56 → cat4 +0.0398 / global +0.0217 (biggest fixable slice)
  - packing_trim  31 → cat4 +0.0241 / global +0.0131
  - ranking_depth 24 → cat4 +0.0200 / global +0.0109

The realistic lever is **better query↔turn matching** (semantic/ranking), not a
capture adapter. The "+0.065 global headroom" remembered from #274 was optimistic
(assumed the full 0.27 gap retrievable); the measured retrieval-fixable ceiling
*at fixed pack budget* is **+0.046 global**.

## The actual lever is the pack CHAR BUDGET, not top_k (and it lifts the whole benchmark)

Config grid, global context_recall, all 1542 cases (`config_lever.json`
+ `config_lever_k20b8k.json` in the local artifact bundle):

| | budget=2000 | budget=8000 |
|---|---|---|
| **k=20**  | 0.6237 (prod) | 0.6829 (**+0.0592**) |
| **k=100** | 0.6242 (+0.0005) | 0.7582 (**+0.1345**) |

Per-category at the best cell (k=100/8000) vs prod: cat1 +0.202, cat2 +0.116,
cat3 +0.125, cat4 +0.120 — **every category up, none regress.** (At k=100/2000,
cat1/cat3 slightly regress −0.012/−0.019, so raising k *without* budget is
mildly harmful — the candidate pool is not the constraint.)

Findings:
- **Deeper candidate pool (top_k 20→100) alone ≈ 0** (+0.0005). The 20-candidate
  cutoff is not what's losing recall.
- **Pack budget (2000→8000 chars) alone = +0.0592 global**, every category.
- **Strong interaction:** k+budget together (+0.1345) ≫ the sum of the parts
  (+0.0597). Extra candidates only pay off once the pack is large enough to hold
  them; at budget=2000 they can't fit and are trimmed by `_trim_context`.

The packer is `_build_evidence_context_from_ids` → `_trim_context(text,
budget=2000)` (adapters/seam.py:542-545), a hard char truncation. The 2000-char
default is the single biggest throttle on this metric — far more than ranking.

**IMPORTANT caveat — context_recall rises with budget almost by construction.**
This metric is "fraction of gold-answer tokens present in the packed text," so
stuffing more text in front of the scorer mechanically raises it. The +0.13 is a
*retrieval-context-recall* lift at **4× the context tokens** (2000→8000 chars per
question), not a proven answer-accuracy gain. Whether a real (paid, judged)
answerer converts the larger haystack into more correct answers — or gets
distracted by it — is unmeasured and requires an operator-gated judged run. Do
not ship a budget bump as a "+0.13 LoCoMo win" without that confirmation; frame
it as "the pack budget is the dominant retrieval throttle, validate under judge."

## Artifacts

- Generated raw diagnostic artifacts are intentionally kept out of git. The
  local session copy was moved to
  `../Seam-artifacts/20260601-192239-cat4-diag_out/`.
- `baseline_full10.json` — verified baseline run
- `cat4_attribution.json` — per-case buckets (841 rows)
- `crowding_check.json` — strict top-20 composition analysis of the 80
  slot-crowding-relevant cases (ranking_depth + matching_weak)
- scripts: `cat4_counterfactual.py`, `crowding_check.py`
