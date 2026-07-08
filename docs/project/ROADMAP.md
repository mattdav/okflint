---
type: ProjectLifeCycle
project: okflint
status: active
updated: 2026-07-08
tags: [python, cli, linter, okf, open-source]
---

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

## v0.3 — Current state

- 3-stage validation: OKF core (§9), profile (manifest), hygiene (opt-in)
- 15 catalogued rules (see [`config/RULES.md`](../../config/RULES.md))
- Generic controlled-vocabulary model: any property constrained via `<prop>_values`, no hardcoded field names (shipped 0.2.0)
- Unified CLI `okflint audit | validate | index`
- `audit` aligned with `validate`: same checks, descriptive, always exit 0 (shipped 0.2.0)
- `okflint index` — deterministic OKF §6 `index.md` generation, dry-run by default (shipped 0.2.0)
- `S202` — deterministic semantic-cohesion split candidate (TF-IDF section clustering), replacing the coarse structural `S201` (shipped 0.3.0)
- Generic engine driven by a YAML manifest
- Manifest self-validation (`manifest.py`)

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

**Update (0.2.0).** The « controlled vocabulary on an arbitrary field » example
above is now shipped: the generic `<prop>_values` model constrains any declared
property. What remains of Track B is the routing/grid layer proper — conditional
required fields, presence rules, and the `routing`/`grid` manifest block still to be
designed.

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

## Track D — `okflint validate-manifest`: expose manifest validation as a command

**Context.** `manifest.py` already validates a manifest's structure and raises
`ManifestError` on virtually anything malformed (missing `base`, empty `roots`,
`_values` on an undeclared property, `required ∩ optional ≠ ∅`, out-of-range
hygiene levels, …). But that validation only fires as a side effect of
`validate`/`audit`/`index`, surfacing as a muddled exit 2 — there is no way to
check a manifest on its own, before scanning any base.

**Direction.** Expose it as a dedicated command — `okflint validate-manifest
<manifest>` — that checks a hand-written manifest **before** scanning anything,
reports « valid » or lists its defects, and exits 0/2. No new validation logic:
extract and surface what `manifest.py` already does.

**Boundary.** Additive, non-breaking → candidate for 0.3.0 on its own. Static,
deterministic, no engine change.

---

## Track E — Generic `okflint fix`: deterministic rewrites

**Context.** Two catalogue rules are already marked auto-fixable (`F106` alias
normalisation, `S102` date reformatting), and `okflint index` (0.2.0) is the first
deterministic generator shipped. These deterministic rewrites currently have no
shared home.

**Direction.** A generic `fix` command hosting the deterministic, judgment-free
rewrites: normalise `type` aliases (F106), reformat date fields (S102), (re)generate
`index.md` (§6). Dry-run + diff by default, write on `--apply` — the `audit`/`index`
convention.

**Boundary — essential.** Deterministic rewrites only. Anything requiring judgment
(what to split, how to rename, what a concept means) never enters `fix`; it stays
with the human or the consuming agent. No LLM in the engine, ever.

---

## Maintenance / technical debt

Small, bounded chores — not exploratory tracks, but tracked so they are not lost.

- **`inv release --dry-run` is not a real dry-run.** `tasks.py` prints
  `[dry-run] …` and then reports the *current* version instead of invoking
  `cz bump --dry-run`; the safety net relied on throughout the 0.2.0 release was
  in fact inert (the real check was done by calling `cz` directly). Fix: make it
  actually run `cz bump --dry-run` and surface its output (target version +
  changelog preview), or remove it rather than keep a lying dry-run.
- **CI `setup-uv` version drift.** `docs.yml` still pins
  `astral-sh/setup-uv@v5` while `release.yml` uses `@v6`. Align `docs.yml` to
  `@v6` in a dedicated `chore(ci)`.
