# SEAM Prompt Codec Optimization Roadmap

**Status:** Planned roadmap track. Concept harvested from `bench/add-memory-benchmark-registry`.
**Track:** J — Prompt Codec Optimization.

## Purpose

SEAM's canonical storage is MIRL, JSON, and SQLite. Those formats are not always the most token-efficient transport for sending structured data into a model prompt. This track evaluates alternative *derived* prompt serialization codecs (TOON, compact JSON, SEAM-RC/1, SEAM-LX/1, markdown tables) and lets SEAM auto-select the cheapest reversible codec for each payload class under the active tokenizer.

Canonical record formats do not change. Audit, surface, and benchmark bundles keep byte-stable canonical JSON. Codec selection is restricted to derived prompt-bound payloads.

## Candidate codecs

- **Compact JSON** — baseline. Already supported. Lossless. Verbose under most tokenizers.
- **TOON** (Token-Oriented Object Notation) — column/array oriented. Often cheaper than JSON for repeated-shape arrays.
- **SEAM-RC/1** — Record-Compact. SEAM-specific record codec tuned for MIRL record arrays.
- **SEAM-LX/1** — Long-Context. SEAM-specific codec for retrieval result lists and context packs.
- **Markdown tables** — sometimes cheapest for small comparator scorecards.

## Initial payload targets

- PACK payloads
- retrieval result lists
- benchmark case matrices
- benchmark reports
- memory search index outputs
- citation / evidence tables
- tool-result arrays
- comparator scorecards

## Gates

- Codec roundtrip exactness is 100% when the payload requires lossless transport.
- Canonical JSON/MIRL hashes remain unchanged on disk.
- An alternate codec must beat compact JSON on measured token count under the active tokenizer before auto-selection promotes it.
- Signed, tamper-evident, or canonical benchmark bundles keep byte-stable canonical JSON unless a formally specified canonical TOON profile (or equivalent) is added, versioned, and tested.

## Proposed commands

```bash
seam codec benchmark payload.json
seam codec encode payload.json --format toon
seam codec encode payload.json --format auto
seam codec decode payload.toon --format toon
```

## Relationship to other tracks

- Track I (external memory benchmarks) Phase 6 adds a prompt-codec benchmark layer that compares codecs under the active tokenizer for the same payload class.
- Track K (trust/security) keeps canonical bundle hashing untouched; codec selection lives strictly on the derived-prompt side.

## Definition of done

Track J is complete when SEAM can encode any of the listed payload classes under any of the candidate codecs, measure tokens under the active tokenizer, auto-select the cheapest reversible codec, and round-trip the result with proof of exactness — all without altering canonical storage hashes.
