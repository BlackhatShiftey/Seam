# Benchmark SOP

Use this SOP when you want to validate whether SEAM memory retrieval is actually getting better.

## What it measures

`python seam.py --db <file> stats` runs the versioned gold benchmark in `docs/retrieval_gold_fixtures.json`.

It compares:

- raw overlap baseline
- vector-only baseline
- MIRL structured retrieval
- hybrid retrieval
- pack quality under budget

The hardened fixture set now includes:

- fact retrieval
- workflow intent recovery
- relation-heavy graph queries
- temporal freshness and supersession
- contradiction handling
- scope isolation
- namespace and symbol inheritance

## Database setup

- SQLite truth store: the `--db` file you choose, such as `seam_validate.db`
- pgvector store: optional Postgres container on `localhost:54329`, database `seam`

If you want the validated live stack:

```powershell
docker start seam-pgvector
$env:SEAM_PGVECTOR_DSN="postgresql://postgres:postgres@localhost:54329/seam"
```

## Run the local baseline

This uses the deterministic hash model and no cloud credentials.

```powershell
python seam.py --db seam_validate.db validate-stack
python seam.py --db seam_validate.db stats
```

Use this when:

- you want reproducible local tests
- you are changing MIRL, retrieval, or pack logic
- you do not want cloud calls during development

## Run the live cloud benchmark

This uses your configured embedding provider.

```powershell
$env:OPENAI_API_KEY="your-key"
$env:SEAM_EMBEDDING_PROVIDER="openai-compatible"
$env:SEAM_EMBEDDING_MODEL="text-embedding-3-small"
$env:SEAM_PGVECTOR_DSN="postgresql://postgres:postgres@localhost:54329/seam"

python seam.py --db seam_validate.db validate-stack
python seam.py --db seam_validate.db stats
```

Use this when:

- you want teacher-quality embedding behavior
- you are comparing local models against a cloud baseline
- you want to validate the real vector database path

## How to read `stats`

Look at `summary.tracks` first:

- `raw` should be the weakest baseline
- `vector` shows pure embedding retrieval
- `mirl` shows structured retrieval without vector help
- `hybrid` shows the combined path you actually want to win

Then look at `summary.success_checks`:

- `mirl_beats_raw_on_fact_or_relation`
- `hybrid_matches_or_beats_vector_on_relation`
- `expected_over_rejected_on_temporal_scope_contradiction`
- `exact_packs_reversible`
- `context_packs_traceable`

Finally inspect per-fixture failures:

- `expected_ids` are the records that should come back
- `rejected_ids` are stale, contradicted, or wrong-scope records that should not outrank the expected answer
- `rejection_rate` tells you how much junk survived into the result set

## How to harden the benchmark

Add a fixture to `docs/retrieval_gold_fixtures.json` when you add a new memory behavior that SEAM should guarantee.

Good hardened cases include:

- stale vs current truth
- contradicted vs asserted truth
- project vs thread scope collisions
- parent-namespace symbol expansion
- provenance and evidence retention through packs

Each fixture should include:

- `query`
- `expected_ids`
- `rejected_ids` when there is a wrong answer worth penalizing
- `notes` explaining what failure mode the fixture is protecting

## Test workflow

When you change retrieval, MIRL fields, packs, or model adapters:

```powershell
python -m unittest -v
python seam.py --db seam_validate.db stats
```

If you changed cloud or pgvector wiring, also run:

```powershell
python seam.py --db seam_validate.db validate-stack
```
