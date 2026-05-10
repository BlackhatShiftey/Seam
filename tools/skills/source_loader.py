"""Load SkillIR instances from YAML source specs.

This loader uses PyYAML, which is not a seam-runtime dependency. It lives in
tools/skills/ so the runtime package stays YAML-free; YAML loading is a
build-time/operator-side concern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyYAML is required for tools.skills.source_loader. "
        "Install with: pip install pyyaml"
    ) from exc

from seam_runtime.skills import SkillIR, sha256_of_bytes


def load_source_bytes(path: Path | str) -> bytes:
    """Read a source spec file as raw bytes (for hashing)."""

    return Path(path).read_bytes()


def load_skill(path: Path | str) -> tuple[SkillIR, str, bytes]:
    """Load a SkillIR from a YAML source spec file.

    Returns:
        (skill_ir, source_spec_sha256, raw_bytes)

    The raw bytes are returned so callers can re-emit or re-hash without
    re-reading the file.
    """

    raw = load_source_bytes(path)
    data: Any = yaml.safe_load(raw)
    ir = SkillIR.from_dict(data)
    return ir, sha256_of_bytes(raw), raw
