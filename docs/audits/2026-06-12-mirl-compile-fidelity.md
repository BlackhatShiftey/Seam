# MIRL Compilation Fidelity — Contract + Failing Baseline

Date: 2026-06-12
Status: active (Stage 1 of the compiler rewrite — the contract + failing baseline)
Harness: `benchmarks/fidelity/` (contract + goldens), `tests/fidelity/test_compile_fidelity.py`

## Why this exists

`seam_runtime/nl.py:compile_nl` — the generic "remember arbitrary text" compiler
behind `seam remember`, the shell, the dashboard remember box, the MCP `ingest`
tool, and the REST `/ingest` endpoint — is not a compiler. It is a template
overfit to SEAM's own self-description: it pattern-matches "want to / goal is to
/ called X", and when those do not fire (i.e. for any real memory) it slugifies
the **entire input** and asserts it as `project:SEAM`'s `goal`, attributed to a
hardcoded `user:local_user` + `project:SEAM`. Every ingest produces the same
skeleton regardless of content.

Consequence: the structured layer (ENT/CLM/STA) carries no faithful information
for real input, and — at a fixed retrieval `search_top_k` — these boilerplate
records **displace the verbatim RAW record** that token-overlap retrieval
actually reads. So the stub is not merely cosmetic; it degrades retrieval and
poisons the self-improvement loop's "tune on the user's own corpus" mode (the
own-corpus probes become cloze-over-slug).

This document is **Stage 1**: pin down what a faithful compilation *is*, as an
executable contract, and lock the current stub's violations as a failing
baseline that the rewrite must turn green. No compiler behavior is changed here.

## The contract (seven properties)

Backend-agnostic — the deterministic floor, the opt-in local-LLM extractor, and
any future backend are all measured by the same checks in
`benchmarks/fidelity/contract.py`.

| Property | A faithful compilation must… |
|---|---|
| `raw_verbatim` | preserve the input exactly in one RAW record |
| `determinism` | produce byte-identical records for the same input (free backend) |
| `entity_extraction` | surface the salient entities as ENT records |
| `subject_grounding` | never make a claim *about* an entity absent from the input (the core faithfulness property the stub breaks with `project:SEAM`) |
| `segmentation` | yield ≥ N claims for N distinct facts, not one mashed slug |
| `separable_coverage` | carry every fact in some claim, with no single claim mashing two facts |
| `fact_grounding` | in a multi-fact input, never let a claim's evidence span cover the whole document |

These are deterministic **structural proxies** for semantic properties, chosen so
a faithful compiler can satisfy them and the stub provably cannot. They are not a
semantic oracle; limitations are documented at each check (e.g. token grounding,
not meaning). Where a future backend legitimately normalizes a surface form, the
relevant check gets a documented allowlist.

## The failing baseline (current `compile_nl`)

Generated from the checks; one row per golden case, `FAIL` = contract violation.

```
case                                raw   det   ent   subj  seg   cov   grnd
single_fact_ownership               PASS  PASS  FAIL  FAIL  PASS  PASS  PASS
two_independent_facts               PASS  PASS  FAIL  FAIL  FAIL  FAIL  FAIL
personal_event_with_place_and_date  PASS  PASS  FAIL  FAIL  PASS  PASS  PASS
schedule_change                     PASS  PASS  FAIL  FAIL  PASS  PASS  PASS
self_description_overfit            PASS  PASS  PASS  PASS  PASS  PASS  PASS
```

Reading it:

- **Every realistic memory (rows 1–4) fails `entity_extraction` and
  `subject_grounding`** — the stub extracts no real entities and asserts every
  fact about a fabricated `project:SEAM`.
- **Multi-fact input (row 2) additionally fails `segmentation`,
  `separable_coverage`, and `fact_grounding`** — two facts collapse into one
  slug claim whose span covers the whole document.
- **The self-description input the stub was written for (row 5) passes the whole
  contract.** This is deliberate: it proves the harness is fair and the contract
  is satisfiable, not rigged so the stub always loses. The stub is correct on
  exactly the one document it was overfit to.

`raw_verbatim` and `determinism` pass everywhere — the verbatim text is safe and
compilation is deterministic. The rewrite must preserve both.

## How the baseline is enforced (the ratchet)

`tests/fidelity/test_compile_fidelity.py` runs every (case × property) pair.
Each property a case currently violates is listed in the case's
`baseline_failures` and marked `xfail(strict=True)`. Two consequences:

1. The failing baseline is **on record and green in CI** (xfailed, not failed;
   the strict-no-skip conftest exempts `wasxfail`).
2. It is a **ratchet**: when the compiler rewrite makes a violated property pass,
   the strict xfail becomes an XPASS → a hard failure → forcing that property to
   be removed from `baseline_failures`. Properties cannot silently flip; each fix
   is a deliberate baseline edit.

The 25-pass / 11-xfail result is the Stage-1 checkpoint.

## Reconciled to the spec metrics (§22 / §24)

