# SEAM Branding Concepts

These are first-pass SVG concepts for the `seam` CLI/tool identity.

Recommended direction:
- `seam-mark-retro.svg`
- Reason: it combines a memorable seam silhouette with a phosphor-terminal feel, which fits the CLI identity better than a generic modern tech mark.

Concepts:
- `seam-mark-retro.svg`
  - A retro terminal badge with a phosphor seam cut and memory-grid details.
  - Feels nostalgic, ownable, and more visually sticky for a CLI product.
- `seam-mark-join.svg`
  - Two interlocking halves meeting at a center seam.
  - Feels like stitching, composition, and system integration.
- `seam-mark-stack.svg`
  - A layered memory stack with a highlighted seam line.
  - Feels more infrastructural and storage-oriented.
- `seam-mark-terminal.svg`
  - A terminal-inspired prompt mark fused with a seam cut.
  - Best if the identity should feel strongly CLI-native.

Shared visual rules:
- simple geometry
- strong silhouette
- works in monochrome
- works at small terminal/icon sizes
- should feel good with glow, scanline, or hover-reactive effects in a GUI shell

Palette used in these drafts:
- deep ink: `#0f172a`
- steel: `#1e293b`
- seam cyan: `#22d3ee`
- seam gold: `#f59e0b`
- retro phosphor green: `#72f1b8`
- amber terminal glow: `#ffbf69`

Suggested next step:
1. Pick the strongest concept.
2. Refine line weight, corner radius, and color behavior.
3. Export a final app icon, terminal badge, and social/repo mark from the chosen direction.
4. Carry the same motion language into the GUI shell with subtle glow and scanline interaction.

Runnable previews:
- Browser preview:
  - `.\.venv\Scripts\python -m http.server 8000`
  - open `http://localhost:8000/branding/seam-retro-preview.html`
- Terminal preview:
  - `.\.venv\Scripts\python branding\seam_terminal_preview.py --snapshot`
  - `.\.venv\Scripts\python branding\seam_terminal_preview.py`

Current packaged assets:
- browser mock:
  - `branding/seam-retro-preview.html`
- terminal prototype:
  - `branding/seam_terminal_preview.py`
- current reference-backed header art:
  - `branding/assets/seam-dashboard-reference.png`
- latest screenshot:
  - `branding/screenshots/retro-preview-v7.png`
