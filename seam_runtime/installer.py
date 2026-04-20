from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


PATH_MARKER_BEGIN = "# >>> SEAM installer >>>"
PATH_MARKER_END = "# <<< SEAM installer <<<"


@dataclass(frozen=True)
class InstallLayout:
    repo_root: Path
    install_root: Path
    venv_dir: Path
    bin_dir: Path
    seam_entry: Path
    benchmark_entry: Path
    persistent_db_path: Path
    is_windows: bool


def detect_layout(repo_root: str | Path | None = None) -> InstallLayout:
    root = Path(repo_root or Path(__file__).resolve().parents[1]).resolve()
    is_windows = os.name == "nt"
    if is_windows:
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        install_root = local_app_data / "SEAM"
        venv_dir = install_root / "runtime"
        bin_dir = install_root / "bin"
        seam_entry = venv_dir / "Scripts" / "seam.exe"
        benchmark_entry = venv_dir / "Scripts" / "seam-benchmark.exe"
        persistent_db_path = install_root / "state" / "seam.db"
    else:
        install_root = Path.home() / ".local" / "share" / "seam"
        venv_dir = install_root / "runtime"
        bin_dir = Path.home() / ".local" / "bin"
        seam_entry = venv_dir / "bin" / "seam"
        benchmark_entry = venv_dir / "bin" / "seam-benchmark"
        persistent_db_path = install_root / "state" / "seam.db"
    return InstallLayout(
        repo_root=root,
        install_root=install_root,
        venv_dir=venv_dir,
        bin_dir=bin_dir,
        seam_entry=seam_entry,
        benchmark_entry=benchmark_entry,
        persistent_db_path=persistent_db_path,
        is_windows=is_windows,
    )


def ensure_virtualenv(layout: InstallLayout, python_executable: str | None = None) -> Path:
    if layout.seam_entry.exists() and layout.benchmark_entry.exists():
        return layout.venv_dir
    layout.install_root.mkdir(parents=True, exist_ok=True)
    layout.bin_dir.mkdir(parents=True, exist_ok=True)
    interpreter = python_executable or sys.executable
    subprocess.run([interpreter, "-m", "venv", str(layout.venv_dir)], check=True)
    return layout.venv_dir


