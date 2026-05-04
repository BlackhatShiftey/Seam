# Runtime Compression Ledger

Stable source files:

- `docs/MIRL_V1.md`
- `REPO_LEDGER.md`
- `seam_runtime/lossless.py`
- `seam_runtime/storage.py`
- `seam_runtime/runtime.py`

## Current Direction

SEAM compression means directly readable AI-native machine language. The
compressed artifact is the working document for AI question answering; SEAM must
not depend on restoring the original source before it can answer detail
questions.

## Implemented Runtime Slice

- `seam_runtime/lossless.py` defines `SEAM-RC/1` readable compression for text.
- `seam_runtime/holographic.py` defines `SEAM-HS/1` holographic surfaces for
  lossless PNG-backed machine-language payloads.
- `python seam.py readable-compress <file> --output <file.seamrc>` writes the
  directly readable compressed language.
- `python seam.py readable-query <file.seamrc> <query>` searches the compressed
  language directly and returns exact quoted/chunk hits.
- `python seam.py readable-rebuild <file.seamrc>` verifies the embedded hash and
  rebuilds exact text for audit, but rebuild is not required for direct query.
- `python seam.py benchmark run readable` runs the RC/1 1:1 direct-read gate.
- `python seam.py surface compile <file> --output <file.seam.png>` compiles
  source text into MIRL and writes that MIRL directly into an HS/1 PNG surface.
- `python seam.py surface query <file.seam.png> <query>` reads embedded MIRL or
  RC/1 directly from a PNG surface without OCR, NLP recompilation, or SQLite
  import.
- `python seam.py benchmark run surface` runs the HS/1 surface exactness gate.

## Benchmark Gate

The `readable` benchmark takes source text, writes `SEAM-RC/1`, reads the RC/1
records, and checks that the compressed language preserves the same information:

- exact full-text readback from `CHUNK` + `ORDER` records without byte-level
  decompression
- exact rebuild text and SHA-256 match
- source quote spans match RC/1 `QUOTE` records
- source terms are covered by RC/1 `INDEX` records
- direct compressed-language queries return exact quote hits or same-record term
  coverage for table/cell-style facts

RC/1 benchmark exactness is a hard 100% gate. The default suite includes a
recipe case requiring exact direct readback of the complete recipe plus direct
queries for title, ingredients, measurements, steps, and the quoted serving note.

The `surface` benchmark is the HS/1 hard gate:

- `surface_exact_rate == 1.0`
- `payload_hash_match_rate == 1.0`
- `direct_query_exactness_rate == 1.0`

Surfaces are queryable containers, not a replacement for SQLite canonical truth.
They are portable immutable snapshots that can feed search/context directly
before or without import.

## Required Contract

- The readable compressed language must preserve exact queryable details.
- Text and document compilers must preserve quote spans, headings, tables,
  entities, names, numbers, references, and source provenance.
- Image compilers must preserve OCR spans, regions, object labels, captions, and
  spatial relationships.
- Video and audio compilers must preserve transcript spans, time ranges, scenes,
  events, and tracked objects.
- SEAM-LX/1 or similar byte payloads may remain as exact reconstruction and hash
  verification backing layers, but they are not sufficient as the only
  compressed output.
- SEAM-HS/1 may carry MIRL, RC/1, LX/1, or raw bytes in lossless PNG pixels.
  MIRL and RC/1 payloads are directly queryable; LX/1 is verify/decode only
  until converted into a readable format.
- HS/1 modes are `bw1`, `rgb24`, and explicit `rgba32`. `rgb24` is the default;
  `rgba32` raises raw channel density from 3 to 4 bytes per pixel but has a
  higher operational mutation risk because image tooling may rewrite alpha.

## Next Safe Implementation Step

Broaden `SEAM-RC/1` from text into document/table/image/audio/video compilers,
then make stored `SEAM-HS/1` image surfaces a first-class runtime source.
Each compiler should emit directly readable records first, then use
reconstruction payloads only for audit or rebuild requests.

For the document/image-surface path, the safe sequence is:

1. Compile source documents into directly readable MIRL/RC records.
2. Pack those records into lossless `.seam.png` surfaces.
3. Store the surfaces as addressable artifacts with SQLite metadata and hashes.
4. Query/search/context by reading the embedded machine-language payload from
   the surface image itself, without restoring the original document and without
   requiring prior SQLite import.
