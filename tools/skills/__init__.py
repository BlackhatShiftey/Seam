"""Operator-side Skills Compiler tooling.

Modules under tools/skills/ are operator-side. They may use PyYAML and other
non-runtime dependencies because they are not packaged with seam-runtime.

- source_loader: YAML -> SkillIR
- profile_loader: YAML -> profile dict
- targets/: per-harness renderers (claude, cursor, ...)
- model_profiles/: per-harness YAML profiles
"""
