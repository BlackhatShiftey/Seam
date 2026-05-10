"""Per-harness skill renderers.

Each module exposes a render(ir, profile, provenance) -> str function that
returns the rendered artifact body as a string. Callers (CLI in Phase 3) are
responsible for writing to disk.
"""
