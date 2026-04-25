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

## Dashboard Chat Models With OpenRouter

The dashboard chat client uses one OpenAI-compatible endpoint at a time. For
OpenRouter, use one OpenRouter API key and switch models by changing the model
id. Do not write raw API keys into this repo or into docs.

### Windows Temporary PowerShell Session

Use this when you only want the current terminal session configured:

```powershell
$env:SEAM_CHAT_BASE_URL = "https://openrouter.ai/api/v1"
$env:SEAM_CHAT_API_KEY = $env:OPENROUTER_API_KEY
$env:SEAM_CHAT_MODEL = "qwen/qwen3-coder"
.\.venv\Scripts\python.exe seam.py dashboard
```

If you are using the installed command instead of the repo-local Python path:

```powershell
seam dashboard
```

### Windows Persistent User Defaults

Use this when you want new PowerShell sessions to pick up the same backend:

```powershell
[Environment]::SetEnvironmentVariable("SEAM_CHAT_BASE_URL", "https://openrouter.ai/api/v1", "User")
[Environment]::SetEnvironmentVariable("SEAM_CHAT_API_KEY", [Environment]::GetEnvironmentVariable("OPENROUTER_API_KEY", "User"), "User")
[Environment]::SetEnvironmentVariable("SEAM_CHAT_MODEL", "qwen/qwen3-coder", "User")
```

Open a new PowerShell window after setting user environment variables.

### Linux / WSL2 Temporary Bash Session

Use this when you only want the current shell session configured:

```bash
export SEAM_CHAT_BASE_URL="https://openrouter.ai/api/v1"
export SEAM_CHAT_API_KEY="$OPENROUTER_API_KEY"
export SEAM_CHAT_MODEL="qwen/qwen3-coder"
./.venv/bin/python seam.py dashboard
```

If you are using the installed command instead of the repo-local Python path:

```bash
seam dashboard
```

### Linux / WSL2 Persistent User Defaults

Append these lines to the shell profile you actually use, then open a new shell:

```bash
cat >> ~/.bashrc <<'EOF'
export SEAM_CHAT_BASE_URL="https://openrouter.ai/api/v1"
export SEAM_CHAT_API_KEY="$OPENROUTER_API_KEY"
export SEAM_CHAT_MODEL="qwen/qwen3-coder"
EOF
```

For `zsh`, use `~/.zshrc` instead of `~/.bashrc`.

### Switch Models Inside The Dashboard

```text
?models
?model qwen/qwen3-coder
?model deepseek/deepseek-v4-pro
?model xiaomi/mimo-v2.5-pro
?model x-ai/grok-4.20
?model x-ai/grok-code-fast-1
?model google/gemma-4-31b-it
?model google/gemma-4-31b-it:free
```

The default dashboard list also includes OpenAI fallbacks. To override the list
for one session, set `SEAM_CHAT_MODELS` to comma-separated model ids.

Windows PowerShell:

```powershell
$env:SEAM_CHAT_MODELS = "qwen/qwen3-coder,deepseek/deepseek-v4-pro,x-ai/grok-4.20,google/gemma-4-31b-it"
```

Linux / WSL2 bash:

```bash
export SEAM_CHAT_MODELS="qwen/qwen3-coder,deepseek/deepseek-v4-pro,x-ai/grok-4.20,google/gemma-4-31b-it"
```

## Known-Good First Run Output Fragments

Expect these fragments after a healthy setup:

- `SEAM doctor: PASS`
- `Compile smoke: PASS`
- `Required deps: OK`
- `Ran <N> tests` and `OK`
