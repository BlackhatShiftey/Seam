# Symbol Nursery

SEAM symbols are machine-only allocations.

Humans do not author them directly. They are:

- proposed from MIRL usage patterns
- scored for ambiguity
- stored as `SYM` records
- used in `context` packs
- expanded during search and safety/audit export
- inherited through namespace trees

## Rules

- canonical meaning stays in MIRL
- shorthand lives in `SYM`
- low-ambiguity symbols are eligible for pack-time use
- exact packs never depend on shorthand
- safety export is generated from the symbol table, not handwritten

## Families

- `predicate`
- `entity`
- `generic`
- `status`
- `time`
- `boolean`

## Namespace inheritance

Symbols are resolved through namespace ancestry.

Example:

- `org`
- `org.app`
- `org.app.user`
- `org.app.user.thread`

A child namespace can use parent symbols unless it overrides them locally with a lower-ambiguity or more specific allocation.

## Current workflow

1. persist MIRL
2. run `promote-symbols`
3. use `context` packs with compaction
4. search queries expand scoped symbols before ranking
5. generate `export-symbols` output when humans need to audit the registry
