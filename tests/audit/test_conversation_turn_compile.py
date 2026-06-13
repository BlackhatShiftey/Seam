"""Tests for compile_conversation_turn — conversation text extraction and CLM generation."""

import re

import pytest

from seam_runtime.mirl import RecordKind, Status
from seam_runtime.nl import compile_conversation_turn


def test_creates_raw_span_prov_records():
    """compile_conversation_turn always creates RAW, SPAN, and PROV records."""
    batch = compile_conversation_turn("Caroline: I went to the LGBTQ support group on 7 May 2023.")
    by_kind = {}
    for record in batch.records:
        by_kind.setdefault(record.kind, []).append(record)

    assert RecordKind.RAW in by_kind, f"Expected RAW record, got kinds: {list(by_kind.keys())}"
    assert RecordKind.SPAN in by_kind, f"Expected SPAN record"
    assert RecordKind.PROV in by_kind, f"Expected PROV record"

    raw = by_kind[RecordKind.RAW][0]
    assert raw.attrs.get("content") == "Caroline: I went to the LGBTQ support group on 7 May 2023."

    prov = by_kind[RecordKind.PROV][0]
    assert prov.attrs.get("activity") == "compile_conversation_turn"


def test_extracts_speaker_and_creates_person_ent():
    """Speaker is extracted from Name: prefix and a person ENT record is created."""
    batch = compile_conversation_turn("Caroline: I went to the LGBTQ support group on 7 May 2023.")
    ents = [r for r in batch.records if r.kind == RecordKind.ENT]

    person_ents = [e for e in ents if e.attrs.get("entity_type") == "person"]
    assert len(person_ents) >= 1, f"Expected at least one person ENT, got {[e.attrs for e in ents]}"
    assert person_ents[0].attrs.get("label") == "Caroline"


def test_extracts_date():
    """Date strings are extracted and stored as CLM records with predicate='date'."""
    batch = compile_conversation_turn("Caroline: I went to the LGBTQ support group on 7 May 2023.")
    claims = [r for r in batch.records if r.kind == RecordKind.CLM]

    date_claims = [c for c in claims if c.attrs.get("predicate") == "date"]
    assert len(date_claims) >= 1, f"Expected date claims, got predicates: {[c.attrs.get('predicate') for c in claims]}"
    assert any("7 May 2023" in str(c.attrs.get("object")) for c in date_claims), (
        f"Expected '7 May 2023' in date claim objects, got {[c.attrs.get('object') for c in date_claims]}"
    )


def test_extracts_location():
    """Locations after 'in', 'at', 'to' are extracted with predicate='location'."""
    batch = compile_conversation_turn("Caroline: I went to the LGBTQ support group on 7 May 2023.")
    claims = [r for r in batch.records if r.kind == RecordKind.CLM]

    location_claims = [c for c in claims if c.attrs.get("predicate") == "location"]
    # "the LGBTQ support group" should be extracted after "to"
    location_objects = [str(c.attrs.get("object")) for c in location_claims]
    assert any("LGBTQ" in obj for obj in location_objects), f"Expected LGBTQ in location objects, got {location_objects}"


def test_extracts_action_fact():
    """Action verbs produce CLM records with specific predicates like 'went_to'."""
    batch = compile_conversation_turn("Caroline: I went to the LGBTQ support group on 7 May 2023.")
    claims = [r for r in batch.records if r.kind == RecordKind.CLM]

    action_claims = [c for c in claims if c.attrs.get("predicate") == "went_to"]
    assert len(action_claims) >= 1, f"Expected 'went_to' claim, got predicates: {[c.attrs.get('predicate') for c in claims]}"
    obj = str(action_claims[0].attrs.get("object"))
    assert "LGBTQ support group" in obj, f"Expected 'LGBTQ support group' in went_to object, got {obj!r}"


def test_person_claim_has_speaker_subject():
    """Person CLM has the speaker ENT as the subject."""
    batch = compile_conversation_turn("Alice: I met Bob at the park yesterday.")
    claims = [r for r in batch.records if r.kind == RecordKind.CLM]

    person_claims = [c for c in claims if c.attrs.get("predicate") == "person"]
    assert len(person_claims) >= 1, f"Expected 'person' claim, got: {[c.attrs.get('predicate') for c in claims]}"
    # Subject should reference the speaker entity, not the turn entity
    subject = str(person_claims[0].attrs.get("subject"))
    assert "person" in subject, f"Expected 'person' in subject reference, got {subject!r}"
    assert "alice" in subject.lower(), f"Expected 'alice' in subject reference, got {subject!r}"


