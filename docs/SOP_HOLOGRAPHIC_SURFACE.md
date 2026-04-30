# SOP: Holographic Surface Workflow

Use this SOP when creating, verifying, querying, or importing `SEAM-HS/1`
surfaces.

## Compile Source Text Straight To A Surface

```powershell
python seam.py surface compile input.txt --output input.seam.png --mode rgb24
python seam.py surface verify input.seam.png
```

This is the automatic flow: source text is compiled into MIRL, then MIRL is
encoded into a `SEAM-HS/1` PNG. It does not persist the records into SQLite
unless `--persist` is supplied.

## Create A Surface From RC/1

```powershell
python seam.py readable-compress input.txt --output input.seamrc
python seam.py surface encode input.seamrc --output input.seam.png --mode rgb24
python seam.py surface verify input.seam.png
```

Expected result: verification reports `PASS` and shows `payload_format:
SEAM-RC/1`.

## Query A Surface Directly

```powershell
python seam.py surface query input.seam.png "exact phrase or topic"
python seam.py surface search input.seam.png "stable compression"
python seam.py surface context input.seam.png --query "agent behavior" --budget 1200
```

These commands read embedded MIRL or `SEAM-RC/1` from PNG pixel data in memory.
They do not use OCR, natural-language recompilation, or SQLite import.

## Decode For Audit

```powershell
python seam.py surface decode input.seam.png --output restored.seamrc
python seam.py readable-rebuild restored.seamrc --output restored.txt
```

Use decode/rebuild for audit or export. Direct query does not require this step.

## Import When Needed

```powershell
python seam.py --db seam.db surface import input.seam.png
```

MIRL payloads are persisted as records. Non-MIRL payloads are stored as machine
artifact metadata so the original surface contract remains auditable.

## Rules

- Use PNG for v1 exact surfaces.
- Do not use JPEG or other lossy formats for exact SEAM memory.
- Prefer `rgb24` for default density and `bw1` for proof/debug fixtures.
- Use `rgba32` only when the extra channel density is worth the operational
  risk; it stores 4 bytes per pixel but alpha channels are often modified by
  image tooling.
- Treat the surface as a queryable snapshot, not as the replacement for SQLite
  canonical storage.
