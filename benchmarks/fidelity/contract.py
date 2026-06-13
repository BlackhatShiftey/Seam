"""The MIRL compilation fidelity contract, as executable checks.

Each ``check_*`` takes a compiled :class:`IRBatch` (plus the input text and/or
the golden expectation) and returns a :class:`CheckResult`. The checks encode
five properties a faithful compiler must satisfy:

- ``raw_verbatim``      the original text is preserved exactly in one RAW record.
- ``determinism``       same input -> byte-identical records.
- ``entity_extraction`` the salient entities in the text appear as ENT records.
- ``subject_grounding`` no claim is *about* an entity absent from the input
                        (the core faithfulness property - the current stub
                        asserts everything about a fabricated ``project:SEAM``).
- ``segmentation``      N distinct facts produce >= N claims, not one mashed slug.
- ``separable_coverage``every fact is carried by some claim, and no single claim
                        mashes two distinct facts together.
- ``fact_grounding``    in a multi-fact input, no claim's evidence span covers
                        the entire document (claims must localize to their fact).

PROXY HONESTY: these are deterministic structural proxies for semantic
properties, chosen so that (a) a faithful compiler can satisfy them and (b) the
current stub provably violates them on real input. They are not a semantic
oracle. ``subject_grounding`` / ``entity_extraction`` test token grounding, not
meaning; ``separable_coverage`` tests key-token containment. Where a future
backend legitimately normalizes a surface form (e.g. a relation ontology), the
relevant check may need an allowlist - documented at each check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from seam_runtime.mirl import IRBatch, RecordKind

# Function/structure words that may appear in an entity label or fact key
# without being "content" - so "billing service" grounds on {billing, service}
# and a relation like "married_in" grounds on {married}.
_STOPWORDS = frozenset({
    "a", "an", "the", "of", "to", "in", "on", "at", "by", "with", "for",
    "is", "are", "was", "were", "be", "and", "or", "that", "this", "it",
    "as", "from", "into", "my", "our", "their", "his", "her", "its",
})

_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class CheckResult:
    property: str
    passed: bool
    detail: str


def content_tokens(text: str) -> frozenset[str]:
    """Lowercase content words of ``text`` (stopwords removed)."""
    return frozenset(t for t in _WORD_RE.findall(text.lower()) if t not in _STOPWORDS)


def _claims(batch: IRBatch) -> list:
    return [r for r in batch.records if r.kind == RecordKind.CLM]


def _ents_by_id(batch: IRBatch) -> dict:
    return {r.id: r for r in batch.records if r.kind == RecordKind.ENT}


def _spans_by_id(batch: IRBatch) -> dict:
    return {r.id: r for r in batch.records if r.kind == RecordKind.SPAN}


def _claim_text(claim) -> str:
    """All stringy attr values of a claim flattened to one searchable string
    (predicate + object, plus any nested string values)."""
    parts: list[str] = []

    def walk(value):
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, (list, tuple)):
            for v in value:
                walk(v)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)

    for key in ("predicate", "object"):
        if key in claim.attrs:
            walk(claim.attrs[key])
    return " ".join(parts)


def claim_content_tokens(batch: IRBatch, claim) -> frozenset[str]:
    """Content tokens carried by a claim = resolved subject-entity label +
    predicate + object. A claim's subject is an entity *reference*, so a faithful
    claim like ``(ent:priya, owns, billing_service)`` carries 'priya' only via
    its resolved ENT label, not its attrs text. Coverage/reconstruction must see
    that, or a correct compiler (subject as a separate entity) would wrongly look
    like it dropped the subject. The stub's all-in-one slug already contains
    every token, so this does not change the stub baseline."""
    ents = _ents_by_id(batch)
    ent = ents.get(claim.attrs.get("subject"))
    subject_label = str(ent.attrs.get("label", "")) if ent is not None else str(claim.attrs.get("subject") or "")
    return content_tokens(subject_label + " " + _claim_text(claim))


def check_raw_verbatim(batch: IRBatch, text: str) -> CheckResult:
    raws = [r for r in batch.records if r.kind == RecordKind.RAW]
    if len(raws) != 1:
        return CheckResult("raw_verbatim", False, f"expected exactly 1 RAW record, got {len(raws)}")
    content = raws[0].attrs.get("content")
    if content != text:
        return CheckResult("raw_verbatim", False, "RAW content does not equal the input verbatim")
    return CheckResult("raw_verbatim", True, "input preserved verbatim in one RAW record")


def check_determinism(batch_a: IRBatch, batch_b: IRBatch) -> CheckResult:
    a = batch_a.to_json()
    b = batch_b.to_json()
    if a != b:
        return CheckResult("determinism", False, "two compilations of the same input differ")
    return CheckResult("determinism", True, "repeated compilation is byte-identical")


def check_entity_extraction(batch: IRBatch, expected_entities) -> CheckResult:
    """Every expected entity's content tokens must be the content tokens of some
    ENT record's label. The stub only ever emits ``local_user`` + ``SEAM`` so it
    fails for any real-world entity."""
    ent_token_sets = [content_tokens(str(r.attrs.get("label", ""))) for r in batch.records if r.kind == RecordKind.ENT]
    missing = []
    for entity in expected_entities:
        want = content_tokens(entity)
        if not want:
            continue
        if not any(want <= have for have in ent_token_sets):
            missing.append(entity)
    if missing:
        return CheckResult("entity_extraction", False, f"no ENT record covers: {missing}")
    return CheckResult("entity_extraction", True, "every expected entity has an ENT record")


def check_subject_grounding(batch: IRBatch, text: str) -> CheckResult:
    """No claim may be *about* an entity whose label is absent from the input.

    Resolve each claim's ``subject`` to its ENT label; the label's content tokens
    must all appear in the input. This is the precise fabrication the current
    stub commits: asserting every fact about ``project:SEAM`` even when 'SEAM'
    never appears in the text."""
    allowed = content_tokens(text)
    ents = _ents_by_id(batch)
    offenders = []
    for claim in _claims(batch):
        subject = claim.attrs.get("subject")
        ent = ents.get(subject)
        label = str(ent.attrs.get("label", "")) if ent is not None else str(subject or "")
        want = content_tokens(label)
        if want and not (want <= allowed):
            offenders.append(label)
    if offenders:
        return CheckResult("subject_grounding", False, f"claims about entities absent from the input: {sorted(set(offenders))}")
    return CheckResult("subject_grounding", True, "every claim subject is grounded in the input")


def check_segmentation(batch: IRBatch, expected_fact_count: int) -> CheckResult:
    """A text with N distinct facts must yield at least N claims."""
    n = len(_claims(batch))
    if n < expected_fact_count:
        return CheckResult("segmentation", False, f"{expected_fact_count} facts but only {n} claim(s) - facts are mashed")
    return CheckResult("segmentation", True, f"{n} claim(s) for {expected_fact_count} fact(s)")


def check_separable_coverage(batch: IRBatch, facts) -> CheckResult:
    """Every fact is carried by some claim, and no single claim carries two
    distinct facts. A fact is 'in' a claim when the fact's key tokens are a
    subset of the claim's text tokens. The stub's one mashed slug contains every
    fact's tokens, so it carries multiple facts in one claim and fails (b)."""
    claim_token_sets = [(c, claim_content_tokens(batch, c)) for c in _claims(batch)]
    # (a) coverage
    uncovered = []
    for fact in facts:
        if not any(fact.key_tokens <= toks for _c, toks in claim_token_sets):
            uncovered.append(fact.description)
    # (b) separability
    mashed = False
    for _c, toks in claim_token_sets:
        carried = sum(1 for fact in facts if fact.key_tokens <= toks)
        if carried >= 2:
            mashed = True
            break
    if uncovered:
        return CheckResult("separable_coverage", False, f"facts carried by no claim: {uncovered}")
    if mashed:
        return CheckResult("separable_coverage", False, "a single claim mashes >=2 distinct facts together")
    return CheckResult("separable_coverage", True, "each fact maps to its own claim")


def check_fact_grounding(batch: IRBatch, text: str, expected_fact_count: int) -> CheckResult:
    """In a multi-fact input, no claim's evidence span may cover the whole
    document - each claim must localize to the region of its fact. (A single-
    fact input legitimately spans the whole, short document.)"""
    if expected_fact_count < 2:
        return CheckResult("fact_grounding", True, "single-fact input; whole-document span is acceptable")
    spans = _spans_by_id(batch)
    full_len = len(text)
    whole_doc_claims = 0
    for claim in _claims(batch):
        for span_id in claim.evidence:
            span = spans.get(span_id)
            if span is None:
                continue
            start = span.attrs.get("start")
            end = span.attrs.get("end")
            if start == 0 and end == full_len:
                whole_doc_claims += 1
                break
    if whole_doc_claims:
        return CheckResult("fact_grounding", False, f"{whole_doc_claims} claim(s) span the entire document instead of their fact")
    return CheckResult("fact_grounding", True, "claims localize to their fact spans")