The seven Stage-1 properties were ad-hoc. Per the governing-contract rule
(AGENTS.md Session Start item 6; HISTORY#304) the compiler is measured by the
spec's **own** metrics, `SEAM_SPEC_V0.1.md` §22, implemented in
`benchmarks/fidelity/spec_metrics.py`:

| Metric | Spec definition | Implemented as |
|---|---|---|
| `cr` compression ratio | `original_tokens / packed_tokens` | source NL tokens / context-PACK tokens (NL→PACK, the north-star density; note `score_pack`'s existing `compression_ratio` is the narrower IR→PACK) |
| `rr` reconstruction rate | `recovered_fields / required_fields` | expected entities + facts + temporal present in the IR |
| `sr` semantic retention | `semantic_match(original_ir, reconstructed_ir)` | structured (subject, relation, object) triple match per golden — catches fabrication a word-overlap score misses |
| `pr` provenance retention | `provenance_links_recovered / expected` | fraction of claims with a complete claim→SPAN→RAW chain |
| `tr` temporal retention | `temporal_facts_recovered / expected` | golden temporal tokens present in a claim / a `t0`/`t1` field |
| `qr` retrieval quality | `retrieval_success_at_k` | **deferred** — needs the ingest+retrieval harness (next slice); `None` here |

The Stage-1 checks become **diagnostic components** of these metrics, not a
parallel contract: `raw_verbatim` is the lossless backing for `rr`;
`entity_extraction`/`segmentation`/`separable_coverage` feed `rr`;
`subject_grounding` feeds `sr`; `fact_grounding` feeds `pr`; `determinism` is a
translator guarantee (§29.1), not a §22 score.

**§24 promotion gate** (`passes_promotion`): a candidate compiler may be promoted
only if `sr≥0.98`, `pr==1.00`, `tr≥0.99`, `qr` no worse than baseline, and `cr`
strictly better than baseline. An unmeasured metric blocks promotion. This is the
spec's rule — "denser only when it proves it can still recover what matters."

**`compile_nl` spec-metric baseline** (generated from the metrics):

```
case                                   cr     rr     sr     pr     tr   qr
single_fact_ownership               0.018  0.333  0.333  1.000  1.000 None
two_independent_facts               0.040  0.500  0.333  1.000  1.000 None
personal_event_with_place_and_date  0.024  0.500  0.333  1.000  1.000 None
schedule_change                     0.031  0.750  0.333  1.000  1.000 None
self_description_overfit            0.031  1.000  1.000  1.000  1.000 None
```

Reading it:

- **`sr` is the clean discriminator** — `0.333` on every real memory (the stub
  fabricates the subject `project:SEAM` and predicate `goal`; only the slug's
  *object* tokens match, 1 of 3 components) versus `1.000` on the overfit
  self-description. This is the Stage-1 finding restated in the spec's own terms.
- **`cr` exposes token inflation the Stage-1 harness missed** — `0.018`–`0.040`
  means the packed IR is 25–55× the source. (A single short sentence cannot reach
  `cr > 1` losslessly; `cr`'s value is comparative — does the rewrite raise it —
  and at corpus scale. It is the spec's north-star axis, "intelligence per
  token", and the stub is deeply negative on it.)
- **`pr` and `tr` are `1.000` and do NOT expose the stub.** It *does* bind every
  claim to a span→RAW chain (`pr`), and its one slug accidentally contains the
  temporal tokens (`tr`). Honest: the stub's sin is faithfulness/density (`sr`,
  `rr`, `cr`), not provenance or temporal token-presence.

The §24 gate **rejects** the stub on every case (`sr < 0.98`, and `qr` pending).
A latent Stage-1 bug was fixed here so the contract is satisfiable by a correct
compiler: coverage/`rr` now read the *resolved subject-entity label*
(`contract.claim_content_tokens`), so a faithful `(ent:priya, owns,
billing_service)` claim is recognized as carrying the fact "Priya owns…" — a
hand-built faithful batch scores `sr = rr = pr = 1.0` and passes every check
(`tests/fidelity/test_spec_metrics.py`). The stub baseline is unchanged by the
fix (its slug already contained every token).

## Next stages (not in this slice)

- **Slice 2 — `qr` (retrieval quality).** Add the ingest + `search_ir` harness so
  `retrieval_success@k` is measured and the §24 gate is complete (`qr` is the
  "directly queryable" axis the spec and operator both require).

- **Stage 2 — deterministic floor rewrite.** Segment into propositions, verbatim
  RAW/SPAN per proposition, entities from high-confidence rules, and **never
  fabricate** a claim. Turn the `entity_extraction` / `subject_grounding` /
  `segmentation` / `separable_coverage` / `fact_grounding` xfails green.
- **Stage 3 — unify** `compile_nl` and `compile_conversation_turn` behind one
  pipeline; delete the SEAM-specific stub.
- **Stage 4 — opt-in LLM extractor** (local Ollama default, cloud optional)
  behind the same contract, for rich S-P-O triples.
- **Stage 5 — migration**: recompile existing degenerate records (keep RAW,
  replace derived ENT/CLM/STA) and re-validate the self-probe loop on a real
  corpus.

The backend decision for the free floor (honest-minimal vs. spaCy NER vs. local
LLM tiering) is recorded separately; the contract here is invariant across it.
