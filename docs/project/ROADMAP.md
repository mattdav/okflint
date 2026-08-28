---
type: ProjectLifeCycle
project: okflint
status: active
updated: 2026-08-03
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

## v0.4 — Current state

- OKF v0.2 support: the manifest's `okf_version` drives validation; a base
  that declares none resolves to `"0.2"` (`Manifest.resolved_okf_version`)
- `F003`, `F004`, `F005` — OKF core (§3a) shape checks for `generated`,
  `sources`, and the spec-prescribed `Attested Computation` type
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

## Discarded directions

- *Track B (reading-grid expectations)* — la partie utile (vocabulaire contrôlé
  sur un champ arbitraire) est livrée en 0.2.0 ; le reste relève de la
  méthodologie propre à chaque organisation, pas d'un standard outillé.
- *Track C (MCP server, standalone binary, .mcpb)* — décision de positionnement,
  pas de périmètre : okflint reste un CLI Python ; la surface MCP est couverte
  par des bibliothèques complémentaires comme `okf-parser`.
- *Track E (`okflint fix`)* — okflint signale, il ne réécrit pas. La réécriture
  appartient à l'humain ou à l'agent consommateur.

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
