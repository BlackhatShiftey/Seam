from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


DEFAULT_SURFACE_DIR = Path(".seam") / "surfaces"


@dataclass(frozen=True)
class SurfaceFileCopy:
    artifact_path: str
    surface_sha256: str
    copied: bool
    source_path: str

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_path": self.artifact_path,
            "surface_sha256": self.surface_sha256,
            "copied": self.copied,
            "source_path": self.source_path,
        }


class SurfaceFileAdapter:
    """File-backed adapter for redundant SEAM-HS/1 artifact copies."""

    def __init__(self, root: str | Path | None = None) -> None:
        configured = root or os.environ.get("SEAM_SURFACE_DIR") or DEFAULT_SURFACE_DIR
        self.root = Path(configured).expanduser()

    def store_copy(self, source_path: str | Path, surface_sha256: str | None = None) -> SurfaceFileCopy:
        source = Path(source_path).expanduser().resolve()
        if not source.exists():
            raise FileNotFoundError(source)
        actual_sha = _file_sha256(source)
        if surface_sha256 and actual_sha != surface_sha256:
            raise ValueError(f"Surface hash mismatch before copy: expected {surface_sha256}, got {actual_sha}")
        self.root.mkdir(parents=True, exist_ok=True)
        target = (self.root / f"{actual_sha}.seam.png").expanduser().resolve()
        copied = False
        if source != target:
            shutil.copy2(source, target)
            copied = True
        copied_sha = _file_sha256(target)
        if copied_sha != actual_sha:
            raise ValueError(f"Surface hash mismatch after copy: expected {actual_sha}, got {copied_sha}")
        return SurfaceFileCopy(
            artifact_path=str(target),
            surface_sha256=actual_sha,
            copied=copied,
            source_path=str(source),
        )


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
