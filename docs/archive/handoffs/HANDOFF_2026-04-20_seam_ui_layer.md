# SEAM dashboard UI layer — handoff for Claude Code

**Session date:** 2026-04-20
**Outgoing surface:** Cowork (desktop)
**Project root:** `C:\Users\iwana\OneDrive\Documents\Codex`
**Protocol:** `AGENTS.md` (canonical) · **Status:** `PROJECT_STATUS.md` · **History:** `HISTORY_INDEX.md` → surgical reads from `HISTORY.md`

---

## What was built this session

New subpackage `seam_runtime/ui/` — operator-surface primitives split out of `dashboard.py`. Four modules, all verified via standalone preview (`python -m seam_runtime.ui.<module>`) and wired into the live Textual app.

| File | Purpose |
| --- | --- |
| `seam_runtime/ui/__init__.py` | Lazy package init — submodules imported explicitly by callers so Rich/Textual aren't pulled at package load |
| `seam_runtime/ui/theme.py` | Single source of truth for every hex literal. Base tones + semantic aliases (`ACCENT`, `SIGNAL`, `FRAME`, `STATUS_OK/WARN/ERR`, `BAR_FILL_*`, `IR_TAG_COLORS`). Helpers: `fg(color, text)`, `fg_bg(fg, bg, text)`, `as_css_vars()` |
| `seam_runtime/ui/logo.py` | 8×8 `PIXEL_S_MARK` + 5×7 `WORDMARK_LETTERS` for S/E/A/M. Half-block renderer (`▀` U+2580) composes a 4-row header. `HeaderFields` dataclass + `header_markup(fields)` → `Static.update()` |
| `seam_runtime/ui/bars.py` | Typed bar family: `solid`, `segmented`, `indeterminate` (ping-pong scan-wave), `stalled`, `error`. `BarStyle` + `OK_STYLE`/`WARN_STYLE`/`ERR_STYLE`/`RUN_STYLE`. Unified `render(kind, **kwargs)` dispatch |
| `seam_runtime/ui/animations.py` | `MachineStream` (rolling MIRL record reveal with age-fade: newest full color, +1 `SIGNAL_DIM`, older `GRID_MID`). `CompressionPipeline` (3 stages: PARSE→MIRL→EMIT for compile / RAW→IR→PACK for compress, rates 0.22/0.16/0.20, `DWELL_AFTER_DONE = 1.5s`). `AnimationEngine(height)` — one callback driver: `trigger_compress(label, source_tokens, machine_tokens, kind)` + `tick_and_render(now=None)` |

## Wiring points in `seam_runtime/dashboard.py`

| Location (approx line) | Change |
| --- | --- |
| L50–52 | Added `from .ui import animations as _ui_animations / bars as _ui_bars / logo as _ui_logo` |
| `__init__` ~L321 | `self._anim_engine = _ui_animations.AnimationEngine(height=6)` |
| `_refresh_logo()` ~L711 | Builds `HeaderFields(version, tagline, launch_dir, shell_cwd, model, chat_status, mode, glow=True)`, pushes `header_markup(fields)` to `#logo-header` Static |
| `_trigger_mirl_animation()` ~L778 | Heuristic: `source_tokens = len(body) // 4`, `machine_tokens = source_tokens // 3`. Kind = `"compile"` or `"compress"` from label. Calls `self._anim_engine.trigger_compress(...)` |
| `_tick_mirl_animation()` ~L796 | Thin wrapper around `self._anim_engine.tick_and_render()`, pushes to panel |
| `_bar()` ~L851 | Shim: `return _ui_bars.solid(ratio, width=width)` |

Both AST walk and `py_compile` pass clean. Verification run (pipeline trigger → 23 ticks → idle) returned expected 6-row frame.

## Known issues / tuning knobs

