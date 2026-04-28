# MIRL v1 Freeze

MIRL is the canonical memory IR inside SEAM.

## Readable Lossless Compression Contract

SEAM compression is not complete when it only produces an opaque compressed
payload. The primary compressed artifact must be directly readable AI-native
machine language. A SEAM agent or query engine must be able to answer questions
from the compressed language itself without restoring the original document,
image, audio, or video.

The phrase "read just like the original" means exact details remain addressable
inside the compressed language:

- text spans, quote boundaries, headings, tables, names, numbers, and references
- image regions, OCR text, captions, object labels, and spatial relationships
- video scenes, frame or time ranges, transcript spans, audio events, and tracked objects
- provenance from each compressed record back to the source region, span, frame, or segment

SEAM-LX/1 and other byte-level codecs may exist as exact reconstruction and
integrity backing layers, but they are not the working document for AI question
answering. The working document is the readable MIRL or successor SEAM machine
language representation. If a compression path cannot be queried directly, it is
only archival compression, not finished SEAM compression.

## SEAM-RC/1 Readable Compression

`SEAM-RC/1` is the first runtime-readable lossless text compression format. It
stores exact source text as directly parseable machine-language records:

- `META` records store source identity, hash, media type, granularity, and the
  direct-read contract.
- `CHUNK` records store exact unique text chunks, chunk hashes, and terms.
- `ORDER` records store the source order and source offsets needed to rebuild
  the exact text.
- `QUOTE` records store exact quoted spans with source offsets.
- `INDEX` records store term-to-chunk postings for direct compressed-language
  queries.

Current CLI commands:

```powershell
python seam.py readable-compress input.txt --output input.seamrc
python seam.py readable-query input.seamrc '"exact quoted text"'
python seam.py readable-rebuild input.seamrc --output rebuilt.txt
python seam.py benchmark run readable
```

`readable-query` reads `SEAM-RC/1` directly. It does not rebuild the source
document before returning exact hits.

The `readable` benchmark performs the current RC/1 1:1 gate:

- read exact full text back from RC/1 `CHUNK` and `ORDER` records without using
  byte-level decompression
- rebuild the source from RC/1 records and compare text/hash exactly
- compare source quote spans against RC/1 `QUOTE` records
- compare source terms against RC/1 `INDEX` records
- run direct `readable-query` checks against the compressed language and require
  exact quoted hits or same-record term coverage for table/cell-style facts

RC/1 exactness cannot fall below 100%. A recipe document must be readable back
from the compressed language exactly, including title, yield, ingredients,
measurements, ordered steps, notes, punctuation, and quoted text.

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
