from __future__ import annotations

import hashlib
import re
from collections import Counter

from .mirl import IRBatch, MIRLRecord, RecordKind, Status


STOPWORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "into", "is", "it", "of", "on", "or", "that", "the", "this", "to", "we", "with", "without"}

# --- Deterministic honest-minimal floor (SEAM spec §3.2 + §8) ----------------
#
# This replaces the former template that fabricated a (project:SEAM, goal,
# <slug-of-whole-input>) skeleton for every memory. The floor never invents a
# subject or predicate: it preserves the input verbatim in one RAW, splits it
# into propositions with REAL character offsets, and emits one grounded claim
# per proposition whose subject is drawn from that proposition's own text and
# whose object IS the verbatim proposition (so meaning is recoverable, §8).
# Entities are extracted only by high-confidence rules (a sentence's leading
# noun phrase + capitalized proper-noun runs). Rich S-P-O triples (real
# predicates and object structure) are the job of the opt-in extractor (local
# Ollama), added behind the same fidelity contract in a later slice; the floor
# is the zero-new-dep base it sits on.

# Determiners/possessives stripped from the front of a leading subject phrase.
_LEADING_DETERMINERS = {"the", "a", "an", "my", "our", "your", "his", "her", "its", "their", "this", "that", "these", "those"}
# Capitalized words that are NOT proper nouns even when capitalized (usually
# sentence-initial); excluded from the proper-noun entity pass so we don't mint
# entities like "The" or "I".
_NON_ENTITY_CAPS = {"The", "A", "An", "My", "Our", "Your", "His", "Her", "Its", "Their", "This", "That", "These", "Those", "I", "It", "We", "They", "He", "She", "You", "If", "And", "But", "Or", "So", "Then"}

# Sentence-ending punctuation. A run of these is a boundary only when followed
# by whitespace or end-of-string (so 4.2 / 9:30 / B12 don't split). Detected by
# a linear scan, NOT a regex: `[.!?]+(?=\s|$)` is polynomial on uncontrolled
# input (catastrophic backtracking on long "!!!!" runs that fail the lookahead).
_SENTENCE_PUNCT = frozenset(".!?")
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
_PROPER_NOUN_RUN = re.compile(r"[A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*")


