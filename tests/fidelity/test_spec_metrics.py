"""SEAM-spec §22 metrics: mechanism, the compile_nl baseline, and proof the
contract is satisfiable by a *faithful* compiler.

CI-safe: the cr/rr/sr/pr/tr tests are embedder-free (uses `compile_nl` pure
regex + `pack_records` token counting + hand-built batches; no persistence, no
retrieval, no model). The qr tests run a real persist+search round-trip through
a hermetic temp runtime (deterministic hash embedder + SQLite vector adapter),
which is still in-process and network-free, so they stay CI-safe.
"""

from __future__ import annotations

import pytest

from benchmarks.fidelity import contract
from benchmarks.fidelity.golden import GOLDENS
from benchmarks.fidelity.spec_metrics import (
    SpecMetrics,
    measure_spec_metrics,
    passes_promotion,
    provenance_retention,
    reconstruction_rate,
    retrieval_quality,
    semantic_retention,
)
from seam_runtime.mirl import IRBatch, MIRLRecord, RecordKind
from seam_runtime.nl import compile_nl


def _golden(name):
    return next(g for g in GOLDENS if g.name == name)


def _faithful_batch_priya() -> IRBatch:
    """What a correct compiler should emit for 'Priya owns the billing service.':
    verbatim RAW, a localized SPAN, real ENTs, and a grounded (Priya, owns,
    billing_service) claim with a provenance chain. Used to prove the contract +
    §22 metrics are satisfiable (not rigged so only the stub can be scored)."""
    text = "Priya owns the billing service."
    return IRBatch([
        MIRLRecord(id="raw:1", kind=RecordKind.RAW, attrs={"source_ref": "local://input", "content": text, "media_type": "text/plain"}),
        MIRLRecord(id="span:1", kind=RecordKind.SPAN, attrs={"raw_id": "raw:1", "start": 0, "end": len(text)}),
        MIRLRecord(id="prov:1", kind=RecordKind.PROV, attrs={"entity": "raw:1", "activity": "compile_nl", "agent": "system.nl"}),
        MIRLRecord(id="ent:priya", kind=RecordKind.ENT, attrs={"entity_type": "person", "label": "Priya"}),
        MIRLRecord(id="ent:billing", kind=RecordKind.ENT, attrs={"entity_type": "service", "label": "billing service"}),
        MIRLRecord(id="clm:1", kind=RecordKind.CLM, evidence=["span:1"], prov=["prov:1"],
                   attrs={"subject": "ent:priya", "predicate": "owns", "object": "billing service"}),
    ])


# --- the contract fix: faithful compiler must satisfy coverage + §22 -----------

def test_faithful_batch_satisfies_semantic_and_reconstruction():
    golden = _golden("single_fact_ownership")
    batch = _faithful_batch_priya()
    assert semantic_retention(batch, golden) == pytest.approx(1.0)
    assert reconstruction_rate(batch, golden) == pytest.approx(1.0)
    assert provenance_retention(batch) == pytest.approx(1.0)


def test_faithful_batch_passes_all_stage1_checks():
    """The subject-aware claim_content_tokens fix means a correct compiler (subject
    as a separate entity) is recognized as carrying its fact — it must pass every
    Stage-1 check, not just the stub."""
    golden = _golden("single_fact_ownership")
    batch = _faithful_batch_priya()
    assert contract.check_entity_extraction(batch, golden.expected_entities).passed
    assert contract.check_subject_grounding(batch, golden.text).passed
    assert contract.check_separable_coverage(batch, golden.facts).passed
    assert contract.check_segmentation(batch, golden.expected_fact_count).passed
    assert contract.check_raw_verbatim(batch, golden.text).passed


def test_claim_content_tokens_includes_resolved_subject_label():
    batch = _faithful_batch_priya()
    clm = next(r for r in batch.records if r.kind == RecordKind.CLM)
    toks = contract.claim_content_tokens(batch, clm)
    assert {"priya", "owns", "billing", "service"} <= toks  # subject label resolved in


# --- the stub baseline, in spec terms -----------------------------------------

def test_stub_fails_semantic_retention_on_real_memory():
    golden = _golden("single_fact_ownership")
    batch = compile_nl(golden.text)
    # subject (project:SEAM) + predicate (goal) fabricated; only the slug object
    # matches -> 1 of 3 components -> 0.333.
    assert semantic_retention(batch, golden) == pytest.approx(1 / 3, abs=1e-3)
    assert reconstruction_rate(batch, golden) < 1.0  # no real entities recovered


def test_stub_passes_on_its_overfit_input():
    golden = _golden("self_description_overfit")
    batch = compile_nl(golden.text)
    m = measure_spec_metrics(golden.text, batch, golden)
    assert m.sr == pytest.approx(1.0)
    assert m.rr == pytest.approx(1.0)
    assert m.pr == pytest.approx(1.0)