def install_repo(layout: InstallLayout, upgrade_pip: bool = True) -> None:
    python_bin = layout.venv_dir / ("Scripts/python.exe" if layout.is_windows else "bin/python")
    requirements_path = layout.repo_root / "requirements.txt"
    if upgrade_pip:
        subprocess.run([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"], check=True)
    if requirements_path.exists():
        subprocess.run([str(python_bin), "-m", "pip", "install", "-r", str(requirements_path)], check=True)
        subprocess.run([str(python_bin), "-m", "pip", "install", "--no-deps", str(layout.repo_root)], check=True)
    else:
        subprocess.run([str(python_bin), "-m", "pip", "install", str(layout.repo_root)], check=True)
    ensure_persistence(layout)


def ensure_persistence(layout: InstallLayout) -> Path:
    layout.persistent_db_path.parent.mkdir(parents=True, exist_ok=True)
    return layout.persistent_db_path


def render_windows_cmd_shim(target_executable: Path, repo_root: Path, bootstrap_hint: str, persistent_db_path: Path) -> str:
    target_text = str(target_executable)
    db_text = str(persistent_db_path)
    repo_text = str(repo_root)
    return (
        "@echo off\n"
        f'set "SEAM_EXE={target_text}"\n'
        f'set "SEAM_DB_PATH={db_text}"\n'
        'if not exist "%SEAM_EXE%" (\n'
        f"  echo SEAM is not installed at {repo_text}\n"
        f'  echo Run: {bootstrap_hint}\n'
        "  exit /b 1\n"
        ")\n"
        '"%SEAM_EXE%" %*\n'
        "exit /b %ERRORLEVEL%\n"
    )


def render_posix_shim(target_executable: Path, repo_root: Path, bootstrap_hint: str, persistent_db_path: Path) -> str:
    target_text = target_executable.as_posix() if isinstance(target_executable, Path) else str(target_executable)
    db_text = persistent_db_path.as_posix() if isinstance(persistent_db_path, Path) else str(persistent_db_path)
    repo_text = repo_root.as_posix() if isinstance(repo_root, Path) else str(repo_root)
    return (
        "#!/usr/bin/env sh\n"
        f'SEAM_EXE="{target_text}"\n'
        f'export SEAM_DB_PATH="{db_text}"\n'
        'if [ ! -x "$SEAM_EXE" ]; then\n'
        f'  echo "SEAM is not installed at {repo_text}"\n'
        f'  echo "Run: {bootstrap_hint}"\n'
        "  exit 1\n"
        "fi\n"
        'exec "$SEAM_EXE" "$@"\n'
    )


def write_shims(layout: InstallLayout) -> tuple[Path, Path]:
    layout.bin_dir.mkdir(parents=True, exist_ok=True)
    ensure_persistence(layout)
    if layout.is_windows:
        bootstrap_hint = f'powershell -ExecutionPolicy Bypass -File "{layout.repo_root / "installers" / "install_seam_windows.ps1"}"'
        seam_shim = layout.bin_dir / "seam.cmd"
        benchmark_shim = layout.bin_dir / "seam-benchmark.cmd"
        seam_shim.write_text(
            render_windows_cmd_shim(layout.seam_entry, layout.repo_root, bootstrap_hint, layout.persistent_db_path),
            encoding="ascii",
        )
        benchmark_shim.write_text(
            render_windows_cmd_shim(layout.benchmark_entry, layout.repo_root, bootstrap_hint, layout.persistent_db_path),
            encoding="ascii",
        )
    else:
        bootstrap_hint = f'"{layout.repo_root / "installers" / "install_seam_linux.sh"}"'
        seam_shim = layout.bin_dir / "seam"
        benchmark_shim = layout.bin_dir / "seam-benchmark"
        seam_shim.write_text(
            render_posix_shim(layout.seam_entry, layout.repo_root, bootstrap_hint, layout.persistent_db_path),
            encoding="utf-8",
        )
        benchmark_shim.write_text(
            render_posix_shim(layout.benchmark_entry, layout.repo_root, bootstrap_hint, layout.persistent_db_path),
            encoding="utf-8",
        )
        seam_shim.chmod(0o755)
        benchmark_shim.chmod(0o755)
    return seam_shim, benchmark_shim


def ensure_path_access(layout: InstallLayout) -> list[Path]:
    if layout.is_windows:
        _ensure_windows_user_path(layout.bin_dir)
        return []
    return _ensure_posix_shell_profiles(layout.bin_dir)


def run_doctor(layout: InstallLayout) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["SEAM_DB_PATH"] = str(layout.persistent_db_path)
    return subprocess.run([str(layout.seam_entry), "doctor"], check=True, text=True, capture_output=True, env=env)


def path_in_environment(target: Path, path_value: str | None = None) -> bool:
    current = path_value if path_value is not None else os.environ.get("PATH", "")
    normalized_target = str(target.resolve())
    for raw_part in current.split(os.pathsep):
        part = raw_part.strip().strip('"')
        if not part:
            continue
        try:
            if str(Path(part).resolve()) == normalized_target:
                return True
        except OSError:
            if part == normalized_target:
                return True
    return False


def _ensure_windows_user_path(target: Path) -> None:
    user_path = os.environ.get("Path") or ""
    existing_user_path = os.environ.get("SEAM_INSTALLER_USER_PATH")
    if existing_user_path is None:
        existing_user_path = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "[Environment]::GetEnvironmentVariable('Path','User')",
            ],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip()
    parts = [part for part in existing_user_path.split(";") if part]
    target_text = str(target)
    if target_text not in parts:
        updated = ";".join(parts + [target_text]) if parts else target_text
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"[Environment]::SetEnvironmentVariable('Path', '{updated}', 'User')",
            ],
            check=True,
        )
    if not path_in_environment(target, user_path):
        os.environ["PATH"] = os.environ.get("PATH", "").rstrip(";") + (";" if os.environ.get("PATH") else "") + target_text


def _ensure_posix_shell_profiles(target: Path) -> list[Path]:
    updated: list[Path] = []
    if path_in_environment(target):
        return updated
    export_block = (
        f"{PATH_MARKER_BEGIN}\n"
        f'export PATH="{target}:$PATH"\n'
        f"{PATH_MARKER_END}\n"
    )
    profile_candidates = [
        Path.home() / ".profile",
        Path.home() / ".bashrc",
        Path.home() / ".zprofile",
    ]
    for candidate in profile_candidates:
        existing = candidate.read_text(encoding="utf-8") if candidate.exists() else ""
        if PATH_MARKER_BEGIN in existing:
            continue
        candidate.parent.mkdir(parents=True, exist_ok=True)
        content = existing
        if content and not content.endswith("\n"):
            content += "\n"
        candidate.write_text(content + export_block, encoding="utf-8")
        updated.append(candidate)
    os.environ["PATH"] = f"{target}{os.pathsep}{os.environ.get('PATH', '')}"
    return updated


def current_platform_label() -> str:
    if os.name == "nt":
        return "windows"
    return platform.system().lower()


def default_runtime_db_path() -> str:
    configured = os.environ.get("SEAM_DB_PATH")
    if configured:
        return configured
    return "seam.db"
