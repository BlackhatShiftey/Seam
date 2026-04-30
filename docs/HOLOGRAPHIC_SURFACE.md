# SEAM Holographic Surface

`SEAM-HS/1` is the first Holographic Surface format for SEAM. It stores
machine-language payload bytes inside lossless PNG pixel data so SEAM can read
and query a portable memory snapshot without OCR, natural-language recompilation,
or SQLite import.

## Theory Boundary

Holographic Surface does not create free compression. The useful compression
already happened when SEAM converted source material into MIRL, `SEAM-RC/1`, or
`SEAM-LX/1`. The surface is a dense visual container for that payload.

The information-theory boundary is:

- Shannon entropy still controls compressibility of the bytes.
- Kolmogorov complexity still bounds the shortest exact program or description.
- A raw image can have fixed container size, but filling empty pixels with real
  payload bytes increases actual information content.
- Lossy formats such as JPEG are not exact memory formats because they mutate
  pixel values.

The breakthrough is practical, not magical: SEAM can encode directly readable
machine language into a compact, immutable, visual artifact and query that
artifact directly.

## Runtime Contract

`SEAM-HS/1` surfaces contain:

- a `SEAM-HS/1` envelope
- payload format metadata: `MIRL`, `SEAM-RC/1`, `SEAM-LX/1`, or `bytes`
- payload byte length
- payload SHA-256
- payload bytes encoded into PNG pixels

Supported v1 modes:

- `bw1`: proof mode using black/white pixels as bits
- `rgb24`: density mode using RGB channel bytes directly
- `rgba32`: explicit high-density mode using RGBA channel bytes directly

Direct-read behavior:

- MIRL payloads can be parsed and searched directly from the surface.
- `SEAM-RC/1` payloads can be queried directly through the readable-compression
  query path.
- `SEAM-LX/1` payloads can be verified and decoded exactly, but they are not
  directly queryable until converted into MIRL or `SEAM-RC/1`.

SQLite remains the canonical long-term store. Holographic surfaces are portable,
immutable, directly readable snapshots and transport artifacts.

## Commands

```powershell
seam surface compile input.txt --output memory.seam.png --mode rgb24
seam surface encode input.seamrc --output memory.seam.png --mode rgb24
seam surface encode input.seamrc --output memory.seam.png --mode rgba32
seam surface decode memory.seam.png --output restored.seamrc
seam surface verify memory.seam.png
seam surface query memory.seam.png "behavior"
seam surface search memory.seam.png "stable compression"
seam surface context memory.seam.png --query "agent behavior" --budget 1200
seam surface import memory.seam.png --db seam.db
```

`surface query`, `surface search`, and `surface context` read the embedded
machine-language payload from the image in memory. They do not require database
import first.

`surface compile` is the automatic source-to-surface path: source text is
compiled into MIRL, then the MIRL bytes are encoded into `SEAM-HS/1`. `rgb24`
is the default because it survives ordinary PNG tooling more predictably.
`rgba32` stores 4 bytes per pixel instead of 3, increasing raw channel density
by about 33%, but it must stay explicit because alpha channels are more likely
to be rewritten or stripped by image editors and optimization tools.

## Benchmark Gate

The `surface` benchmark family requires:

- `surface_exact_rate == 1.0`
- `payload_hash_match_rate == 1.0`
- `direct_query_exactness_rate == 1.0`

Any pixel-packing, envelope, or query-dispatch change that drops exactness below
100% is release-blocking.
