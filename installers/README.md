# SEAM Installers

This folder is the direct "download and run" install surface for SEAM.

The goal is:

1. clone or download the repo
2. run the installer for your platform
3. open a new terminal
4. type `seam`

## Windows

From the repo root:

```powershell
powershell -ExecutionPolicy Bypass -File .\installers\install_seam_windows.ps1
```

For repo-local dashboard runs on Windows, use the launcher under `scripts\windows`:

```powershell
.\scripts\windows\launch_dashboard.bat
```

## Linux (including WSL2)

### Prerequisites

Python's `venv` module is not bundled by default on Debian/Ubuntu. Install it first:

```sh
sudo apt-get install -y python3.12-venv
```

> If you are on a different Python version, replace `3.12` with your version (check with `python3 --version`).

### Run the installer

From the repo root:

```sh
sh ./installers/install_seam_linux.sh
```

The installer creates a self-contained SEAM runtime at `~/.local/share/seam/runtime` and adds `seam` to your PATH via your shell profile. **Do not use system `pip` or `pip3` — the installer manages its own venv.**

### Install optional extras

Base install now includes required runtime packages from `requirements.txt`, including `rich`, `chromadb`, and `tiktoken`.
Use extras only for optional backends:

```sh
# Textual dashboard and Textual dashboard tests
~/.local/share/seam/runtime/bin/pip install -e "/path/to/seam/repo[dash]"

# PgVector backend (requires a running Postgres with pgvector extension)
~/.local/share/seam/runtime/bin/pip install -e "/path/to/seam/repo[pgvector]"

# SBERT neural embeddings (downloads ~80MB model on first use)
~/.local/share/seam/runtime/bin/pip install -e "/path/to/seam/repo[sbert]"

# Both
~/.local/share/seam/runtime/bin/pip install -e "/path/to/seam/repo[all-extras]"
```

Replace `/path/to/seam/repo` with the actual repo path. On WSL2 with the repo on the Windows filesystem:

```sh
~/.local/share/seam/runtime/bin/pip install -e "/mnt/c/Users/<you>/OneDrive/Documents/Codex[all-extras]"
```

### Open a new terminal after install

The installer updates your shell profile but the change only takes effect in a new terminal session:

```sh
seam doctor
seam --help
```

## Shared behavior

Both platform installers call the same Python installer core in `install_seam.py`.

That installer:

- creates a dedicated SEAM runtime under the user home directory
- installs SEAM into that runtime with the `[dash]` extra (so the Textual dashboard works without extra setup)
- creates `seam`, `seam-benchmark`, and `seam-dash` command shims
- sets up a persistent default database for the installed runtime
- updates PATH or shell profile state as needed
- runs `seam doctor`

Default persistent database paths:

- Windows: `%LOCALAPPDATA%\SEAM\state\seam.db`
- Linux: `~/.local/share/seam/state/seam.db`

## Optional backends

| Extra | Package installed | When you need it |
|---|---|---|
| `dash` | `textual>=0.50` | Textual dashboard UI and Textual dashboard tests |
| `pgvector` | `psycopg[binary]>=3.0` | PgVector as the vector backend (set `SEAM_PGVECTOR_DSN`) |
| `sbert` | `sentence-transformers>=2.0` | Neural SBERT embeddings |
| `all-extras` | both | Full production setup |

To activate PgVector after installing the extra, set the DSN in your environment:

```sh
export SEAM_PGVECTOR_DSN="postgresql://user:password@localhost:5432/seam"
seam doctor  # should show: PgVector: reachable
```

### Setting up Postgres with pgvector (Docker)

A `docker-compose.yaml` is included at the repo root for local development. From the repo root:

```sh
docker compose up -d
```

This starts a Postgres 18 instance with the pgvector extension pre-installed, listening on port `5432`. The default credentials are:

| Setting | Default |
|---|---|
| Database | `seam` |
| User | `seam` |
| Password | `local-test-password` |
| Port | `5432` |

Set the DSN to match:

```sh
export SEAM_PGVECTOR_DSN="postgresql://seam:local-test-password@localhost:5432/seam"
```

To override any default, set the corresponding environment variable before running `docker compose up`:

```sh
POSTGRES_PASSWORD=mypassword SEAM_PGVECTOR_PORT=5433 docker compose up -d
```

To persist the DSN across terminal sessions, add the export to your shell profile (`.bashrc`, `.zshrc`, etc.):

```sh
echo 'export SEAM_PGVECTOR_DSN="postgresql://seam:local-test-password@localhost:5432/seam"' >> ~/.bashrc
source ~/.bashrc
```

Verify the full setup:

```sh
seam doctor  # PgVector: reachable
```

## Prove-It Flow After Install

Health check:

```text
seam doctor
```

Terminal dashboard (operator UI):

```text
seam dashboard
```

The dashboard is a live terminal UI connected to the SEAM runtime. It shows memory records, search logs, benchmark results, and lets you run compile, search, and context operations interactively. Requires `rich` (installed by default).

To take a one-shot snapshot without launching the interactive UI:

```text
seam dashboard --snapshot
```

Full benchmark glassbox run:

```text
seam benchmark run all --persist --output seam-benchmark-report.json
seam benchmark show latest
seam benchmark verify seam-benchmark-report.json
```

Exact machine-language demo:

```text
seam demo lossless /path/to/document.txt /path/to/document.seamlx --min-savings 0.75
seam demo lossless /path/to/document.seamlx /path/to/rebuilt.txt --rebuild
```

## Setup and Troubleshooting References

- `docs/setup.md`
- `docs/errors.md`
- `docs/howto/README.md`
