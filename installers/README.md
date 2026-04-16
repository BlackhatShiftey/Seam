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

## Linux

From the repo root:

```bash
sh ./installers/install_seam_linux.sh
```

## Shared behavior

Both platform installers call the same Python installer core in `install_seam.py`.

That installer:

- creates a dedicated SEAM runtime under the user home directory
- installs SEAM into that runtime
- creates `seam` and `seam-benchmark` command shims
- sets up a persistent default database for the installed runtime
- updates PATH or shell profile state as needed
- runs `seam doctor`

After install, open a new terminal and run:

```text
seam doctor
seam --help
```

Default persistent database paths:

- Windows: `%LOCALAPPDATA%\SEAM\state\seam.db`
- Linux: `~/.local/share/seam/state/seam.db`