def test_fallback_content_claim_when_no_facts_extracted():
    """When no facts can be extracted, a single content CLM with the full text is created."""
    batch = compile_conversation_turn("ok")
    claims = [r for r in batch.records if r.kind == RecordKind.CLM]
    assert len(claims) >= 1, f"Expected at least one fallback claim, got {len(claims)}"
    content_claims = [c for c in claims if c.attrs.get("predicate") == "content"]
    assert len(content_claims) >= 1, f"Expected 'content' fallback claim, got predicates: {[c.attrs.get('predicate') for c in claims]}"
    assert content_claims[0].attrs.get("object") == "ok"


def test_no_speaker_still_works():
    """Conversation turn without a Name: prefix still produces records with turn entity as subject."""
    batch = compile_conversation_turn("I went to the store on 2025-01-15 to buy groceries.")
    claims = [r for r in batch.records if r.kind == RecordKind.CLM]

    # Should extract date '2025-01-15'
    date_claims = [c for c in claims if c.attrs.get("predicate") == "date"]
    assert len(date_claims) >= 1, f"Expected date claim, got: {[c.attrs.get('predicate') for c in claims]}"

    # Should extract action 'went_to'
    action_claims = [c for c in claims if c.attrs.get("predicate") == "went_to"]
    assert len(action_claims) >= 1, f"Expected went_to claim, got: {[c.attrs.get('predicate') for c in claims]}"

    # Subject should be the turn entity, not a person entity
    for c in claims:
        subj = str(c.attrs.get("subject"))
        assert "turn" in subj.lower() or "person" in subj.lower(), f"Subject {subj!r} does not reference turn or person entity"


def test_all_clm_records_have_meaningful_predicates():
    """Every CLM record uses a predicate from the expected set."""
    batch = compile_conversation_turn("Caroline: I went to the LGBTQ support group on 7 May 2023. I met Dr. Smith there.")
    claims = [r for r in batch.records if r.kind == RecordKind.CLM]

    valid_predicates = {
        "person", "date", "location", "mentioned", "went_to", "attended",
        "met", "learned", "felt", "content",
    }
    for claim in claims:
        pred = claim.attrs.get("predicate")
        assert pred in valid_predicates, (
            f"Predicate {pred!r} not in valid set {valid_predicates}. "
            f"Claim attrs: {claim.attrs}"
        )


def test_clm_has_evidence_and_prov():
    """Each CLM record has prov linking to the PROV record and evidence linking to the SPAN."""
    batch = compile_conversation_turn("Caroline: I went to the LGBTQ support group on 7 May 2023.")
    claims = [r for r in batch.records if r.kind == RecordKind.CLM]
    prov_records = [r for r in batch.records if r.kind == RecordKind.PROV]

    assert len(prov_records) == 1, f"Expected exactly one PROV record, got {len(prov_records)}"
    prov_id = prov_records[0].id

    for claim in claims:
        assert prov_id in claim.prov, f"CLM {claim.id} missing PROV reference {prov_id}"
        assert len(claim.evidence) >= 1, f"CLM {claim.id} missing evidence"


def test_compile_nl_floor_is_faithful():
    """compile_nl is the deterministic floor (HISTORY#308): it preserves the input
    verbatim, segments into grounded per-proposition claims, and - crucially -
    NEVER fabricates the old (project:SEAM, goal, <slug>) skeleton."""
    from seam_runtime.nl import compile_nl
    text = "I need to build a vector search engine for my database."
    batch = compile_nl(text)

    raws = [r for r in batch.records if r.kind == RecordKind.RAW]
    assert len(raws) == 1 and raws[0].attrs.get("content") == text  # verbatim RAW

    claims = [r for r in batch.records if r.kind == RecordKind.CLM]
    assert claims, "the floor must emit at least one grounded claim"
    # No fabricated goal/project skeleton, and every claim subject is grounded
    # in the input (no project:SEAM).
    ent_by_id = {r.id: r for r in batch.records if r.kind == RecordKind.ENT}
    allowed = text.lower()
    for claim in claims:
        assert claim.attrs.get("predicate") != "goal", "floor must not fabricate a goal claim"
        subject = claim.attrs.get("subject")
        label = ent_by_id[subject].attrs["label"] if subject in ent_by_id else str(subject)
        for token in re.findall(r"[a-z0-9]+", label.lower()):
            assert token in allowed, f"claim subject {label!r} not grounded in the input"
    assert not any(r.attrs.get("label") == "SEAM" for r in ent_by_id.values()), \
        "floor must not invent a SEAM entity for unrelated input"
