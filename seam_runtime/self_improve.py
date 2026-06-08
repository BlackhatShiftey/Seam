"""Self-supervised improvement signal for the H2 loop's front half.

Free, deterministic, paid-free measurement of retrieval quality generated from
the runtime's OWN stored memory corpus - no external benchmark dataset, no judge
calls. A probe takes a stored record as gold, derives a query that record should
answer, runs retrieval, and scores a binary hit (was the source record returned
in the candidate set). Aggregate recall over a held-out probe set is the signal
the auto-proposer optimizes.

Why binary-recall-on-own-corpus is the right driver:

* Free + deterministic: no judge, no API, re-runnable every loop iteration.
* Not gameable by context budget: the gold is "the source record is in the
  candidate set or not", so inflating the packed-context char budget (which
  mechanically lifts LoCoMo's token-overlap ``context_recall``) does not move
  this score. That closes the budget-gaming hazard at the root.
* On-distribution: it optimizes retrieval on the user's real memories.

Probe *difficulty* is the deliberate next lever (paraphrase / multi-hop /
temporal styles): a trivially lexical probe is retrieved regardless of flag
settings and so cannot discriminate between lever configurations. v1 here is
extractive; the ``Scorer`` mechanism, the per-category breakdown, and the
deterministic sampling are what this module pins.
"""

from __future__ import annotations

import random
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, Sequence, runtime_checkable

from .mirl import MIRLRecord, RecordKind, iter_textual_fields

if TYPE_CHECKING:  # avoid import cycle / heavy import at module load
    from .retrieval import RetrievalFlags
    from .runtime import SeamRuntime


@dataclass(frozen=True)
class Probe:
    """One self-supervised retrieval case. ``case_id`` and ``gold_record_id`` are
    the source record's id; a hit is that id appearing in the candidate set.
    ``masked`` is the salient span removed from the record text to form the
    query (the "answer" the query no longer contains) - kept for proposal
    rationale and debugging."""

    case_id: str
    query: str
    gold_record_id: str
    category: str
    masked: str = ""
    style: str = "cloze"


@dataclass(frozen=True)
class ScoreReport:
    """Outcome of a :class:`Scorer` run.

    ``aggregate`` is mean binary recall over the cases; ``per_category`` is the
    same split by category so the proposer can detect a lever that helps one
    category while regressing another (the #273 R1 lesson). ``per_case`` keeps
    the case->hit map so a proposal can cite the exact dev case_ids as evidence.
    """

    scorer: str
    aggregate: float
    n: int
    per_category: dict[str, float] = field(default_factory=dict)
    per_case: dict[str, bool] = field(default_factory=dict)


@runtime_checkable
class Scorer(Protocol):
    """A free, deterministic, per-case dev scorer. External benchmarks (NIAH,
    LoCoMo string-match) and the paid judged tier implement the same shape."""

    name: str

    def score(self, runtime: "SeamRuntime", flags: "RetrievalFlags | None" = None) -> ScoreReport: ...


_WORD_RE = re.compile(r"[^\W\d_]+|\d[\w'./-]*")

# Minimum residual word count for a cloze query to be a usable probe: shorter
# than this and the masked sentence is too thin to identify a record.
_MIN_RESIDUAL_WORDS = 3


def _category_of(record: MIRLRecord) -> str:
    kind = getattr(record, "kind", None)
    return getattr(kind, "value", None) or str(kind)


def _record_text(record: MIRLRecord) -> str | None:
    """The most content-bearing textual field of a record (the cloze source).
    None when the record has no usable text."""
    texts = [t.strip() for t in iter_textual_fields(record) if t and t.strip()]
    if not texts:
        return None
    return max(texts, key=len)


def _salient_index(tokens: list[str]) -> int:
    """Index of the most answer-bearing token to mask, deterministically.

    Priority: a token containing a digit (number / date / code) > a non
    sentence-initial Capitalized token (proper noun) > the longest token. Ties
    break on earliest position.
    """
    for i, token in enumerate(tokens):
        if any(ch.isdigit() for ch in token):
            return i
    for i, token in enumerate(tokens):
        if i > 0 and token[:1].isupper():
            return i
    return max(range(len(tokens)), key=lambda i: len(tokens[i]))


