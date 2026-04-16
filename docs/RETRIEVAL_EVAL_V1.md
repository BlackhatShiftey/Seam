# Retrieval Evaluation v1

SEAM retrieval is evaluated against versioned gold fixtures in `docs/retrieval_gold_fixtures.json`.

## Tracks

1. raw chunk retrieval baseline
2. vector-only retrieval baseline
3. MIRL structured retrieval baseline
4. hybrid retrieval baseline
5. pack usefulness under token budget

The `stats` command runs the suite with whichever embedding model is currently configured. If no embedding provider is configured, the suite uses the deterministic hash model.

## Query Classes

- fact lookups
- relation-heavy queries
- translator / workflow intent queries

The gold fixtures intentionally include machine-shaped query terms such as normalized predicates or symbols, because that is where SEAM should outperform plain raw chunk overlap.

## Success Conditions

- MIRL retrieval must beat raw-only on at least one fact or relation-heavy fixture
- hybrid retrieval must beat vector-only on at least one relation-heavy fixture
- exact packs must remain reversible
- context packs must preserve traceability through `refs`, `prov`, and `evidence`
