# SEAM Setup (Copy/Paste)

This guide is command-first and intended to be copy/pasted exactly.

## Windows (PowerShell)

```powershell
cd C:\Users\iwana\OneDrive\Documents\Codex
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e ".[dash]"
.\.venv\Scripts\python.exe -m pip show rich chromadb tiktoken textual
.\.venv\Scripts\python.exe -m unittest -v
.\.venv\Scripts\seam.exe doctor
```

## Linux / WSL2 (bash)

```bash
cd /path/to/Codex
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip install -e ".[dash]"
./.venv/bin/python -m pip show rich chromadb tiktoken textual
./.venv/bin/python -m unittest -v
./.venv/bin/seam doctor
```

## Install Missing Test Dependencies

Use this when tests skip due to optional modules not being installed.

### Windows

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dash]"
.\.venv\Scripts\python.exe -m unittest test_seam.SeamTests.test_textual_dashboard_mounts_core_panels test_seam.SeamTests.test_textual_dashboard_routes_retrieval_output test_seam.SeamTests.test_textual_dashboard_routes_compile_output test_seam.SeamTests.test_textual_dashboard_tab_switch_updates_side_panel_mode
```

### Linux / WSL2

```bash
./.venv/bin/python -m pip install -e ".[dash]"
./.venv/bin/python -m unittest test_seam.SeamTests.test_textual_dashboard_mounts_core_panels test_seam.SeamTests.test_textual_dashboard_routes_retrieval_output test_seam.SeamTests.test_textual_dashboard_routes_compile_output test_seam.SeamTests.test_textual_dashboard_tab_switch_updates_side_panel_mode
```

## Known-Good First Run Output Fragments

Expect these fragments after a healthy setup:

- `SEAM doctor: PASS`
- `Compile smoke: PASS`
- `Required deps: OK`
- `Ran <N> tests` and `OK`

