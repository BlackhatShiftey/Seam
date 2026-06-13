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

## Next stages (not in this slice)

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