def _cloze(text: str) -> tuple[str, str] | None:
    """Mask the salient word and return (query, masked_surface).

    The query is rebuilt by re-joining the *remaining* word tokens with spaces -
    not by slicing the raw string - so it normalizes both natural text and the
    underscore/slug form SEAM stores compiled records in (e.g.
    ``maria_adopted_..._2021``). The query no longer contains the answer token,
    so a retrieval hit means the record was found from surrounding context, not
    lexical echo. None when there is no maskable span or the residual is too
    thin to identify a record.
    """
    tokens = [m.group() for m in _WORD_RE.finditer(text)]
    if len(tokens) <= _MIN_RESIDUAL_WORDS:
        return None
    pick = _salient_index(tokens)
    residual = tokens[:pick] + tokens[pick + 1 :]
    if len(residual) < _MIN_RESIDUAL_WORDS:
        return None
    return " ".join(residual), tokens[pick]


def generate_probes(
    runtime: "SeamRuntime",
    *,
    ns: str | None = None,
    scope: str | None = None,
    load_limit: int | None = 500,
    sample: int | None = 50,
    seed: int = 1234,
    kinds: Sequence[RecordKind] | None = None,
) -> list[Probe]:
    """Build a deterministic cloze probe set from the runtime's stored corpus.

    Each probe masks the salient span of a record's text (see :func:`_cloze`),
    so the query is a near-paraphrase missing the answer token and a hit means
    retrieval found the record from context, not lexical echo. Records whose
    text has no maskable salient span (labels, too-short fields) are skipped, so
    ``kinds=None`` (all kinds) self-selects the answer-bearing records.

    Determinism (fixed ``seed``) is required so the SAME probe set scores a
    config before and after an ``improvement apply`` - that identity is what
    makes the no-regression ratchet meaningful. An empty/too-small corpus simply
    yields fewer (or zero) probes - the loop no-ops on cold start rather than
    failing.
    """
    batch = runtime.store.load_ir(ns=ns, scope=scope, limit=load_limit)
    kind_set = set(kinds) if kinds else None
    candidates: list[Probe] = []
    for record in batch.records:
        if kind_set is not None and record.kind not in kind_set:
            continue
        text = _record_text(record)
        if not text:
            continue
        cloze = _cloze(text)
        if cloze is None:
            continue
        query, masked = cloze
        candidates.append(
            Probe(
                case_id=record.id,
                query=query,
                gold_record_id=record.id,
                category=_category_of(record),
                masked=masked,
            )
        )

    rng = random.Random(seed)
    rng.shuffle(candidates)
    if sample is not None:
        candidates = candidates[:sample]
    return candidates


@dataclass
class SelfProbeScorer:
    """Scores a probe set: fraction of probes whose gold record is in the
    retrieved candidate set, overall and per category."""

    probes: Sequence[Probe]
    budget: int = 5
    name: str = "self_probe"

    def score(self, runtime: "SeamRuntime", flags: "RetrievalFlags | None" = None) -> ScoreReport:
        per_case: dict[str, bool] = {}
        cat_hits: dict[str, list[bool]] = defaultdict(list)
        for probe in self.probes:
            result = runtime.search_ir(probe.query, budget=self.budget, flags=flags)
            hit = any(c.record.id == probe.gold_record_id for c in result.candidates)
            per_case[probe.case_id] = hit
            cat_hits[probe.category].append(hit)
        n = len(self.probes)
        aggregate = (sum(per_case.values()) / n) if n else 0.0
        per_category = {cat: sum(hits) / len(hits) for cat, hits in cat_hits.items()}
        return ScoreReport(
            scorer=self.name,
            aggregate=aggregate,
            n=n,
            per_category=per_category,
            per_case=dict(per_case),
        )
