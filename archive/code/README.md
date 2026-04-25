# Inactive Code Archive

This folder is for code that is intentionally not part of the active runtime,
tests, package, or operator tooling.

Rules:

- Do not import code from this folder.
- Do not package code from this folder.
- Do not treat code here as current behavior.
- If archived code becomes useful again, port the needed behavior into an active
  source area and add tests there.
- Keep generated build copies ignored. They are useful only as temporary local
  inspection artifacts and should not be committed as historical source.

Active code lives in:

- `../../seam_runtime/` - runtime package
- `../../seam.py` - CLI entrypoint module
- `../../experimental/` - live prototypes that may still be tested or promoted
- `../../tools/` - active development/history tools
- `../../scripts/` - active operator scripts
- `../../installers/` - active install entrypoints
