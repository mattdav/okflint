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

## Track F — OKF v0.2: provenance, trust, lifecycle, attestation

**Context.** Google Cloud published OKF v0.2 on 2026-07-25, six weeks after v0.1.
The change is **additive and backward-compatible**: `type` remains the only
always-required field, every new field is optional, and a v0.1 bundle stays valid
unchanged. What v0.2 adds is vocabulary, not rules.

The motivating problem is one okflint is well placed to serve. When a human writes
a concept, accountability is implicit — someone put their name on it. When an agent
generates ten thousand concepts overnight, that guarantee is gone, and whatever
reads them next must judge each one on signals it can actually see. v0.2 makes five
questions answerable from frontmatter:

| Question | Family |
| --- | --- |
| What was this created from? | provenance |
| How much should I trust it? | trust |
| Is it still true? | freshness |
| Is it the current version? | lifecycle |
| Was this number produced the way we said it must be? | attestation |

Two deliberate renames carry a migration cost for every existing bundle:

| v0.1 | v0.2 |
| --- | --- |
| `timestamp` | `generated.at` |
| body `# Citations` list | `sources` field |

A v0.2 consumer is expected to fall back to the v0.1 forms, so nothing breaks.

**Direction.** Make the target spec version an explicit input rather than an
implicit assumption. The manifest already carries `okf_version`; the engine should
validate against the version the base declares.

- **Dual-form acceptance.** Recognise both `generated.at` and `timestamp`, both the
  `sources` field and the body `# Citations` section. When a base declares
  `okf_version: "0.2"` but still uses v0.1 forms, report it — a warning, not an
  error, mirroring the spec's own fallback stance.
- **Shape validation for the new field families.** `sources` records, `verified`,
  `generated`, and lifecycle `status` all have declared structures. Validating their
  *shape* is squarely in scope, in the same family as every existing frontmatter rule.
- **Lifecycle vocabulary.** `status: deprecated` is a closed-vocabulary case the
  generic `<prop>_values` model already covers — likely little more than a default
  profile entry.
- **`Attested Computation`.** v0.2 introduces this concept type, carrying both what a
  value means and the sanctioned way to compute it. okflint can verify that such a
  concept declares what the spec requires, and that its declared parameters are
  well-formed.

**Boundary — essential.** Two lines okflint must not cross, both of which follow
directly from the guiding principle.

First, **okflint validates that a trust signal is present and well-formed, never
that it is true.** `verified` is the most load-bearing field in v0.2 precisely
because it separates *having read* from *having confirmed*. A tool that implied it
had checked the underlying claim would make the field worthless within a week. The
linter reports the shape of the assertion; only a human or a consuming agent can
make the assertion.

Second, **attestation validation stops at the declaration.** Checking that an
`Attested Computation` is structurally sound is static analysis. Executing the
sanctioned computation, or verifying at runtime that it was the one that actually
ran, is orchestration — it belongs to the consumer of the base, not to the linter.

The v0.1 → v0.2 migration — renaming `timestamp` to `generated.at`, converting a
body `# Citations` list into a `sources` field — is signaled by okflint but never
rewritten by it: the linter does not rewrite.

**Note on timing.** As of 2026-07-27, an ecosystem observer reported that nearly
every tool on Google's community list still targeted v0.1. The window in which
v0.2 support is a differentiator is narrow but real.

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
