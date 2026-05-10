"""Load model profile YAML files into plain dicts.

Profiles are intentionally schemaless at this stage; each renderer reads only
the keys it cares about. A future Profile dataclass can replace this once the
contract is stable across at least three targets.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "PyYAML is required for tools.skills.profile_loader. "
        "Install with: pip install pyyaml"
    ) from exc

from seam_runtime.skills import sha256_of_bytes


def load_profile(path: Path | str) -> tuple[dict[str, Any], str, bytes]:
    """Load a model profile YAML file.

    Returns:
        (profile_dict, profile_sha256, raw_bytes)
    """

    raw = Path(path).read_bytes()
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"profile {path!s} must be a YAML mapping")
    return data, sha256_of_bytes(raw), raw
