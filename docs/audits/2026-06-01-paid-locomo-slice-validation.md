# Paid LoCoMo Slice Validation (2026-06-01)

Paid OpenAI A/B validation for the semantic recovery pack-budget finding in
`docs/audits/2026-06-01-semantic-recovery-policy-experiment.md`.

This is **not** a full paid LoCoMo run. It is a 100-case representative slice
intended to check whether the no-paid context-recall improvement converts into
judged answer quality before spending on a full 1542-case judged run.

## Setup

- Dataset source: `benchmarks/external/locomo/data/locomo10.json`
- Generated slice artifact: `../Seam-artifacts/20260601-paid-locomo-slice/locomo_paid_slice_100.json`
- Cases: 100
- Conversations: all 10 conversations represented
- Category mix: cat1=24, cat2=24, cat3=24, cat4=26, cat5=2
- Answerer: OpenAI `gpt-4o-mini`
- Judge: OpenAI `gpt-4o-mini`
- Workers: 1
- Local vector path: SQLite; `SEAM_PGVECTOR_DSN` unset
- Context saved: yes
- Raw reports and durable archives: `../Seam-artifacts/20260601-paid-locomo-slice/`

Smoke check before the paid slice: 2 baseline cases completed with zero judge
errors, answerer model `gpt-4o-mini`, and judge model `gpt-4o-mini`.

## Compared Policies

| config | mode | context budget | search top-k | rerank top-k |
|---|---|---:|---:|---:|
| baseline | `baseline` | 2000 | 20 | 20 |
| candidate | `pack-budget-deep` | 8000 | 100 | 20 |

## Results

| metric | baseline | pack-budget-deep | delta |
|---|---:|---:|---:|
| context_recall_mean | 0.433482 | 0.604897 | +0.171415 |
| answer_em_mean | 0.180000 | 0.230000 | +0.050000 |
| answer_f1_mean | 0.349337 | 0.402854 | +0.053517 |
| judge_score_mean | 0.440000 | 0.570000 | +0.130000 |
| correct_count | 32 | 40 | +8 |
| partial_count | 24 | 34 | +10 |
| incorrect_count | 44 | 26 | -18 |
| judge_errors | 0 | 0 | 0 |

Elapsed time was 406.2s for baseline and 413.4s for `pack-budget-deep`.

Per-category:

| cat | n | baseline context | candidate context | baseline judge | candidate judge |
|---:|---:|---:|---:|---:|---:|
| 1 | 24 | 0.294912 | 0.570310 | 0.333333 | 0.520833 |
| 2 | 24 | 0.555060 | 0.685020 | 0.437500 | 0.541667 |
| 3 | 24 | 0.211562 | 0.390472 | 0.291667 | 0.416667 |
| 4 | 26 | 0.687363 | 0.807326 | 0.634615 | 0.750000 |
| 5 | 2 | 0.000000 | 0.000000 | 1.000000 | 1.000000 |

Verdict flips:

| flip | count |
|---|---:|
| partial -> correct | 4 |
| incorrect -> correct | 10 |
| incorrect -> partial | 10 |
| correct -> partial | 5 |
| partial -> incorrect | 1 |
| correct -> incorrect | 1 |

## Interpretation

The paid slice supports the no-paid pack-budget diagnosis. On this balanced
100-case slice, the larger pack plus deeper candidate pool improves judged
answer quality, not just token-overlap context recall:

- judge score mean improves by `+0.13`
- correct answers increase by 8
- incorrect answers decrease by 18
- all major categories improve on judged score
- judge/provider errors were zero

There are still regressions at the case level: 5 cases moved from correct to
partial, 1 from partial to incorrect, and 1 from correct to incorrect. That is
enough to treat the change as promising, not proven globally.

Next step: run the full 1542-case paid judged A/B only if the operator accepts
the 100-case slice as sufficient evidence to spend on the full validation. Use
the same two policies and the same model/provider path unless deliberately
testing model sensitivity.
