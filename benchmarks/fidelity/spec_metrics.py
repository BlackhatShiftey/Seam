"""SEAM-spec §22 compression metrics over a compiled batch.

This reconciles the Stage-1 ad-hoc fidelity checks (`contract.py`) to the
metrics the spec actually defines (`SEAM_SPEC_V0.1.md` §22) and gates on
(§24 "the language is allowed to become denser only when it proves it can still
recover what matters"). Per the governing-contract rule (AGENTS.md Session Start
item 6 / REPO_LEDGER), the compiler is measured by the spec's own contract, not
by invented properties.

§22 metrics (spec definitions):

- ``cr`` compression ratio   = original_token_count / packed_token_count
- ``rr`` reconstruction rate = recovered_fields / required_fields
- ``sr`` semantic retention  = semantic_match(original_ir, reconstructed_ir)
- ``pr`` provenance retention= provenance_links_recovered / provenance_links_expected
- ``tr`` temporal retention  = temporal_facts_recovered / temporal_facts_expected
- ``qr`` retrieval quality   = retrieval_success_at_k

§22 promotion thresholds: ``sr>=0.98``, ``pr==1.00``, ``tr>=0.99``, ``qr`` no
worse than baseline, ``cr`` strictly better than baseline.

How the Stage-1 checks map onto these metrics (they become diagnostic
components, not a parallel contract):

| Stage-1 check        | §22 metric it feeds                                  |
|----------------------|------------------------------------------------------|
| raw_verbatim         | lossless backing — the reconstruction source for rr  |
| determinism          | translator guarantee (§29.1), not a §22 score        |
| entity_extraction    | rr (entities are required fields)                    |
| subject_grounding    | sr (a fabricated subject is a semantic mismatch)     |
| segmentation         | rr (facts recovered as distinct units)               |
| separable_coverage   | rr + sr (each fact recovered without mashing)        |
| fact_grounding       | pr (claims localized to their evidence span)         |

PROXY HONESTY: ``cr`` is exact (token counts). ``sr`` is a structured
triple match against each golden's canonical (subject, relation, object) — a
deterministic stand-in for ``semantic_match(original_ir, reconstructed_ir)``
that catches fabrication (wrong subject/predicate) which a word-overlap score
would miss, because the stub's slug preserves the source *words* while changing
their *meaning*. ``qr`` needs a live ingest+retrieval harness and is deferred to
the next slice (returns ``None`` here); the §24 gate treats an unmeasured metric
as "cannot promote".
"""

from __future__ import annotations

from dataclasses import dataclass

from benchmarks.fidelity.contract import (
    _claims,
    _claim_text,
    _ents_by_id,
    _spans_by_id,
    claim_content_tokens,
    content_tokens,
)
from seam_runtime.lossless import count_prompt_tokens
from seam_runtime.mirl import IRBatch, RecordKind
from seam_runtime.pack import pack_records

# §22 promotion thresholds.
SR_MIN = 0.98
PR_EXACT = 1.00
TR_MIN = 0.99


@dataclass(frozen=True)
class SpecMetrics:
    """The §22 metric vector for one (source, compiled batch). ``qr`` is None
    until the retrieval harness lands (next slice)."""

    cr: float
    rr: float
    sr: float
    pr: float
    tr: float
    qr: float | None = None

    def to_dict(self) -> dict:
        return {"cr": round(self.cr, 6), "rr": round(self.rr, 6), "sr": round(self.sr, 6),
                "pr": round(self.pr, 6), "tr": round(self.tr, 6),
                "qr": None if self.qr is None else round(self.qr, 6)}


def compression_ratio(source_text: str, batch: IRBatch) -> float:
    """cr = original NL tokens / packed (context PACK) tokens. Spec §22 measures
    NL->PACK density (the north star), NOT the IR->PACK ratio `score_pack`
    already reports. A huge budget is used so nothing is dropped — we measure
    the full packed form. For a single short sentence cr is typically < 1 (the
    IR+pack is larger than the sentence); the density win is corpus-scale."""
    src_tokens, _ = count_prompt_tokens(source_text)
    pack = pack_records(batch.records, lens="general", budget=1_000_000, mode="context")
    return src_tokens / max(pack.token_cost, 1)


def reconstruction_rate(batch: IRBatch, golden) -> float:
    """rr = recovered required fields / required fields. Required fields are the
    golden's expected entities + facts + temporal facts; a field is recovered
    when it is present in the IR (entity has an ENT; fact's key tokens are
    carried by some claim; temporal token appears in a claim)."""
    ent_token_sets = [content_tokens(str(r.attrs.get("label", ""))) for r in batch.records if r.kind == RecordKind.ENT]
    claim_token_sets = [claim_content_tokens(batch, c) for c in _claims(batch)]

    required = 0
    recovered = 0
    for entity in golden.expected_entities:
        want = content_tokens(entity)
        if not want:
            continue
        required += 1
        if any(want <= have for have in ent_token_sets):
            recovered += 1
    for fact in golden.facts:
        required += 1
        if any(fact.key_tokens <= toks for toks in claim_token_sets):
            recovered += 1
    for temporal in getattr(golden, "temporal_facts", ()):  # optional
        want = content_tokens(temporal)
        if not want:
            continue
        required += 1
        if any(want <= toks for toks in claim_token_sets):
            recovered += 1
    return recovered / required if required else 1.0