def compile_nl(raw_text: str, source_ref: str = "local://input", ns: str = "local.default", scope: str = "thread") -> IRBatch:
    """Compile arbitrary natural language into faithful MIRL (deterministic floor).

    Guarantees, measured by ``benchmarks/fidelity`` against the spec contract:
    the input is preserved verbatim in exactly one RAW record; each proposition
    (sentence) gets a SPAN with real ``(start, end)`` offsets and a CLAIM that is
    grounded in a subject taken from that proposition's own words (NEVER a
    fabricated ``project:SEAM``/``goal``); high-confidence entities (leading
    subject phrases + capitalized proper-noun runs) become ENT records. A claim's
    object is the verbatim proposition, so the fact is recoverable and queryable
    even before a richer extractor assigns a structured relation/object.
    """
    source_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:12]
    # Document-stable, content-unique ids. Unlike the former fixed "raw:1"/"clm:1"
    # ids, these don't collide when several compiled batches are persisted
    # directly into one store (the production path namespaces ids per document;
    # this keeps the un-namespaced path correct too). Deterministic in the input,
    # so repeated compilation stays byte-identical.
    raw_id = f"raw:{source_hash}"
    prov_id = f"prov:compile:{source_hash}"

    records: list[MIRLRecord] = [
        MIRLRecord(id=raw_id, kind=RecordKind.RAW, ns=ns, scope=scope, status=Status.OBSERVED,
                   attrs={"source_ref": source_ref, "content": raw_text, "media_type": "text/plain"}),
        MIRLRecord(id=prov_id, kind=RecordKind.PROV, ns=ns, scope=scope, status=Status.OBSERVED,
                   attrs={"entity": raw_id, "activity": "compile_nl", "agent": "system.nl"}),
    ]

    entity_ids: dict[str, str] = {}

    def entity_id(label: str, entity_type: str = "entity") -> str:
        """Resolve (and lazily create) an ENT for ``label``, deduped by its
        lowercased form. Ids are document-stable and collision-free within the
        batch."""
        key = label.lower()
        existing = entity_ids.get(key)
        if existing is not None:
            return existing
        slug = re.sub(r"[^a-z0-9]+", "_", key).strip("_") or "entity"
        base = f"ent:{slug}:{source_hash}"
        ent_id = base
        suffix = 2
        used = {record.id for record in records}
        while ent_id in used:
            ent_id = f"{base}:{suffix}"
            suffix += 1
        entity_ids[key] = ent_id
        records.append(
            MIRLRecord(id=ent_id, kind=RecordKind.ENT, ns=ns, scope=scope,
                       attrs={"entity_type": entity_type, "label": label})
        )
        return ent_id

    # High-confidence proper-noun entities anywhere in the text.
    for run in _proper_noun_runs(raw_text):
        entity_id(run, "entity")

    span_index = 1
    claim_index = 1
    for proposition, start, end in _segment_propositions(raw_text):
        subject_label = _leading_subject(proposition)
        if not subject_label:
            # A proposition with no word characters carries no fact; skip it
            # rather than fabricate a subject.
            continue
        span_id = f"span:{source_hash}:{span_index}"
        span_index += 1
        records.append(
            MIRLRecord(id=span_id, kind=RecordKind.SPAN, ns=ns, scope=scope, status=Status.OBSERVED,
                       attrs={"raw_id": raw_id, "start": start, "end": end})
        )
        subject = entity_id(subject_label, "entity")
        records.append(
            MIRLRecord(id=f"clm:{source_hash}:{claim_index}", kind=RecordKind.CLM, ns=ns, scope=scope,
                       conf=0.9, prov=[prov_id], evidence=[span_id],
                       attrs={"subject": subject, "predicate": "content", "object": proposition})
        )
        claim_index += 1

    return IRBatch(records)


def _segment_propositions(text: str) -> list[tuple[str, int, int]]:
    """Split ``text`` into propositions (sentences) with REAL character offsets.

    Splits on ``.``/``!``/``?`` runs that are followed by whitespace or end of
    string, so intra-token punctuation (``4.2``, ``9:30``, ``B12``) does not
    split. Each result is ``(proposition_text, start, end)`` with
    ``text[start:end] == proposition_text`` (surrounding whitespace trimmed), and
    only propositions containing at least one word are kept. The boundary scan is
    O(n) and backtracking-free (no regex), so it is safe on uncontrolled input."""
    result: list[tuple[str, int, int]] = []

    def emit(start: int, end: int) -> None:
        segment = text[start:end]
        lead = len(segment) - len(segment.lstrip())
        trimmed = segment.strip()
        if trimmed and _WORD.search(trimmed):
            real_start = start + lead
            result.append((text[real_start:real_start + len(trimmed)], real_start, real_start + len(trimmed)))

    length = len(text)
    cursor = 0
    index = 0
    while index < length:
        if text[index] in _SENTENCE_PUNCT:
            run_end = index
            while run_end < length and text[run_end] in _SENTENCE_PUNCT:
                run_end += 1
            if run_end >= length or text[run_end].isspace():
                emit(cursor, run_end)
                cursor = run_end
            index = run_end
        else:
            index += 1
    if cursor < length:
        emit(cursor, length)
    if not result:
        emit(0, length)
    return result