def test_stub_provenance_is_intact_even_when_unfaithful():
    """pr is NOT the metric that exposes the stub: it does bind every claim to a
    span -> raw chain. sr and rr are the discriminators."""
    golden = _golden("single_fact_ownership")
    assert provenance_retention(compile_nl(golden.text)) == pytest.approx(1.0)


def test_stub_compression_ratio_is_below_one():
    """cr exposes the token inflation the Stage-1 harness missed: the packed IR is
    many times larger than the source."""
    golden = _golden("single_fact_ownership")
    batch = compile_nl(golden.text)
    m = measure_spec_metrics(golden.text, batch, golden)
    assert m.cr < 1.0
    assert m.qr is None  # qr is opt-in (measure_qr=False here)


# --- §24 promotion gate --------------------------------------------------------

def test_promotion_gate_rejects_stub():
    golden = _golden("single_fact_ownership")
    m = measure_spec_metrics(golden.text, compile_nl(golden.text), golden)
    ok, reasons = passes_promotion(m, m)
    assert not ok
    assert any("sr" in r for r in reasons)


def test_promotion_gate_accepts_recovering_denser_candidate():
    baseline = SpecMetrics(cr=0.5, rr=1.0, sr=1.0, pr=1.0, tr=1.0, qr=0.80)
    candidate = SpecMetrics(cr=1.2, rr=1.0, sr=1.0, pr=1.0, tr=1.0, qr=0.82)
    ok, reasons = passes_promotion(candidate, baseline)
    assert ok, reasons


def test_promotion_gate_blocks_density_win_that_loses_recovery():
    baseline = SpecMetrics(cr=0.5, rr=1.0, sr=1.0, pr=1.0, tr=1.0, qr=0.80)
    # denser (cr up) but semantic retention collapsed -> must be rejected (§24)
    candidate = SpecMetrics(cr=2.0, rr=0.5, sr=0.40, pr=1.0, tr=1.0, qr=0.80)
    ok, reasons = passes_promotion(candidate, baseline)
    assert not ok
    assert any("sr" in r for r in reasons)


def test_promotion_gate_blocks_unmeasured_qr():
    baseline = SpecMetrics(cr=0.5, rr=1.0, sr=1.0, pr=1.0, tr=1.0, qr=None)
    candidate = SpecMetrics(cr=1.0, rr=1.0, sr=1.0, pr=1.0, tr=1.0, qr=None)
    ok, reasons = passes_promotion(candidate, baseline)
    assert not ok
    assert any("qr" in r for r in reasons)


# --- qr (retrieval_success_at_k): the directly-queryable axis -------------------

def test_every_golden_has_a_query():
    """qr is unmeasurable without a query; the slice requires one per case."""
    for golden in GOLDENS:
        assert golden.query, f"{golden.name} has no qr query"


def test_qr_succeeds_for_stub_on_a_real_memory():
    """Even though the stub fabricates the subject, its slug claim still carries
    the fact's tokens and survives the persist+search round-trip, so the fact is
    queryable -> qr = 1.0. (qr is 'no worse than baseline', not the fabrication
    discriminator; that is sr/cr.)"""
    golden = _golden("single_fact_ownership")
    qr = retrieval_quality(compile_nl(golden.text), golden)
    assert qr == pytest.approx(1.0)


def test_qr_succeeds_for_a_faithful_batch():
    """A correct compiler's grounded claim is also retrievable -> qr satisfiable,
    not rigged so only the stub can score it."""
    golden = _golden("single_fact_ownership")
    qr = retrieval_quality(_faithful_batch_priya(), golden)
    assert qr == pytest.approx(1.0)


def test_qr_is_zero_when_no_record_carries_the_fact():
    """If the compiled batch holds no retrievable record covering the fact, the
    fact is not queryable at all -> qr = 0.0 (no persist needed)."""
    golden = _golden("single_fact_ownership")  # fact tokens: priya/owns/billing/service
    unrelated = compile_nl("The weather is nice today.")
    assert retrieval_quality(unrelated, golden) == pytest.approx(0.0)


def test_qr_is_none_without_a_query():
    from dataclasses import replace

    golden = replace(_golden("single_fact_ownership"), query="")
    assert retrieval_quality(compile_nl(golden.text), golden) is None


def test_measure_qr_opt_in_completes_the_metric_vector():
    """measure_qr=True turns qr from None into a real float so the §24 gate has
    every axis; the gate still rejects the stub (on sr), now with qr measured."""
    golden = _golden("single_fact_ownership")
    batch = compile_nl(golden.text)
    m = measure_spec_metrics(golden.text, batch, golden, measure_qr=True)
    assert m.qr == pytest.approx(1.0)
    ok, reasons = passes_promotion(m, m)
    assert not ok
    assert any("sr" in r for r in reasons)
    assert not any("qr not measured" in r for r in reasons)
