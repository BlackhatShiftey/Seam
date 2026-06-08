"""Self-improvement front half, foundation: the free self-probe scorer.

Pins the STABLE mechanism - binary hit detection against the candidate set,
the ScoreReport shape, deterministic probe sampling, the cold-start no-op, and
the explicit-flags ablation hook on search_ir. It deliberately does NOT pin the
v1 query-extraction heuristic in generate_probes (probe difficulty is the next
design lever and is expected to change); tests that need controlled hit/miss
build Probe objects directly.
"""

from __future__ import annotations

from seam_runtime.mirl import RecordKind
from seam_runtime.retrieval import RetrievalFlags
from seam_runtime.runtime import SeamRuntime
from seam_runtime.self_improve import (
    Probe,
    ScoreReport,
    SelfProbeScorer,
    generate_probes,
)

_FACTS = [
    "Maria adopted a rescue greyhound named Pixel in March 2021.",
    "The quarterly revenue target for the Helsinki office is 4.2 million euros.",
    "Daniel switched from a vegetarian to a pescatarian diet last winter.",
    "The backup server room is on the third floor behind the east stairwell.",
    "Priya's flight to Singapore departs at 6:45 AM from gate B12.",
    "The museum's deep-sea bioluminescence exhibit opens in October.",
]


def _seed(runtime: SeamRuntime) -> None:
    for i, fact in enumerate(_FACTS):
        runtime.persist_ir(runtime.compile_nl(fact, source_ref=f"unit://fact-{i}"))


def _two_retrievable_records(runtime: SeamRuntime):
    """Pick two distinct records whose own text retrieves them at top-1."""
    from seam_runtime.self_improve import _record_text

    picks = []
    for record in runtime.store.load_ir().records:
        query = _record_text(record)
        if not query:
            continue
        result = runtime.search_ir(query, budget=1)
        if result.candidates and result.candidates[0].record.id == record.id:
            picks.append((record.id, query))
        if len(picks) == 2:
            break
    return picks


def test_scorer_detects_hit_and_miss(tmp_path):
    runtime = SeamRuntime(tmp_path / "p.db")
    _seed(runtime)
    picks = _two_retrievable_records(runtime)
    assert len(picks) == 2, "need two self-retrievable records to exercise hit vs miss"
    (id_a, query_a), (id_b, _query_b) = picks

    hit = Probe(case_id="hit", query=query_a, gold_record_id=id_a, category="t")
    # query_a retrieves record A at top-1, so gold=B is NOT in the top-1 set -> miss
    miss = Probe(case_id="miss", query=query_a, gold_record_id=id_b, category="t")

    report = SelfProbeScorer([hit, miss], budget=1).score(runtime)

    assert report.per_case == {"hit": True, "miss": False}
    assert report.aggregate == 0.5
    assert report.n == 2


def test_score_report_shape(tmp_path):
    runtime = SeamRuntime(tmp_path / "p.db")
    _seed(runtime)
    probes = generate_probes(runtime, kinds=None, sample=8)
    report = SelfProbeScorer(probes).score(runtime)

    assert isinstance(report, ScoreReport)
    assert report.scorer == "self_probe"
    assert 0.0 <= report.aggregate <= 1.0
    assert report.n == len(probes)
    assert set(report.per_case) == {p.case_id for p in probes}
    # aggregate is exactly mean of per_case hits
    assert report.aggregate == sum(report.per_case.values()) / report.n
    # every probe category is represented in the breakdown
    assert set(report.per_category) == {p.category for p in probes}


def test_generate_probes_is_deterministic(tmp_path):
    runtime = SeamRuntime(tmp_path / "p.db")
    _seed(runtime)
    first = [p.case_id for p in generate_probes(runtime, kinds=None, sample=6, seed=99)]
    second = [p.case_id for p in generate_probes(runtime, kinds=None, sample=6, seed=99)]
    assert first == second
    assert first  # non-empty on a seeded corpus


def test_generate_probes_respects_sample_cap(tmp_path):
    runtime = SeamRuntime(tmp_path / "p.db")
    _seed(runtime)
    probes = generate_probes(runtime, kinds=None, sample=3)
    assert len(probes) <= 3


def test_empty_corpus_is_a_noop(tmp_path):
    runtime = SeamRuntime(tmp_path / "empty.db")
    probes = generate_probes(runtime, kinds=None)
    assert probes == []
    report = SelfProbeScorer(probes).score(runtime)
    assert report.aggregate == 0.0
    assert report.n == 0
    assert report.per_category == {}


def test_explicit_flags_hook_is_honored(tmp_path):
    """The scorer must be able to ablate a lever via explicit flags without
    mutating env or the runtime's cached flags (the proposer's counterfactual)."""
    runtime = SeamRuntime(tmp_path / "p.db")
    _seed(runtime)
    probes = generate_probes(runtime, kinds=None, sample=6)
    scorer = SelfProbeScorer(probes)

    baseline = scorer.score(runtime, flags=RetrievalFlags())
    ablated = scorer.score(runtime, flags=RetrievalFlags(bm25_all_kinds=True, fusion="rrf"))

    # Both run cleanly and are well-formed; the cached runtime flags are untouched.
    assert baseline.n == ablated.n == len(probes)
    assert runtime._retrieval_flags is None  # never resolved the cache on this path


def test_generate_probes_raw_default_filters_kind(tmp_path):
    runtime = SeamRuntime(tmp_path / "p.db")
    _seed(runtime)
    raw_probes = generate_probes(runtime, kinds=(RecordKind.RAW,))
    assert all(p.category == "RAW" for p in raw_probes)
