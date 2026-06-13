"""MIRL compilation fidelity harness.

Executable contract for what a *faithful* NL->MIRL compilation must satisfy,
plus golden cases. Backend-agnostic: the deterministic floor, the opt-in local
LLM extractor, and any future backend are all measured against the same checks
in ``contract.py``. ``golden.py`` carries the cases and records which properties
the *current* compiler already violates (the failing baseline).
"""
