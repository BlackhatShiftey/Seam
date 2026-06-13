"""MIRL compilation fidelity: the contract run against the current compiler.

This is the failing baseline on record. Each (golden case x contract property)
is one parametrized check. A property listed in the case's ``baseline_failures``
is marked ``xfail(strict=True)`` - it documents a known violation of the current
``compile_nl`` stub AND ratchets: when the compiler rewrite makes that property
pass, the strict xfail becomes an XPASS (a hard failure), forcing the baseline
set to be updated. Properties NOT in ``baseline_failures`` must pass today and
are locked against regression.

The harness/checks are backend-agnostic (``benchmarks/fidelity/contract.py``):
the deterministic floor and the opt-in LLM extractor will be measured by the
exact same checks.
"""

from __future__ import annotations

import pytest

from benchmarks.fidelity import contract
from benchmarks.fidelity.golden import GOLDENS, PROPERTIES
from seam_runtime.nl import compile_nl


def _run_check(prop: str, golden, batch, batch_repeat) -> contract.CheckResult:
    if prop == "raw_verbatim":
        return contract.check_raw_verbatim(batch, golden.text)
    if prop == "determinism":
        return contract.check_determinism(batch, batch_repeat)
    if prop == "entity_extraction":
        return contract.check_entity_extraction(batch, golden.expected_entities)
    if prop == "subject_grounding":
        return contract.check_subject_grounding(batch, golden.text)
    if prop == "segmentation":
        return contract.check_segmentation(batch, golden.expected_fact_count)
    if prop == "separable_coverage":
        return contract.check_separable_coverage(batch, golden.facts)
    if prop == "fact_grounding":
        return contract.check_fact_grounding(batch, golden.text, golden.expected_fact_count)
    raise ValueError(f"unknown property {prop!r}")


def _params():
    params = []
    for golden in GOLDENS:
        for prop in PROPERTIES:
            marks = []
            if prop in golden.baseline_failures:
                marks = [pytest.mark.xfail(
                    strict=True,
                    reason=f"compile_nl stub violates '{prop}' on '{golden.name}' "
                           f"- target for the compiler rewrite (remove when fixed)",
                )]
            params.append(pytest.param(golden, prop, id=f"{golden.name}-{prop}", marks=marks))
    return params


@pytest.mark.parametrize("golden,prop", _params())
def test_compile_fidelity(golden, prop):
    batch = compile_nl(golden.text)
    batch_repeat = compile_nl(golden.text)
    result = _run_check(prop, golden, batch, batch_repeat)
    assert result.passed, f"[{golden.name}/{prop}] {result.detail}"


def test_baseline_failures_reference_real_properties():
    """Guard the baseline spec itself: every property named in any case's
    baseline_failures is a real contract property."""
    for golden in GOLDENS:
        unknown = golden.baseline_failures - set(PROPERTIES)
        assert not unknown, f"{golden.name} lists unknown properties: {unknown}"
