# SEAM Query Engine — Learnings from Gemini-SQL2 (future direction)

Date: 2026-06-15. Status: **FUTURE DIRECTION, not scheduled.** This is what SEAM
should learn from the text-to-SQL line of work (Google Gemini-SQL2 reports 80.04%
on BIRD) and how a SEAM-wide query capability would be built later — independent of
any single benchmark or the current cat1/cat3 retrieval work.

There is no public SQL2 API/codebase to integrate; the value is the **product
philosophy**, not a dependency.

## The kernel worth taking

> **A generated query is not trusted until execution + semantic verification succeed.**

This is already SEAM's DNA — the #313 extractor grounding firewall, the §24 promotion
gate, glass-box provenance. So a SEAM Query Engine is an *extension* of the
verify-before-trust philosophy SEAM already practices, applied to a new surface:
**declarative querying of the whole store.**

The single highest-value, model-independent idea:

> **NL → typed query plan → deterministic compilation → verified execution → provenance-backed result.**

The model emits a *typed plan*, never raw executable authority. A deterministic
compiler turns the plan into the actual operation. This preserves SEAM's model
independence (Gemini, GPT, Claude, local Ollama, or a deterministic parser all emit
the same plan schema).

## Why SEAM wants this at all (the SEAM-overall case)

Today SEAM's store is queryable only through `search_ir` (semantic/lexical/graph
retrieval) and hand-typed CLI flags. There is no way for a user or agent to ask a
*structured* question declaratively:

> "active claims about the MIRL compiler decided after June 1, excluding superseded
> ones, with their original evidence."

That needs structured predicates (status / time / record-kind / scope / confidence /
relationships) the retrieval layer doesn't express. A query engine is the declarative
front-end that unifies **structured filters (SQL-like) + semantic retrieval + graph
traversal** over MIRL — and it composes naturally with the multi-hop work (the typed
plan is the right home to express decomposition + edge-expansion declaratively).

## What to take vs leave (blunt triage)

**Take (high value, low effort, model-independent):**
- **Typed query plan** as the model-independent intermediate. The keystone.
- **Read-only AST-validated sandbox** with scope/namespace predicates injected by
  *trusted code* (never requested from the LLM); SQLite authorizer + timeout + row
  limits; deny ATTACH/PRAGMA/extension-load. Build only when querying is exposed.
- **Execution-verified evaluation** (judge executable results, not query strings) —
  SEAM already practices this (BIL, the recall/judge scorers).
- **A semantic schema registry** (NL aliases + MIRL kind/status/edge semantics) so the
  planner understands the store without dumping raw DDL into a prompt.
- **Provenance-backed query traces** — extend `retrieval_event` to record plan,
  compiled query, candidates, selected result, verification. Pure glass-box win.

**Leave / de-prioritize (over-built for SEAM):**
- **The SQL2 candidate-consensus ensemble** (generate 3-5 SQL variants, execute,
  cluster, vote). Its value comes from taming LLM *variance* over messy enterprise
  schemas. A deterministic typed-plan compiler over SEAM's ~10 well-defined tables
  removes that variance by construction — so Phase 1's design eliminates the problem
  Phase 3 solves. Low ROI for SEAM.
- **Heavy schema-linking machinery.** BIRD's hard part is large/dirty/ambiguous
  enterprise schemas; SEAM's schema is small and known. Most of it is N/A.
- **A fine-tuned query specialist** — premature, high-risk, vendor-shaped.
- **Any direct Gemini-SQL2 dependency** — no public API; correctly avoided.

## How it would be implemented later (phased)

- **Phase 1 — deterministic foundation (no LLM):** `seam_runtime/query/` with a typed
  `SEAMQueryPlan`, schema registry, deterministic plan→operation compiler (over the
  existing hybrid retrieval + structured SQLite filters), read-only sandbox, and query
  trace persistence. A fixture-based execution benchmark. CLI `seam query --plan-only`.
- **Phase 2 — model-assisted planning:** NL→plan adapters (Ollama default,
  openai/claude/gemini opt-in), schema linking, ambiguity detection, single-candidate
  verification. The model emits *plans*, not executable authority.
- **Phase 3 — verification scaling (only if needed):** failure-aware repair,
  confidence-gated abstention, cost/latency budgets. Candidate consensus only if a
  measured variance problem actually appears (it shouldn't, given Phase 1).
- **Phase 4 — specialization:** mine successful traces into a gold-query dataset +
  hard negatives + (optional) local-model distillation, reusing SEAM's existing
  self-improvement + benchmark loop.

## Positioning

This belongs on the roadmap as its own track (alongside Track K Trust/Auditability —
the sandbox + provenance traces overlap K's audit ledger), to be prioritized **after**
the current retrieval-quality work (cat1/cat3 recall is the measured bottleneck;
a query engine is a different, additive axis). The extractable kernel — the typed,
model-independent query plan as a declarative front-end to existing retrieval — is the
piece to bank now and build first when this track opens.
