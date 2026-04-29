# SEAM RAG Architecture

SEAM uses MIRL as the canonical memory graph and keeps vector stores as derived
indexes.

## Competitive Notes

LightRAG is strong at document ingestion, entity/relation extraction, graph plus
vector retrieval, WebUI graph exploration, reranking, and incremental updates.
SEAM now adopts the same practical retrieval shape while keeping its own
contract: canonical meaning lives in MIRL records stored in SQLite.

claude-mem is strong at agent integration: one-command install, automatic
capture, progressive disclosure, and Claude Code ecosystem fit. SEAM follows
that pattern with command-first install docs, compact `memory search`, full
`memory get`, and a lightweight `mcp serve` bridge that wrappers can sit on top
of without rewriting the Python runtime.

## Data Flow

1. `seam ingest <path> --persist` reads text and compiles MIRL records.
2. `document_status` records source ref, source hash, byte count, chunk count,
   extraction status, and index status.
3. `ir_records` stays canonical for claims, states, events, entities, and
   relations.
4. `ir_edges` stores derived graph edges from MIRL refs, relations, evidence,
   and provenance.
5. `vector_index` stores derived embeddings with source hashes for cache/stale
   detection.
6. Retrieval builds a compact PACK only after records are selected.

## Retrieval Modes

- `vector`: embedding-only semantic recall through the configured vector
  adapter.
- `graph`: MIRL edge expansion over entities, relations, evidence, and
  provenance.
- `hybrid`: structured SQL plus vector recall.
- `mix`: SQL, vector, and graph legs merged together. Use this for agent RAG
  unless a benchmark says another mode is better for the task.

Example:

```powershell
seam retrieve "persistent memory" --mode mix --budget 5 --trace
seam context "persistent memory" --retrieval-mode mix --view prompt
```

## Progressive Disclosure

Use compact search before fetching full detail:

```powershell
seam memory search "benchmark gate"
seam memory get clm:1,clm:2 --timeline
```

This keeps prompt cost low. Agents inspect IDs, summaries, refs, and scores
first, then fetch full MIRL only for selected records.

## Agent Bridge

`seam mcp serve` starts a JSON-lines stdio bridge with these tool names:

- `seam_memory_search`
- `seam_memory_get`
- `seam_ingest`

The bridge is intentionally thin. Node, Claude Code, Gemini CLI, OpenCode, or
other wrappers can spawn the Python command and speak JSON lines while SEAM
keeps the runtime, storage, and retrieval code in one place.

## Stale Index Detection

The SQLite vector index records a source hash for each vectorized record. When
`seam reindex` runs, the report includes `stale_before` entries for missing,
changed, or dimension-mismatched vectors before they are refreshed.

Example:

```powershell
seam reindex
```

PgVector follows the same derived-index rule. If the embedding model or vector
dimension changes, reindex vectors instead of treating the old vector table as
canonical memory.

## Boundaries

- SQLite remains canonical.
- Vector stores and graph edges are rebuildable.
- Reranking belongs behind the optional `rerank` extra.
- External agent ecosystem wrappers belong outside the core runtime unless they
  are small bridge shims.
- Benchmark claims still require verified bundles, diffs, and gates.
