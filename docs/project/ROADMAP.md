---
type: ProjectLifeCycle
project: okflint
status: active
updated: 2026-08-28
tags: [python, cli, linter, okf, open-source]
---

# okflint Roadmap

This document outlines envisioned evolutions. It does not commit to any
timeline — it is a thinking backlog, not a release plan.

okflint follows a stable guiding principle: **deterministically validate the
conformance of a documentary base to OKF and to the framework the base has itself
declared in its manifest.** Every evolution must stay within this scope — no LLM
judgment in the engine, no runtime execution logic. What requires judgment or
orchestration belongs to the *consumer* of the base (an agent, a harness), not the
linter.

---

## v0.3 — Shipped

- 3-stage validation: OKF core (§11), profile (manifest), hygiene (opt-in)
- Generic controlled-vocabulary model: any property constrained via `<prop>_values`, no hardcoded field names (shipped 0.2.0)
- Unified CLI `okflint audit | validate | index`
- `audit` aligned with `validate`: same checks, descriptive, always exit 0 (shipped 0.2.0)
- `okflint index` — deterministic OKF `index.md` generation, dry-run by default (shipped 0.2.0)
- `S202` — deterministic semantic-cohesion split candidate (TF-IDF section clustering), replacing the coarse structural `S201` (shipped 0.3.0)
- Generic engine driven by a YAML manifest
- Manifest self-validation (`manifest.py`)

---

## v0.4 — Ready to release

25 catalogued rules (see [`config/RULES.md`](../../config/RULES.md)): 7 core,
5 profile, 13 hygiene.

- `okflint validate-manifest` — checks a hand-written manifest on its own,
  before scanning any base; exits 0/2. Surfaces what `manifest.py` already
  validated as a side effect of the other commands (was Track D)
- `manifest_okflint.yaml` migrated to `okf_version: "0.2"` — dogfooding, green
- Multi-root fix for absolute bundle-relative links: a `/x.md` link whose target
  lives in another root of the same manifest is no longer reported as `L002`
- OKF v0.2 support: the manifest's `okf_version` drives validation; a base
  that declares none resolves to `"0.2"` (`Manifest.resolved_okf_version`)
- `F003`, `F004`, `F005` — OKF core shape checks for `generated` and `sources`
  (§5) and for the spec-prescribed `Attested Computation` type (§10)
- `S203`–`S207` — hygiene checks for the v0.2 optional-family shapes
  (`status`, `stale_after`, `generated.at`/`verified[].at`, the actor
  convention, the `Attested Computation` contract), opt-in via
  `hygiene.okf_v02_shapes`
- `S208` — legacy v0.1 forms (`timestamp`, body `# Citations`) on a base
  declaring `okf_version: "0.2"`, opt-in via `hygiene.legacy_forms`
- `S209` — staleness (`stale_after` reached or passed), opt-in via
  `hygiene.stale_content`
- Boundary respected: okflint validates that a trust signal is present and
  well-formed, never that it is true; attestation validation stops at the
  declaration, execution is left to the consumer of the base

---

## Next — migrate the sibling project manifests to `okf_version: "0.2"`

`manifest_okflint.yaml` was migrated as part of the 0.4.0 release and is green:
the base declares no v0.2 family, so the new rules are a strict no-op on it, and
`S208` stays silent on the `timestamp` declared in the profile for `Spec`, `Fix`
and `Plan` — the neutralisation by declared field working exactly as designed.

The sibling project manifests (`manifest_project_template.yaml`, the per-project
`okf-base.yaml` files, and the Home Lab `mattdav-base.yaml`) still declare
`"0.1"`, so the engine emits the informational line on every run there.

Points to watch when migrating each one:

- `S208` stays silent on `timestamp` only where the profile declares it. A
  manifest that does not declare the field will report every document carrying
  one.
- Bases running `unknown_fields: error` must declare any v0.2 family before
  using it.
- The French Home Lab base uses its own vocabulary (`statut`), so `S203` is
  neutralised there by the declared `<prop>_values` rather than by the field
  name.

---

## Discarded directions

- *Track B (reading-grid expectations)* — the useful part (controlled vocabulary
  on an arbitrary property) shipped in 0.2.0; the rest is methodology specific to
  each organisation, not something a standard should tool.
- *Track C (MCP server, standalone binary, `.mcpb`)* — a positioning decision,
  not a scope one: okflint stays a Python CLI, and the MCP surface is covered by
  complementary libraries such as `okf-parser`.
- *Track E (`okflint fix`)* — okflint reports, it does not rewrite. Rewriting
  belongs to the human or to the consuming agent.

---

## Maintenance / technical debt

Small, bounded chores — not exploratory tracks, but tracked so they are not lost.

- **`inv release` forces `part=patch` by default.** `tasks.py` always passes
  `--increment {part}` to `cz bump`, so commitizen never infers the bump level
  from the commit history: a `feat!` / `BREAKING CHANGE` released without an
  explicit `--part=minor` would ship as a patch, silently under-versioning a
  breaking change. Fix: let `cz bump` infer the increment from commits by
  default (drop the forced `--increment`), keeping `--part` as an optional
  override — the version then follows the commits, not a flag one can forget.
- **`.claude/progress.log` stub entries.** The `on-stop` hook has produced an
  empty entry at the end of most PLAN-002 sessions. Harmless, but the file is
  what drives session-to-session continuity, so the stubs erode the one thing it
  is for. Worth a look at `~/.claude/hooks/`.
