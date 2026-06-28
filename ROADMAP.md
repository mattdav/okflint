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

## Track C — Reaching agents beyond the Python toolchain (MCP server, bundles, standalone binary)

**Problem**. Today okflint is a Python CLI on PyPI. That already serves users who
have a Python toolchain and an agentic harness with a real filesystem and
lifecycle hooks (Claude Code, Gemini CLI, Cursor): they wire okflint validate
into a PostToolUse-style hook and get a deterministic gate on every generated
Markdown file, for free, with the existing CLI. But a large and growing population
of agent users never touch Python — people working in chat-first apps like Claude
Desktop. For them, "validate the Markdown my agent just produced" is out of reach:
no pip install, often no local file at all, and no lifecycle-hook surface to
attach a gate to.

**Direction**. Broaden okflint's invocation surface without touching its engine.
Several packaging layers, all sharing one thin adapter over the existing --json
output:

A thin MCP server (stdio) exposing validate and audit as model-callable
tools. Lets an agent self-diagnose mid-task and self-correct, and is the common
brick under everything below. One server can serve Claude Code, a Gemini CLI
extension, and Claude Desktop alike.
A standalone binary (PyInstaller / shiv / pex) bundling the engine and the
MCP entrypoint into a single runtime-free executable. Removes the Python
dependency entirely — drops into non-Python repos and feeds the bundle below.
A Desktop Extension (.mcpb) wrapping that binary as a "binary MCP server",
giving non-technical Claude Desktop users a one-click, no-JSON, no-Python install.
A Python-based .mcpb would not do: Claude Desktop bundles Node.js, not Python,
and the MCP Python SDK's compiled dependencies cannot be bundled portably — hence
the binary.
Optionally, a remote MCP connector (HTTPS) exposing validate(content, manifest) with the document passed in-band: zero install, zero Python.
Trade-off: hosting cost and document content leaving the user's machine — often
unacceptable on corporate endpoints, so this stays secondary to the local binary.

A Skill (e.g. the OKF skill ecosystem) is the natural instruction layer that
tells an agent to call the okflint tool after generating Markdown, and to fix what
it reports. Coordinating with skill authors is the distribution flywheel.

**Boundary** — essential. Every layer here is transport and packaging, never
engine. The MCP server, the binary, the .mcpb, the remote connector — all are
adapters over the same deterministic core, in the exact same family as the CLI. No
LLM ever enters the engine; okflint stays static and reproducible. One honesty
constraint also carries over: chat-first surfaces like Claude Desktop expose no
lifecycle hooks, so the best they can offer is model-invoked validation (strong
nudging via skill + tool), not a guaranteed gate. A hard, every-time gate still
lives where the documents ultimately land — CI or a pre-commit on the repository or
vault — not in the chat app. okflint provides the check; the harness or the
pipeline decides whether it is advisory or blocking.

---

## Track D — Manifest-driven multi-root scanning (vault-aware CLI)

**Problem.** The current CLI takes a single `--bundle` path, forcing users with
a multi-root base to run N separate `audit` or `validate` commands — one per
root — and mentally stitch the results together. This breaks the core promise of
a multi-root manifest: the `roots` array is already declared in `okf-base.yaml`,
but the CLI ignores it entirely. Cross-root link resolution is blind (a link from
a file in `Dev/` to a file in `.claude/` is always reported broken), and there is
no single pane of glass over the whole base.

The problem sharpens at scale. A knowledge base that spans an Obsidian vault, a
dev workspace, and an agent configuration directory (e.g. `.claude/`) is the
normal end-state for a power user — not a corner case. Requiring four separate
commands to audit it defeats the point of declaring a unified manifest.

**Direction.** When `--manifest` is supplied without `--bundle`, let the manifest
be the sole source of truth: build the file index and the link-resolution graph
over the *union* of all declared `roots`, then scan and report as a single base.

Concrete CLI changes:

```bash
# Proposed — manifest pilots everything
okflint audit --manifest okf-base.yaml
okflint validate --manifest okf-base.yaml
okflint validate --manifest okf-base.yaml src/docs/  # subset target, global index
```

`--bundle` is kept for backward compatibility (single-root bases without a
manifest), but becomes optional when `--manifest` is present and `roots` is
declared. If both are supplied, `--bundle` is treated as a target filter over the
manifest-declared index, not as a root replacement.

The audit JSON output gains a `roots` key listing the resolved paths and per-root
file counts, so downstream consumers (CI dashboards, agents) know which directories
were actually scanned.

**Boundary.** This is purely a CLI and scanning-layer change — no new validation
rules, no engine modification. The manifest schema itself already supports
multi-root (`roots` is already a list); this track makes the CLI honour it.
