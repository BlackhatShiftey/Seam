"""Golden cases for the MIRL compilation fidelity contract.

Each case carries the input text, the entities and facts a faithful compiler
should surface, and ``baseline_failures`` - the set of contract properties the
*current* ``compile_nl`` floor violates on this input. ``baseline_failures`` is
the failing baseline on record: the fidelity test xfails exactly these, so when
the compiler is improved and a property starts passing, the strict xfail flips
to a failure and forces the set to be updated.

History: the original stub fabricated a ``project:SEAM`` subject and mashed
every input into one slug, so every realistic memory (G1-G4) failed
``subject_grounding`` (+ segmentation/coverage/grounding when multi-fact) and
``entity_extraction``. The HISTORY#308 deterministic floor (verbatim RAW,
per-proposition SPAN with real offsets, grounded subjects drawn from the text,
high-confidence proper-noun + leading-subject entities, NEVER a fabricated
claim) closed all of those EXCEPT ``entity_extraction`` for the cases whose
salient entity is a lowercase common-noun phrase (``billing service``,
``west datacenter``) - that needs the opt-in rich extractor (local Ollama), so
those two remain on record as the only baseline failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from benchmarks.fidelity.contract import content_tokens

# Every property name in the contract, in report order.
PROPERTIES = (
    "raw_verbatim",
    "determinism",
    "entity_extraction",
    "subject_grounding",
    "segmentation",
    "separable_coverage",
    "fact_grounding",
)


@dataclass(frozen=True)
class Fact:
    description: str
    # Content tokens that identify this fact; a claim "carries" the fact when
    # these are a subset of the claim's text tokens.
    key_tokens: frozenset[str] = field(default_factory=frozenset)
    # Canonical (subject, relation, object) for the spec §22 `sr` structured
    # semantic-match metric (`spec_metrics.semantic_retention`). Empty when the
    # fact is only used for token-coverage checks.
    subject: str = ""
    relation: str = ""
    obj: str = ""

    @staticmethod
    def of(description: str, key_phrase: str, *, subject: str = "", relation: str = "", obj: str = "") -> "Fact":
        return Fact(
            description=description,
            key_tokens=content_tokens(key_phrase),
            subject=subject,
            relation=relation,
            obj=obj,
        )


@dataclass(frozen=True)
class GoldenCase:
    name: str
    text: str
    expected_entities: tuple[str, ...]
    facts: tuple[Fact, ...]
    baseline_failures: frozenset[str]
    # Temporal facts a faithful compiler should retain, for the spec §22 `tr`
    # metric. Optional; empty means tr is vacuously 1.0 for this case.
    temporal_facts: tuple[str, ...] = ()
    # A natural-language retrieval query about this case's PRIMARY fact
    # (``facts[0]``), for the spec §22 `qr` (retrieval_success_at_k) metric
    # (`spec_metrics.retrieval_quality`). Empty means qr is unmeasurable here.
    query: str = ""

    @property
    def expected_fact_count(self) -> int:
        return len(self.facts)


GOLDENS: tuple[GoldenCase, ...] = (
    GoldenCase(
        name="single_fact_ownership",
        text="Priya owns the billing service.",
        expected_entities=("Priya", "billing service"),
        facts=(Fact.of("Priya owns the billing service", "Priya owns billing service",
                       subject="Priya", relation="owns", obj="billing service"),),
        # The floor grounds the subject ("Priya") and recovers it as an entity,
        # but "billing service" is a lowercase common-noun phrase the floor's
        # high-confidence rules don't surface -> entity_extraction stays failed
        # until the opt-in extractor.
        baseline_failures=frozenset({"entity_extraction"}),
        query="Who owns the billing service?",
    ),
    GoldenCase(
        name="two_independent_facts",
        text="Backups run nightly in the west datacenter. Priya owns the billing service.",
        expected_entities=("billing service", "west datacenter"),
        facts=(
            Fact.of("backups run nightly in the west datacenter", "backups run nightly west datacenter",
                    subject="backups", relation="run", obj="west datacenter"),
            Fact.of("Priya owns the billing service", "Priya owns billing service",
                    subject="Priya", relation="owns", obj="billing service"),
        ),
        # The floor segments the two sentences into two grounded, separable
        # claims with localized spans (segmentation/coverage/grounding/subject
        # all pass); only entity_extraction stays failed because both salient
        # entities are lowercase common-noun phrases.
        baseline_failures=frozenset({"entity_extraction"}),
        query="Where do the nightly backups run?",
    ),
    GoldenCase(
        name="personal_event_with_place_and_date",
        text="My sister Maria got married in Lisbon last June.",
        expected_entities=("Maria", "Lisbon"),
        facts=(Fact.of("Maria got married in Lisbon", "Maria married Lisbon",
                       subject="Maria", relation="married", obj="Lisbon"),),
        temporal_facts=("last June",),
        # Maria + Lisbon are capitalized proper nouns, so the floor recovers both
        # as entities and grounds the subject -> the full contract passes.
        baseline_failures=frozenset(),
        query="Where did Maria get married?",
    ),
    GoldenCase(
        name="schedule_change",
        text="The standup moved to 9:30 am on Mondays.",
        expected_entities=("standup",),
        facts=(Fact.of("the standup moved to 9:30 am on Mondays", "standup moved 9 30 am mondays",
                       subject="standup", relation="moved", obj="9:30 am Mondays"),),
        temporal_facts=("9:30 am", "Mondays"),
        # "standup" is the leading subject phrase, so the floor recovers it as an
        # entity and grounds the claim -> the full contract passes.
        baseline_failures=frozenset(),
        query="When does the standup happen?",
    ),
    GoldenCase(
        name="self_description_overfit",
        text="I want to build SEAM, a memory translator that compresses meaning.",
        expected_entities=("SEAM",),
        facts=(Fact.of("the goal is to build SEAM, a memory translator", "build SEAM memory translator",
                       subject="SEAM", relation="goal", obj="memory translator"),),
        # SEAM is a capitalized proper noun the floor recovers; the single fact
        # is grounded and localized. The full contract passes (note: the floor's
        # generic predicate means sr here is the floor value, not the stub's
        # overfit 1.0 - see test_spec_metrics).
        baseline_failures=frozenset(),
        query="What do you want to build?",
    ),
)
