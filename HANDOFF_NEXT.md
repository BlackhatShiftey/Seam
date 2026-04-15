# SEAM Handoff: Next Steps

## Highest-value next tasks

1. Move the retrieval package out of the old `experimental/hybrid_orchestrator` folder name.
   - The user-facing CLI terminology is now simplified, but the module path still carries the older stage name.
   - Rename it to something like:
     - `experimental/retrieval_orchestrator`
     - or `experimental/retrieval_pipeline`

2. Replace the basic in-memory SQL ranking with stronger structured retrieval.
   - Push more filtering and ranking into SQLite queries.
   - Add support for better fielded retrieval over:
     - `kind`
     - `scope`
     - `namespace`
     - `predicate`
     - `subject`
     - `object`

3. Decide whether the retrieval orchestrator should stay experimental or become part of `seam_runtime`.
   - If promoted:
     - expose it through the main runtime API
     - treat `index` and `context` as first-class SEAM features

4. Add richer context output for generation.
   - Right now `context` returns a pack.
   - Add options for:
     - plain text prompt context
     - citations/evidence view
     - record summaries vs exact record payloads

5. Improve documentation language.
   - Update remaining internal references that still say "hybrid".
   - Align docs around:
     - compile
     - export
     - search
     - retrieval
     - indexing
     - context

## Suggested immediate follow-up conversation

"Rename the experimental module path away from `hybrid_orchestrator`, keep compatibility imports, and update the docs/tests to match the new retrieval terminology everywhere."
