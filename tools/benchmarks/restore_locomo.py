"""Restore and verify the LoCoMo dataset (locomo10.json) from defense-in-depth sources.

The LoCoMo benchmark dataset was once lost because it lived only on a near-full
root volume. This tool makes the dataset recoverable and integrity-checked from
multiple independent sources, in priority order:

    1. In-repo committed copy  (benchmarks/external/locomo/data/locomo10.json)
       -> also lives on GitHub via the private repo = offsite backup.
    2. T7 durable copy         (<repo>/.dataset_store/locomo/locomo10.json)
       -> separate physical disk from the OS root volume.
    3. Canonical upstream      (snap-research/locomo, network)

Every candidate is verified against the SHA256 pinned in the manifest before it
is accepted, so a truncated or drifted file is never silently used.

Usage:
    python -m tools.benchmarks.restore_locomo --verify          # check the canonical in-repo copy
    python -m tools.benchmarks.restore_locomo --to <path>       # restore a verified copy to <path>
    python -m tools.benchmarks.restore_locomo --ensure          # restore every standard location that is missing/bad
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "benchmarks" / "external" / "locomo" / "data"
MANIFEST_PATH = DATA_DIR / "locomo10.manifest.json"
IN_REPO_COPY = DATA_DIR / "locomo10.json"
T7_DURABLE_COPY = REPO_ROOT / ".dataset_store" / "locomo" / "locomo10.json"
# Working path the benchmark harness has historically read via --dataset-path / LOCOMO_PATH.
HOME_WORKING_COPY = Path.home() / "seam_benchmarks" / "track_m" / "locomo" / "locomo10.json"

# Standard locations kept in sync by --ensure (canonical in-repo copy first).
STANDARD_LOCATIONS = [IN_REPO_COPY, T7_DURABLE_COPY, HOME_WORKING_COPY]


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        sys.exit(f"ERROR: manifest missing: {MANIFEST_PATH}")
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify(path: Path, expected_sha: str) -> bool:
    return path.exists() and path.stat().st_size > 0 and _sha256(path) == expected_sha


def _copy_verified(src: Path, dest: Path, expected_sha: str) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    shutil.copyfile(src, tmp)
    if _sha256(tmp) != expected_sha:
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    return True


def _fetch_verified(url: str, dest: Path, expected_sha: str) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310 (pinned canonical https URL)
            tmp.write_bytes(resp.read())
    except Exception as exc:  # network is the last resort; report and move on
        print(f"  network fetch failed: {exc!r}", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        return False
    if _sha256(tmp) != expected_sha:
        print("  network copy failed SHA256 verification (upstream may have drifted)", file=sys.stderr)
        tmp.unlink(missing_ok=True)
        return False
    tmp.replace(dest)
    return True


def _first_good_source(expected_sha: str, exclude: Path | None = None) -> Path | None:
    """Return the first already-present, SHA-verified local source."""
    for cand in (IN_REPO_COPY, T7_DURABLE_COPY, HOME_WORKING_COPY):
        if exclude is not None and cand.resolve() == exclude.resolve():
            continue
        if _verify(cand, expected_sha):
            return cand
    return None


def restore_to(dest: Path, manifest: dict) -> bool:
    """Restore a SHA-verified dataset to ``dest`` from the best available source."""
    expected_sha = manifest["sha256"]
    if _verify(dest, expected_sha):
        print(f"OK  {dest} already present and verified")
        return True
    src = _first_good_source(expected_sha, exclude=dest)
    if src is not None:
        if _copy_verified(src, dest, expected_sha):
            print(f"OK  restored {dest}  <- {src}")
            return True
    print(f"..  no good local source for {dest}; trying canonical upstream", file=sys.stderr)
    if _fetch_verified(manifest["source_url"], dest, expected_sha):
        print(f"OK  restored {dest}  <- {manifest['source_url']}")
        return True
    print(f"FAIL  could not restore a verified {dest}", file=sys.stderr)
    return False


def main() -> int:
    p = argparse.ArgumentParser(description="Restore/verify the LoCoMo dataset")
    p.add_argument("--verify", action="store_true", help="Verify the in-repo canonical copy against the manifest")
    p.add_argument("--to", type=str, help="Restore a verified copy to this path")
    p.add_argument("--ensure", action="store_true", help="Restore every standard location that is missing or bad")
    args = p.parse_args()

    manifest = _load_manifest()
    expected_sha = manifest["sha256"]

    if args.verify or (not args.to and not args.ensure):
        ok = _verify(IN_REPO_COPY, expected_sha)
        actual = _sha256(IN_REPO_COPY) if IN_REPO_COPY.exists() else "(missing)"
        print(f"{'OK' if ok else 'FAIL'}  {IN_REPO_COPY}")
        print(f"      expected sha256: {expected_sha}")
        print(f"      actual   sha256: {actual}")
        if not (args.to or args.ensure):
            return 0 if ok else 1

    rc = 0
    if args.ensure:
        for loc in STANDARD_LOCATIONS:
            if not restore_to(loc, manifest):
                rc = 1
    if args.to:
        if not restore_to(Path(args.to).expanduser(), manifest):
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
