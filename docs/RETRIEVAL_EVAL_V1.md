# Retrieval Evaluation v1

SEAM retrieval is evaluated against four tracks:

1. raw chunk retrieval baseline
2. MIRL claim/state/event retrieval baseline
3. hybrid retrieval baseline
4. pack usefulness under token budget

## Query Classes

- entity lookups
- fact lookups
- temporal lookups
- relation-heavy queries
- translator / workflow intent queries

## Success Conditions

- MIRL retrieval must beat raw-only on at least one fact and one relation-heavy query class
- hybrid retrieval must beat vector-only style scoring on at least one relation-heavy query class
- exact packs must remain reversible
- context packs must preserve traceability through `refs`