def _leading_subject(proposition: str) -> str:
    """The proposition's leading noun phrase, used as a GROUNDED claim subject.

    Strip one leading determiner/possessive, take the next word, and extend it
    with any immediately-following capitalized words (a proper-noun tail like
    ``sister Maria``). The result's tokens are always a subset of the input, so
    a claim built on it can never be 'about' an entity absent from the text. This
    is a deterministic approximation, not a parser; a richer extractor refines
    the subject later."""
    words = [match.group(0) for match in _WORD.finditer(proposition)]
    if not words:
        return ""
    index = 1 if (words[0].lower() in _LEADING_DETERMINERS and len(words) > 1) else 0
    parts = [words[index]]
    follow = index + 1
    while follow < len(words) and words[follow][:1].isupper():
        parts.append(words[follow])
        follow += 1
    return " ".join(parts)


def _proper_noun_runs(text: str) -> list[str]:
    """High-confidence proper-noun entities: capitalized word runs, with leading
    capitalized function words (``The``, ``My``, ``I`` ...) stripped. Deduped,
    order-preserving. Deliberately conservative — lowercase common-noun phrases
    (``billing service``) are left to the opt-in extractor."""
    runs: list[str] = []
    seen: set[str] = set()
    for match in _PROPER_NOUN_RUN.finditer(text):
        kept = [word for word in match.group(0).split() if word not in _NON_ENTITY_CAPS]
        if not kept:
            continue
        run = " ".join(kept)
        key = run.lower()
        if key not in seen:
            seen.add(key)
            runs.append(run)
    return runs


