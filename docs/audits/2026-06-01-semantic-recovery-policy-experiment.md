# Semantic Recovery Policy Experiment (2026-06-01)

No-paid LoCoMo full-suite run (`n=1542`) using the SEAM adapter, SQLite vector
backend, local bge-small embeddings, deterministic workers (`--workers 1`),
`--answerer none`, and `--judge none`.

This verifies the default-off semantic recovery policy surface and records what
the pack-budget experiment means before any paid judged run.

## Policy surface

The LoCoMo SEAM adapter now exposes an explicit diagnostic policy label and
knobs:

- `--semantic-recovery-mode`: `baseline`, `pack-budget`, `deep-candidates`,
  `pack-budget-deep`
- `--context-budget`: evidence-context character budget
- `--search-top-k`: candidate count requested from `search_ir`
- `--rerank-top-k`: candidate count used when cross-encoder rerank is enabled

Defaults preserve the old behavior:

| field | default |
|---|---:|
| mode | `baseline` |
| context budget | 2000 |
| search top-k | 20 |
| rerank top-k | 20 |

## Diagnostics

Saved LoCoMo cases now include `answerer_diagnostics.retrieval_policy` and
`answerer_diagnostics.retrieval` even when `--answerer none` is used. Retrieval
event rows receive the same diagnostic payload in `extra.answerer_diagnostics`,
including empty-retrieval cases.

Sample from the experiment reports:

| config | sample policy | sample retrieval counts |
|---|---|---|
| baseline | `mode=baseline`, `context_char_budget=2000`, `search_top_k=20`, `rerank_top_k=20` | `candidate_count=20`, `closure_id_count=20`, `sub_question_count=0` |
| pack budget | `mode=pack-budget`, `context_char_budget=8000`, `search_top_k=20`, `rerank_top_k=20` | `candidate_count=20`, `closure_id_count=20`, `sub_question_count=0` |
| deep candidates | `mode=deep-candidates`, `context_char_budget=2000`, `search_top_k=100`, `rerank_top_k=20` | `candidate_count=100`, `closure_id_count=108`, `sub_question_count=0` |
| pack budget + deep | `mode=pack-budget-deep`, `context_char_budget=8000`, `search_top_k=100`, `rerank_top_k=20` | `candidate_count=100`, `closure_id_count=108`, `sub_question_count=0` |

## Results

| config | context budget | search top-k | context_recall_mean | delta vs baseline | elapsed |
|---|---:|---:|---:|---:|---:|
| baseline | 2000 | 20 | 0.623668 | +0.000000 | 723.4s |
| pack budget | 8000 | 20 | 0.682864 | +0.059195 | 527.6s |
| deep candidates | 2000 | 100 | 0.624195 | +0.000526 | 522.2s |
| pack budget + deep | 8000 | 100 | 0.758217 | +0.134549 | 528.9s |

Per-category context recall:

| cat | baseline | pack budget | deep candidates | pack budget + deep |
|---:|---:|---:|---:|---:|
| 1 | 0.423144 | 0.523893 | 0.411089 | 0.625226 |
| 2 | 0.631822 | 0.684733 | 0.644740 | 0.747620 |
| 3 | 0.268728 | 0.302085 | 0.249263 | 0.393952 |
| 4 | 0.729795 | 0.780545 | 0.732093 | 0.850240 |
| 5 | 0.000000 | 0.000000 | 0.000000 | 0.000000 |

## Interpretation

The pack budget is the dominant measured throttle for no-paid context recall.
Increasing search depth from 20 to 100 while keeping a 2000-character pack gives
almost no lift (`+0.000526`) and slightly hurts categories 1 and 3. Increasing
the pack from 2000 to 8000 characters at the same search depth gives a clear
global lift (`+0.059195`).

The strong result is the interaction: deep candidates plus an 8000-character
pack reaches `0.758217`, a `+0.134549` global context-recall delta over
baseline. That means deeper retrieval is not useless; it is mostly unusable
under the current 2000-character pack because the extra evidence cannot survive
packing.

This is not yet an answer-quality result. The run used `--answerer none` and
`--judge none`, so it measures whether gold-answer tokens appear in the packed
context, not whether a real model answers better. Larger packs can mechanically
increase context recall by putting more text in front of the scorer. The next
gated step is a paid judged comparison for baseline vs `pack-budget-deep` to
measure whether the larger evidence pack improves judged answer quality or
distracts the answerer.

## Artifacts

Raw reports and durable benchmark archives were kept outside git:

`../Seam-artifacts/20260601-semantic-recovery-policy/`

Report files:

- `reports/baseline_k20_b2000.json`
- `reports/pack_budget_k20_b8000.json`
- `reports/deep_candidates_k100_b2000.json`
- `reports/pack_budget_deep_k100_b8000.json`
