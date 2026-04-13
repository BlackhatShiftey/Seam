# Engineering Log

Use this as an append-only memory for solved problems, failed attempts, and operational lessons that future work should inherit instead of rediscovering.

## Entry Template

For each resolved problem, append:

- `date`
- `problem`
- `what_worked`
- `what_did_not_work`
- `artifacts`
- `follow_up_ideas`

Keep entries concrete. Prefer commands, files, env vars, failure signatures, and behavioral observations over vague summaries.

---

## 2026-04-13 - Live stack validation and real pgvector path

- `problem`
  SEAM needed to move from scaffolded vector wiring to a validated live stack with a real vector database and a real cloud embedding path.
- `what_worked`
  Running pgvector in Docker as `seam-pgvector` on `localhost:54329` with database `seam`.
  Using `SEAM_PGVECTOR_DSN=postgresql://postgres:postgres@localhost:54329/seam`.
  Using `SEAM_EMBEDDING_PROVIDER=openai-compatible` and `SEAM_EMBEDDING_MODEL=text-embedding-3-small`.
  `python seam.py --db seam_validate.db validate-stack` proved both the embedding smoke test and pgvector smoke test.
- `what_did_not_work`
  Running validation from a shell that did not actually inherit the user-set env vars made the runtime fall back to the hash model.
  The first cloud validation attempt hit `HTTP 429`, which was a provider-side quota/rate issue, not a SEAM wiring failure.
- `artifacts`
  `seam_runtime/validation.py`
  `docs/PGVECTOR_LOCAL.md`
  `docs/SOP_MODEL_INTEGRATION.md`
  `README.md`
- `follow_up_ideas`
  Add first-class local OSS embedding adapters under the same contract and compare them against the cloud baseline.
  Add a short command in docs for checking Docker container health and pgvector reachability.

## 2026-04-13 - Harden retrieval benchmark beyond easy semantic matches

- `problem`
  The original benchmark was too small and too forgiving. It could validate plumbing, but it could not defend claims about real memory behavior.
- `what_worked`
  Expanding the fixture corpus to cover temporal freshness, contradiction handling, scope isolation, and namespace inheritance.
  Tracking `expected_ids` and `rejected_ids` per fixture.
  Adding rejection-aware metrics and success checks, especially `expected_over_rejected_on_temporal_scope_contradiction`.
  Preserving `t0` and `t1` in DSL parsing so temporal cases are native MIRL, not test hacks.
- `what_did_not_work`
  The earlier relation check that required hybrid to strictly beat vector stopped being useful once stronger embeddings tied the result.
  A benchmark that only checks hit rate can still miss stale or contradicted records ranking too high.
- `artifacts`
  `seam_runtime/evals.py`
  `seam_runtime/dsl.py`
  `docs/retrieval_gold_fixtures.json`
  `docs/RETRIEVAL_EVAL_V1.md`
  `docs/BENCHMARK_SOP.md`
  `test_seam.py`
- `follow_up_ideas`
  Add provenance-heavy fixtures with longer trace chains.
  Add fixtures that separate cloud embeddings from future local OSS models more sharply.
  Consider a reranking layer once the harder corpus exposes a retrieval ceiling.

## 2026-04-13 - Make validator failure modes operationally useful

- `problem`
  `validate-stack` crashed on upstream cloud HTTP failures, which made operational triage noisier than it needed to be.
- `what_worked`
  Catching `urllib.error.HTTPError` and `urllib.error.URLError` in the embedding smoke test and returning structured `blocked` results instead of throwing.
  Keeping the pgvector check runnable even when the embedding provider is temporarily blocked.
- `what_did_not_work`
  Treating every cloud failure as a code bug.
  Relying on a traceback for normal provider-side conditions such as missing key, quota exhaustion, or network unreachability.
- `artifacts`
  `seam_runtime/validation.py`
  `test_seam.py`
- `follow_up_ideas`
  Add finer-grained messaging for authentication vs billing/quota vs endpoint mismatch.
  Consider a CLI hint field suggesting the next operator action for common blocked states.

## 2026-04-13 - Fix SQLite ResourceWarning noise for real

- `problem`
  Tests passed but emitted `ResourceWarning: unclosed database` during symbol search flows, which meant connection lifecycle was sloppy even though behavior looked correct.
- `what_worked`
  Using `contextlib.closing(self._connect())` around SQLite connections in both `SQLiteStore` and `SQLiteVectorIndex`, then nesting `with connection:` inside for transaction semantics.
  Verifying the fix with `python -Werror::ResourceWarning -m unittest test_seam.SeamTests.test_symbol_export_and_query_expansion`.
- `what_did_not_work`
  Assuming `with connection:` closes a `sqlite3.Connection`. It handles commit/rollback, not deterministic close.
  Ignoring the warning because the main test suite was still green.
- `artifacts`
  `seam_runtime/storage.py`
  `seam_runtime/vector.py`
- `follow_up_ideas`
  Apply the same explicit-close discipline to any future SQLite-backed helper or cache layers.
  Add a targeted regression test if another SQLite-heavy feature starts warning under strict mode.
