"""SEAM operator-surface UI primitives.

Pixel-art logo, typed bar library, and compression/stream animations
for the Textual dashboard. Every submodule ships a standalone preview
runnable via ``python -m seam_runtime.ui.<module>`` so the renderers
can be iterated independently of ``seam_runtime.dashboard``.
"""

# Intentionally empty — submodules are imported explicitly by callers
# (``from seam_runtime.ui import logo``) to avoid pulling Rich/Textual
# until a concrete renderer is requested.
__all__: list[str] = []
