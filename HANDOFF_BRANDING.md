# SEAM Branding Handoff

## What Exists Now

- A portable browser-based dashboard preview:
  - `branding/seam-retro-preview.html`
- A runnable terminal dashboard preview:
  - `branding/seam_terminal_preview.py`
- A packaged SEAM reference image used by the browser mock:
  - `branding/assets/seam-dashboard-reference.png`
- The latest approved screenshot:
  - `branding/screenshots/retro-preview-v7.png`

## How To Run It

Browser preview:

```powershell
.\.venv\Scripts\python -m http.server 8000
```

Then open:

```text
http://localhost:8000/branding/seam-retro-preview.html
```

Terminal preview:

```powershell
.\.venv\Scripts\python branding\seam_terminal_preview.py --snapshot
.\.venv\Scripts\python branding\seam_terminal_preview.py
```

## What Was Added

- `rich` was added to `requirements.txt` so the terminal dashboard can run.
- The browser preview is now self-contained inside the repo and no longer depends on the original `My Drive` file path.
- The dashboard includes:
  - command line
  - runtime profile
  - model and reasoning mode
  - cloud/local execution mode
  - embedding backend
  - persistence footprint
  - vector sync health
  - recall quality
  - runtime log

## Important Notes

- The browser header currently uses a packaged crop/reference image for the SEAM logo area.
- That is good for matching the visual family right now, but it should be replaced with a repo-native recreation before this becomes production UI.
- The terminal preview is a real runnable prototype, but it still uses static demo data rather than live SEAM runtime values.

## Best Next Steps

1. Replace the packaged SEAM header image with a native logo recreation or dedicated asset exported specifically for the dashboard.
2. Decide whether the real product surface should be:
   - terminal-first with `rich`
   - a richer TUI with `textual`
   - or a browser shell that the CLI can launch
3. Wire the dashboard to actual SEAM runtime data instead of static placeholders.
4. Add explicit views or tabs for:
   - memory
   - retrieve
   - trace
   - agents
   - storage
5. Promote the terminal preview into a real command, for example:
   - `seam dashboard`
