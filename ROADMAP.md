# okflint Roadmap

This document outlines envisioned evolutions beyond v0.1. It does not commit to
any timeline — it is a thinking backlog, not a release plan.

okflint follows a stable guiding principle: **deterministically validate the
conformance of a documentary base to OKF and to the framework the base has itself
declared in its manifest.** Every evolution must stay within this scope — no LLM
judgment in the engine, no runtime execution logic. What requires judgment or
orchestration belongs to the *consumer* of the base (an agent, a harness), not the
linter.

---

## v0.1 — Current state

- 3-stage validation: OKF core (§9), profile (manifest), hygiene (opt-in)
- 18 catalogued rules (see [`config/RULES.md`](config/RULES.md))
- Unified CLI `okflint audit | validate`
- Generic engine driven by a YAML manifest (`okf-base.yaml`)
- Manifest self-validation (`manifest.py`)

---

## Track A — Semantic cohesion for finer deterministic splitting

**Problem.** The current `S201` rule (split candidate) relies on coarse structural
signals: presence of multiple `# H1` headings, or a homogeneous list of `## H2`
headings. It misses files that look structurally coherent but mix **thematically
distant topics** — the kind of file that causes agents to react poorly (wrong skills
activated, superfluous context loaded).

**Direction.** Add semantic cohesion rules **measured deterministically**,
without an LLM, for example:

- **Inter-section lexical cohesion**: TF-IDF vectorisation per section, inter-section
  similarity measure. Low cohesion (sections with disjoint vocabularies) flags a
  heterogeneous file → split candidate. Reproducible, auditable.
- **Incoming link family divergence**: if different sections of a file are cited by
  disjoint concept families (section A pointed to by `Decision` nodes, section B by
  `Procedure` nodes), it is probably two concepts.
- **Intra-file tag divergence**: if a file carries (or its sections carry)
  thematically distant tags.

These signals would yield one or more additional hygiene rules
(e.g. `S202` — high thematic heterogeneity). The **final judgment** (should we
split, how to name the pieces) remains outside okflint: it belongs to the human or
to an agent that consumes the diagnostic.

**Boundary.** okflint *signals* a split candidate with metrics; it does not
*decide* or *execute* the split.

---

## Track B — Reading-grid expectations verifiable by the manifest

**Context.** An agent exploiting a base needs a *reading grid*:
from the frontmatter (types, tags), know which concepts to consult for a given
intent, in what order, retrieving as little superfluous context as possible. This
grid is a methodological concern specific to each organisation — it is not
okflint's responsibility.

**What okflint CAN do.** Just as it does not decide which types exist (the manifest
declares them) but verifies the base respects them, okflint can verify that the base
contains **everything needed for a reading grid to work**, provided the manifest
declares the grid's expectations. Examples of declarable, verifiable expectations:

- "Every concept of type `Procedure` must carry a `domain` tag to be routable"
  → conditional required field rule.
- "Values of the `domain` field belong to a closed vocabulary" → controlled
  vocabulary rule on an arbitrary field.
- "Every routable concept declares an `intent`" → presence rule.

This requires extending the manifest with a section describing these expectations
(a `routing` or `grid` block, to be designed), and adding the corresponding
validation rules to the catalogue.

**Boundary — essential.** okflint verifies that the base is **structured to be
routable** (the necessary fields, tags, and vocabularies are present and consistent).
It does **not traverse** the grid: the directed walk "for intent A, read X then Y"
is runtime orchestration logic, executed by the agent in its harness. okflint is
static; it validates a base at rest. The grid makes the base *routable*; the harness
*routes*.
