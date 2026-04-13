# MIRL v1 Freeze

MIRL is the canonical memory IR inside SEAM.

## Record Kinds

- `RAW`
- `SPAN`
- `ENT`
- `CLM`
- `EVT`
- `REL`
- `STA`
- `SYM`
- `PACK`
- `FLOW`
- `PROV`
- `META`

## Shared Non-RAW Fields

- `id`
- `kind`
- `ns`
- `scope`
- `ver`
- `created_at`
- `updated_at`
- `conf`
- `status`
- `t0`
- `t1`
- `prov`
- `evidence`
- `ext`
- `attrs`

The hardened retrieval benchmark now explicitly tests the behavior of `t0`, `t1`, `scope`, `status`, `prov`, and `evidence`, because those are the fields that distinguish real memory from loose text similarity.

## Status Enum

- `asserted`
- `observed`
- `inferred`
- `hypothetical`
- `contradicted`
- `superseded`
- `deprecated`
- `deleted_soft`

## Canonical MIRL Text Form

One line per record:

```txt
KIND|record_id|<canonical_json_payload_without_id_and_kind>
```

## PACK Contract

### Exact

- reversible to the exact MIRL subset named in `refs`
- payload contains full MIRL JSON records
- verifier checks JSON-equivalent reconstruction

### Context

- optimized for token budget
- preserves `refs`, provenance fallback, and evidence fallback
- not durable truth

### Narrative

- natural-language summary
- explicitly lossy
- never treated as durable truth

The benchmark treats exact/context pack behavior as a contract:

- exact packs must remain reversible
- context packs must keep `refs`, `prov`, and `evidence` traceable