1. **`MachineStream` cold-start underfill.** Panel is sparse until enough records have been emitted to fill `height=6`. By design, not a bug — flag for user if they ask "why is it empty at launch".
2. **`CompressionPipeline.DWELL_AFTER_DONE = 1.5s` is wall-clock.** At dashboard's 0.25s tick rate → ~6-tick hold after final stage. Tune in `animations.py:CompressionPipeline` if it reads too short/long once seen live. For unit tests, pass explicit `now=tick * 0.25` to `tick_and_render(now)` or the dwell never elapses.
3. **OneDrive NUL-byte gotcha on `.py` writes.** Files written from the Cowork sandbox to `C:\Users\iwana\OneDrive\Documents\Codex\...` can land with trailing `\x00` bytes → Python ≥3.10 `ValueError: source code string cannot contain null bytes`. Cannot `rm -rf __pycache__` on the mount (EPERM). Workaround for sandbox verification: `tr -d '\000' < src > /tmp/cleaned` then run from `/tmp/pkg_root/...` mirror. **Windows Python is not affected** — the user's `seam-dash` runs clean. If you're iterating from Claude Code on Windows, ignore this entirely.

## What the user needs to do next

Launch on Windows and visually confirm:
```
seam-dash
# or
python -m seam_runtime.dashboard
```
Things to look for:
- 4-row pixel-S + SEAM wordmark header renders without markup artifacts
- Right-side info strip (version, model, mode, cwd) aligns with header height
- Trigger MIRL compilation → compression pipeline bars advance through 3 stages, then dwell ~6 ticks, then yield to idle MachineStream
- `_bar` shim output in load panels matches the old look (`solid` with `show_pct=True` label)

## Open roadmap items (deferred, not asked-for this session)

- Modern/external cyan-slate brand track for repo/docs (vs. retired amber-phosphor)
- Revise stale docs: `branding/README.md`, `branding/retro-direction.md` still reference retired phosphor-green palette
- Add `indeterminate` and `stalled` bar usage somewhere in the live dashboard — currently only `solid` is wired via the shim
- Consider moving Textual `CSS` class attribute out of inline string and interpolating from `theme.as_css_vars()` — pivot layer is ready but not yet used

## User working preferences (abridged — full text in conversation profile)

- Deposition-style, direct, no fluff, no emotional framing
- Raw critique over validation; flag problems the moment you see them
- Show reasoning on architectural decisions
- Never trust training data for library APIs — search + read current official docs before writing code
- Read fully, not selectively. Verify against the version actually installed
- Pre-Coding Update Check is mandatory even for "straightforward" tasks
- If sources conflict: ground truth > user specs > upstream docs > training data; most recent authoritative wins; if unresolvable, stop and present the conflict
- Default loop: Concept QA → Blueprint QA → Implementation → Polish QA → Adversarial stress-test → Launch-readiness → Telemetry → Iterate (compress for trivial tasks, declare when compressing)

## Memory notes saved this session

Cowork's persistent memory now has:
- `onedrive_null_byte_gotcha.md` — the NUL-byte gotcha above
- `seam_dashboard_ui_layer.md` — the UI split + wiring map above

Claude Code does not share Cowork's memory store. Everything load-bearing is in this file or in the repo itself (`AGENTS.md`, `PROJECT_STATUS.md`, `HISTORY_INDEX.md`).

## Verification commands

```bash
# Standalone preview of each UI module (run from Codex root)
python -m seam_runtime.ui.theme
python -m seam_runtime.ui.logo
python -m seam_runtime.ui.bars
python -m seam_runtime.ui.animations

# Compile-check the wired dashboard
python -m py_compile seam_runtime/dashboard.py

# Launch the real thing
python -m seam_runtime.dashboard
```

---

**Bottom line for Claude Code picking this up:** build + wiring + verification are done. Do not re-derive the UI split. Read `AGENTS.md` and `PROJECT_STATUS.md` before touching anything else. If the user reports a visual issue after launching, start from the Wiring Points table above and trace from `dashboard.py` into the relevant `ui/` module.
