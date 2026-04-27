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
- `python seam.py readable-compress <file> --output <file.seamrc>` writes the
  directly readable compressed language.
- `python seam.py readable-query <file.seamrc> <query>` searches the compressed
  language directly and returns exact quoted/chunk hits.
- `python seam.py readable-rebuild <file.seamrc>` verifies the embedded hash and
  rebuilds exact text for audit, but rebuild is not required for direct query.
- `python seam.py benchmark run readable` runs the RC/1 1:1 direct-read gate.

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

## Next Safe Implementation Step

Broaden `SEAM-RC/1` from text into document/table/image/audio/video compilers.
Each compiler should emit directly readable records first, then use
reconstruction payloads only for audit or rebuild requests.