def compile_conversation_turn(raw_text: str, source_ref: str = "local://input", ns: str = "local.default", scope: str = "thread") -> IRBatch:
    raw_id = "raw:1"
    span_id = "span:1"
    prov_id = "prov:compile:1"
    source_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:12]
    turn_ent_id = f"ent:turn:{source_hash}"

    records = [
        MIRLRecord(id=raw_id, kind=RecordKind.RAW, ns=ns, scope=scope, status=Status.OBSERVED,
                    attrs={"source_ref": source_ref, "content": raw_text, "media_type": "text/plain"}),
        MIRLRecord(id=span_id, kind=RecordKind.SPAN, ns=ns, scope=scope, status=Status.OBSERVED,
                    attrs={"raw_id": raw_id, "start": 0, "end": len(raw_text)}),
        MIRLRecord(id=prov_id, kind=RecordKind.PROV, ns=ns, scope=scope, status=Status.OBSERVED,
                    attrs={"entity": raw_id, "activity": "compile_conversation_turn", "agent": "system.nl"}),
    ]

    claim_index = 1
    facts_extracted = False

    def add_claim(predicate: str, obj: object, subject: str | None = None, confidence: float = 0.92) -> str:
        nonlocal claim_index, facts_extracted
        subj = subject or turn_ent_id
        claim_id = f"clm:{claim_index}"
        records.append(
            MIRLRecord(
                id=claim_id,
                kind=RecordKind.CLM,
                ns=ns,
                scope=scope,
                conf=confidence,
                prov=[prov_id],
                evidence=[span_id],
                attrs={"subject": subj, "predicate": predicate, "object": obj},
            )
        )
        claim_index += 1
        facts_extracted = True
        return claim_id

    # -- extract speaker from "Name:" pattern --
    speaker_match = re.match(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*:', raw_text)
    speaker = speaker_match.group(1) if speaker_match else None

    speaker_ent_id: str | None = None
    if speaker:
        speaker_ent_id = f"ent:person:{speaker.lower().replace(' ', '_')}_{source_hash}"
        records.append(
            MIRLRecord(id=speaker_ent_id, kind=RecordKind.ENT, ns=ns, scope=scope,
                        attrs={"entity_type": "person", "label": speaker})
        )
        add_claim("person", speaker, subject=speaker_ent_id)

    # -- extract dates --
    _DATE_PATTERNS = [
        r'\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}',
        r'\d{1,2}/\d{1,2}/\d{4}',
        r'\d{4}-\d{2}-\d{2}',
    ]
    dates_seen: set[str] = set()
    for pattern in _DATE_PATTERNS:
        for m in re.finditer(pattern, raw_text):
            date_str = m.group(0)
            if date_str not in dates_seen:
                dates_seen.add(date_str)
                subj = speaker_ent_id or turn_ent_id
                add_claim("date", date_str, subject=subj, confidence=0.9)

    # -- extract locations after "in", "at", "to the" --
    _LOCATION_PATTERN = re.compile(
        r'(?:in|at|to)\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*'
        r'(?:\s+(?:support group|center|office|building|room|hall|park|city|town|street|avenue|lane|road))?)',
        re.IGNORECASE,
    )
    locations_seen: set[str] = set()
    for m in _LOCATION_PATTERN.finditer(raw_text):
        loc = m.group(1).strip()
        if len(loc) > 2 and loc.lower() not in {"the", "a", "an", "i", "me", "my"}:
            if loc not in locations_seen:
                locations_seen.add(loc)
                subj = speaker_ent_id or turn_ent_id
                add_claim("location", loc, subject=subj, confidence=0.85)

    # -- extract named entities: consecutive capitalized words (not at start of sentence) --
    _CAPITALIZED_ENTITY = re.compile(r'(?:^|[.!?]\s+|\b(?:in|at|to|with|from|by|for|on)\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)')
    entities_seen: set[str] = set()
    for m in _CAPITALIZED_ENTITY.finditer(raw_text):
        entity = m.group(1).strip()
        if entity.lower() not in STOPWORDS and entity.lower() not in {"the", "a", "an", "i", "me", "my", "this", "that"}:
            if entity not in entities_seen and entity != speaker:
                entities_seen.add(entity)
                subj = speaker_ent_id or turn_ent_id
                add_claim("mentioned", entity, subject=subj, confidence=0.82)

    # -- extract key action facts from the body text --
    content_text = raw_text.split(':', 1)[1].strip() if ':' in raw_text else raw_text

    _ACTION_PATTERNS = [
        (r'(?:I\s+)?(?:went|go|travell?ed)\s+to\s+(.+?)(?:[,.!]|$)', 'went_to'),
        (r'(?:I\s+)?(?:saw|visited|attended)\s+(.+?)(?:[,.!]|$)', 'attended'),
        (r'(?:I\s+)?(?:met|spoke to|talked to|chatted with)\s+(.+?)(?:[,.!]|$)', 'met'),
        (r'(?:I\s+)?(?:learned|discovered|found out)\s+(?:that\s+)?(.+?)(?:[,.!]|$)', 'learned'),
        (r'(?:I\s+)?(?:feel|felt|am|was)\s+(.+?)(?:[,.!]|$)', 'felt'),
    ]
    for pattern, predicate in _ACTION_PATTERNS:
        m = re.search(pattern, content_text, re.IGNORECASE)
        if m:
            obj = m.group(1).strip().rstrip('.').rstrip(',')
            if obj:
                subj = speaker_ent_id or turn_ent_id
                add_claim(predicate, obj, subject=subj, confidence=0.85)

    # -- fallback: if no facts were extracted, store the full text as a content claim --
    if not facts_extracted:
        add_claim("content", raw_text, subject=turn_ent_id, confidence=0.8)

    return IRBatch(records)


def suggest_symbols(batch: IRBatch, min_frequency: int = 2) -> list[MIRLRecord]:
    counter: Counter[str] = Counter()
    for record in batch.records:
        for key in ("predicate", "entity_type"):
            value = record.attrs.get(key)
            if isinstance(value, str) and len(value) > 8:
                counter[value] += 1
    symbols: list[MIRLRecord] = []
    for index, (value, frequency) in enumerate(counter.items(), start=1):
        if frequency < min_frequency:
            continue
        short = "".join(part[0] for part in value.split("_"))[:6] or f"sym{index}"
        symbols.append(MIRLRecord(id=f"sym:auto:{index}", kind=RecordKind.SYM, status=Status.INFERRED, conf=0.7, attrs={"symbol": short, "expansion": value, "frequency": frequency}))
    return symbols
