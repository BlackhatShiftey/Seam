from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from seam_runtime.installer import current_platform_label, detect_layout, ensure_path_access, ensure_virtualenv, install_repo, run_doctor, write_shims


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install SEAM as a user-level command with persistent storage")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--skip-pip-upgrade", action="store_true")
    args = parser.parse_args(argv)

    layout = detect_layout(args.repo_root)
    ensure_virtualenv(layout)
    install_repo(layout, upgrade_pip=not args.skip_pip_upgrade)
    seam_shim, benchmark_shim, dashboard_shim = write_shims(layout)
    updated_profiles = ensure_path_access(layout)
    doctor = run_doctor(layout)

    print(f"SEAM installer: PASS ({current_platform_label()})")
    print(f"Install root: {layout.install_root}")
    print(f"Persistent DB: {layout.persistent_db_path}")
    print(f"Command shim: {seam_shim}")
    print(f"Benchmark shim: {benchmark_shim}")
    print(f"Dashboard shim: {dashboard_shim}")
    if updated_profiles:
        print("Updated shell profiles:")
        for profile in updated_profiles:
            print(f"- {profile}")
    print("")
    print(doctor.stdout.strip())
    print("")
    print("Next step:")
    print("- open a new terminal")
    print("- type: seam doctor")
    print("- type: seam --help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