def semantic_retention(batch: IRBatch, golden) -> float:
    """sr = mean structured-triple match over the golden's facts. For each fact
    with a canonical (subject, relation, object), find the best claim and score
    (subject grounded+matching + predicate matching + object matching) / 3.
    Catches the stub's fabrication: it asserts (project:SEAM, goal, <slug>), so
    subject/predicate mismatch even though the slug preserves the words."""
    facts = [f for f in golden.facts if f.subject or f.relation or f.obj]
    if not facts:
        return 1.0  # nothing structured to retain
    ents = _ents_by_id(batch)
    claims = _claims(batch)
    if not claims:
        return 0.0

    def best_triple_match(fact) -> float:
        want_s, want_r, want_o = content_tokens(fact.subject), content_tokens(fact.relation), content_tokens(fact.obj)
        best = 0.0
        for claim in claims:
            ent = ents.get(claim.attrs.get("subject"))
            subj_tokens = content_tokens(str(ent.attrs.get("label", ""))) if ent is not None else content_tokens(str(claim.attrs.get("subject") or ""))
            pred_tokens = content_tokens(str(claim.attrs.get("predicate") or ""))
            obj_tokens = content_tokens(_claim_text(claim))
            s = 1.0 if want_s and want_s <= subj_tokens else 0.0
            r = 1.0 if want_r and (want_r <= pred_tokens or pred_tokens <= want_r) else 0.0
            o = 1.0 if want_o and want_o <= obj_tokens else 0.0
            best = max(best, (s + r + o) / 3.0)
        return best

    return sum(best_triple_match(f) for f in facts) / len(facts)


def provenance_retention(batch: IRBatch) -> float:
    """pr = claims with a complete evidence chain (claim -> SPAN -> RAW) / total
    claims. §22 threshold is 1.00. (The current stub actually satisfies this —
    it does bind every claim to span:1 -> raw:1 — so pr is not the metric that
    exposes the stub; sr and rr are.)"""
    claims = _claims(batch)
    if not claims:
        return 1.0
    spans = _spans_by_id(batch)
    raws = {r.id for r in batch.records if r.kind == RecordKind.RAW}
    complete = 0
    for claim in claims:
        for span_id in claim.evidence:
            span = spans.get(span_id)
            if span is not None and span.attrs.get("raw_id") in raws:
                complete += 1
                break
    return complete / len(claims)


def temporal_retention(batch: IRBatch, golden) -> float:
    """tr = temporal facts recovered / expected. A temporal fact is recovered
    when its tokens appear in a claim or a record carries t0/t1. tr = 1.0 when
    the golden declares no temporal facts (nothing to lose)."""
    expected = list(getattr(golden, "temporal_facts", ()))
    if not expected:
        return 1.0
    claim_token_sets = [claim_content_tokens(batch, c) for c in _claims(batch)]
    has_temporal_field = any(r.t0 is not None or r.t1 is not None for r in batch.records)
    recovered = 0
    for temporal in expected:
        want = content_tokens(temporal)
        if not want:
            continue
        if has_temporal_field or any(want <= toks for toks in claim_token_sets):
            recovered += 1
    return recovered / len(expected)


def retrieval_quality(batch: IRBatch, golden) -> None:
    """qr = retrieval_success_at_k. Deferred: needs a live ingest + search_ir
    harness (embedder + store). Returns None until the next slice; the §24 gate
    treats None as 'cannot promote'."""
    return None


def measure_spec_metrics(source_text: str, batch: IRBatch, golden) -> SpecMetrics:
    """Compute the §22 metric vector for one compiled batch (qr deferred)."""
    return SpecMetrics(
        cr=compression_ratio(source_text, batch),
        rr=reconstruction_rate(batch, golden),
        sr=semantic_retention(batch, golden),
        pr=provenance_retention(batch),
        tr=temporal_retention(batch, golden),
        qr=retrieval_quality(batch, golden),
    )


def passes_promotion(candidate: SpecMetrics, baseline: SpecMetrics) -> tuple[bool, list[str]]:
    """§24 promotion gate: a candidate may be promoted only if it preserves
    recoverability AND strictly improves density. Returns (ok, failed_reasons).
    An unmeasured metric (None) blocks promotion (conservative)."""
    reasons: list[str] = []
    if candidate.sr < SR_MIN:
        reasons.append(f"sr {candidate.sr:.4f} < {SR_MIN}")
    if candidate.pr < PR_EXACT:
        reasons.append(f"pr {candidate.pr:.4f} != {PR_EXACT}")
    if candidate.tr < TR_MIN:
        reasons.append(f"tr {candidate.tr:.4f} < {TR_MIN}")
    if candidate.qr is None or baseline.qr is None:
        reasons.append("qr not measured (retrieval harness pending)")
    elif candidate.qr < baseline.qr:
        reasons.append(f"qr {candidate.qr:.4f} < baseline {baseline.qr:.4f}")
    if not candidate.cr > baseline.cr:
        reasons.append(f"cr {candidate.cr:.4f} not strictly > baseline {baseline.cr:.4f}")
    return (not reasons, reasons)
