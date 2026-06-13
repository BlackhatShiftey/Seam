"""Golden cases for the MIRL compilation fidelity contract.

Each case carries the input text, the entities and facts a faithful compiler
should surface, and ``baseline_failures`` - the set of contract properties the
*current* ``compile_nl`` stub violates on this input. ``baseline_failures`` is
the failing baseline on record: the fidelity test xfails exactly these, so when
the compiler rewrite makes one pass, the strict xfail flips to a failure and
forces the set to be updated.

The cases are chosen so the contrast is unambiguous: every realistic memory
(G1-G4) fails because the stub fabricates a ``project:SEAM`` subject and mashes
facts into one slug, while the self-description input the stub was overfit to
(G5) passes the full contract - proving the harness is fair and the contract is
satisfiable, not just "the stub always loses".
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
        # One fact, so segmentation/coverage/grounding already hold; the stub
        # still fabricates a SEAM subject and extracts no real entities.
        baseline_failures=frozenset({"entity_extraction", "subject_grounding"}),
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
        # The full failure surface: fabricated subject, no entities, two facts
        # mashed into one slug claim spanning the whole document.
        baseline_failures=frozenset({
            "entity_extraction", "subject_grounding",
            "segmentation", "separable_coverage", "fact_grounding",
        }),
        query="Where do the nightly backups run?",
    ),
    GoldenCase(
        name="personal_event_with_place_and_date",
        text="My sister Maria got married in Lisbon last June.",
        expected_entities=("Maria", "Lisbon"),
        facts=(Fact.of("Maria got married in Lisbon", "Maria married Lisbon",
                       subject="Maria", relation="married", obj="Lisbon"),),
        temporal_facts=("last June",),
        baseline_failures=frozenset({"entity_extraction", "subject_grounding"}),
        query="Where did Maria get married?",
    ),
    GoldenCase(
        name="schedule_change",
        text="The standup moved to 9:30 am on Mondays.",
        expected_entities=("standup",),
        facts=(Fact.of("the standup moved to 9:30 am on Mondays", "standup moved 9 30 am mondays",
                       subject="standup", relation="moved", obj="9:30 am Mondays"),),
        temporal_facts=("9:30 am", "Mondays"),
        baseline_failures=frozenset({"entity_extraction", "subject_grounding"}),
        query="When does the standup happen?",
    ),
    GoldenCase(
        name="self_description_overfit",
        text="I want to build SEAM, a memory translator that compresses meaning.",
        expected_entities=("SEAM",),
        facts=(Fact.of("the goal is to build SEAM, a memory translator", "build SEAM memory translator",
                       subject="SEAM", relation="goal", obj="memory translator"),),
        # The input the stub was written for: it names SEAM and states a goal,
        # so the stub satisfies the whole contract here. Empty baseline_failures.
        baseline_failures=frozenset(),
        query="What do you want to build?",
    ),
)
