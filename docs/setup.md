# SEAM Setup Commands

Copy and paste the section for your environment.

## One-Line Private Repo Install

Requires `gh auth login` first.

Windows PowerShell:

```powershell
gh repo clone BlackhatShiftey/Seam Seam; cd Seam; powershell -ExecutionPolicy Bypass -File .\installers\install_seam_windows.ps1
```

Linux / WSL2:

```bash
gh repo clone BlackhatShiftey/Seam Seam && cd Seam && sh ./installers/install_seam_linux.sh
```

Verify in a new terminal:

```text
seam doctor
seam --help
seam dashboard --snapshot --no-clear
```

## Repo-Local Development Install

Windows PowerShell:

```powershell
cd C:\Users\iwana\OneDrive\Documents\Codex
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e ".[dash]"
.\.venv\Scripts\python.exe -m pytest Test-Seam-All\test_seam.py tools\history\test_history_tools.py
.\.venv\Scripts\python.exe seam.py doctor
```

Linux / WSL2 bash:

```bash
cd /path/to/Seam
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m pip install -e ".[dash]"
./.venv/bin/python -m pytest Test-Seam-All/test_seam.py tools/history/test_history_tools.py
./.venv/bin/python seam.py doctor
```

If Debian/Ubuntu says `venv` is missing:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv
```

## First Memory Flow

```powershell
seam ingest README.md --persist
seam memory search "persistent memory"
seam retrieve "persistent memory" --mode mix --budget 5
seam context "persistent memory" --retrieval-mode mix --view prompt
```

## Optional Extras

```powershell
python -m pip install -e ".[server]"
python -m pip install -e ".[pgvector]"
python -m pip install -e ".[sbert]"
python -m pip install -e ".[agent]"
python -m pip install -e ".[rerank]"
python -m pip install -e ".[all-extras]"
```

## Dashboard Chat Models With OpenRouter

Do not write raw API keys into this repo.

Windows temporary session:

```powershell
$env:SEAM_CHAT_BASE_URL = "https://openrouter.ai/api/v1"
$env:SEAM_CHAT_API_KEY = $env:OPENROUTER_API_KEY
$env:SEAM_CHAT_MODEL = "qwen/qwen3-coder"
seam dashboard
```

Linux / WSL2 temporary session:

```bash
export SEAM_CHAT_BASE_URL="https://openrouter.ai/api/v1"
export SEAM_CHAT_API_KEY="$OPENROUTER_API_KEY"
export SEAM_CHAT_MODEL="qwen/qwen3-coder"
seam dashboard
```

Switch models inside the dashboard:

```text
?models
?model qwen/qwen3-coder
?model deepseek/deepseek-v4-pro
?model x-ai/grok-code-fast-1
?model google/gemma-4-31b-it
```

Refresh dashboard state without restarting:

```text
reload
/reload
refresh
```

## Expected Healthy Output

- `SEAM doctor: PASS`
- `Compile smoke: PASS`
- `Required deps: OK`
- `seam dashboard --snapshot --no-clear` renders the console frame
- `seam memory search ...` returns compact record IDs
