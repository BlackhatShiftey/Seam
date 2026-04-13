# Retrieval Evaluation v1

SEAM retrieval is evaluated against versioned gold fixtures in `docs/retrieval_gold_fixtures.json`.

## Tracks

1. raw chunk retrieval baseline
2. vector-only retrieval baseline
3. MIRL structured retrieval baseline
4. hybrid retrieval baseline
5. pack usefulness under token budget and traceability constraints

The `stats` command runs the suite with whichever embedding model is currently configured. If no embedding provider is configured, the suite uses the deterministic hash model.

## Query Classes

- fact lookups
- workflow intent lookups
- relation-heavy queries
- temporal freshness and supersession
- contradiction resolution
- scope isolation
- namespace and symbol inheritance

The gold fixtures intentionally include machine-shaped query terms such as normalized predicates or symbols, because that is where SEAM should outperform plain raw chunk overlap.

## Benchmark Workflow

1. keep the fixture corpus in `docs/retrieval_gold_fixtures.json`
2. run `python seam.py --db seam_validate.db stats`
3. compare raw, vector, MIRL, and hybrid tracks
4. inspect the per-fixture `expected_ids`, `rejected_ids`, and ranked outputs
5. only claim improvement when the benchmark improves without breaking exact/context pack guarantees

The hardened suite is designed to catch more than generic semantic similarity:

- temporal fixtures check that current truth outranks superseded truth
- contradiction fixtures check that asserted truth outranks contradicted truth
- scope fixtures check that thread-local truth stays ahead of project defaults
- namespace fixtures check that symbol expansion works across namespace inheritance
- pack metrics check that context compression still keeps provenance and evidence traceable

When reading `stats`, `rejection_rate` matters alongside recall. A retrieval track is not “good” if it finds the right record but also ranks stale or contradicted records too highly.

## Success Conditions

- MIRL retrieval must beat raw-only on at least one fact or relation-heavy fixture
- hybrid retrieval must match or beat vector-only on relation-heavy fixtures
- expected records must outrank rejected records on temporal, contradiction, and scope-sensitive fixtures
- exact packs must remain reversible
- context packs must preserve traceability through `refs`, `prov`, and `evidence`
