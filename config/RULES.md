---
type: ProjectStandards
project: okflint
updated: 2026-06-28
tags: [lint, rules]
---


# okflint rules

`okflint` verifies that a documentary base conforms to [OKF v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) **and** to the framework the base has itself declared in its manifest.

This document lists all check points, their code, their severity, and how to fix each case.

---

## Philosophy: three stages

OKF is deliberately minimal — its conformance clause (§11) imposes only three
rules. But the spec explicitly invites each producer to refine their framework
beyond that (« anything beyond that is left to the producer »). `okflint`
materialises this invitation as three stages of distinct authority:

| Stage | Authority | Output prefix | Severity | Exit code effect |
| --- | --- | --- | --- | --- |
| **OKF core** | OKF v0.2 spec §11 (universal, non-negotiable) | `OKF non-conformant` | error | `exit 1` |
| **Profile** | the manifest *you* declared | `Profile not respected` | error | `exit 1` |
| **Hygiene** | stricter than OKF (opt-in) | `hygiene (out-of-spec)` | warning | `exit 0` |

The key point: violating **the spec** and violating **your declared contract** are
two different things. In the strict OKF sense, a base that declares a manifest
but does not respect it remains *literally* parsable — but it betrays the OKF spirit
(a self-describing base must keep its own promises). `okflint` flags both,
naming them distinctly.

The core is hardcoded. Profile and hygiene only fire if your manifest declares
them: a minimal base (manifest reduced to the bare minimum) will only be checked
against the OKF core.

Without a manifest, `okflint` only controls the core, on the sole basis of what
the documents contain. With a manifest, the producer commits to declaring
exhaustively what the bundle uses, and `okflint` holds it to that commitment
— including for spec-prescribed vocabulary such as `Attested Computation`
(see `F005`).

---

## Stage 1 — OKF core

Always active. Hardcoded. Corresponds word-for-word to the OKF v0.2 conformance
clause (§11) and to the structural constraints of reserved files (§8, §9, §11).

### `F001` — Frontmatter absent or unparsable

**Severity**: error · **Source**: OKF §11.1

Every non-reserved `.md` file must begin with a YAML frontmatter block delimited
by `---`, and that block must be parsable.

```markdown
<!-- ❌ F001: no frontmatter -->
# My concept
...

<!-- ✅ fixed -->
---
type: Reference
---

# My concept
...
```

**Fix**: add a valid frontmatter block at the top of the file.

### `F002` — `type` field absent or empty

**Severity**: error · **Source**: OKF §11.2

The frontmatter must contain a non-empty `type` field. This is the **only** field
OKF makes mandatory.

```yaml
# ❌ F002: type missing
---
title: My concept
---

# ✅ fixed
---
type: Reference
title: My concept
---
```

**Fix**: set a descriptive `type`. OKF imposes no particular value; if a profile
is declared, see `F101`.

### `F003` — `generated` present without `generated.by`

**Severity**: error · **Source**: OKF v0.2, [SPEC-002](../docs/specs/SPEC-002_okf-v0.2.md) §3a

Optional families are never a defect when absent (OKF v0.2 conformance clause,
§11). But when a concept *does* carry a `generated` block, the spec makes
`generated.by` REQUIRED inside it — so a `generated` block without a `by` is a
structural violation, not a missing option. Only fires on a base whose
resolved `okf_version` is `"0.2"`; a base declaring `"0.1"` is validated
exactly as before v0.2 support existed.

```yaml
# ❌ F003: generated without by
---
type: Reference
generated:
  at: "2026-01-01T00:00:00Z"
---

# ✅ fixed
---
type: Reference
generated:
  by: "human:mdaviaud"
  at: "2026-01-01T00:00:00Z"
---
```

**Fix**: add `generated.by`, following the actor convention (`S206`).

### `F004` — `sources` entry without `resource`

**Severity**: error · **Source**: OKF v0.2, [SPEC-002](../docs/specs/SPEC-002_okf-v0.2.md) §3a

Same principle as `F003`: `sources` is optional, but a present `sources` MUST
be a list of mappings, and each entry MUST carry `resource`. A `sources`
value that is not a list of mappings also triggers this code. Only fires on a
base whose resolved `okf_version` is `"0.2"`.

```yaml
# ❌ F004: entry without resource
---
type: Reference
sources:
  - id: s1
---

# ✅ fixed
---
type: Reference
sources:
  - id: s1
    resource: /tables/customers.md
---
```

**Fix**: give every `sources` entry a `resource`, or fix the field's shape to
a list of mappings.

### `F005` — `Attested Computation` concept without `runtime`

**Severity**: error · **Source**: OKF v0.2, [SPEC-002](../docs/specs/SPEC-002_okf-v0.2.md) §3a, §7

`Attested Computation` is the one concept type v0.2 prescribes in the spec
itself, not through a manifest — hardcoded in the engine exactly like
`index.md`/`log.md` are. `runtime` is REQUIRED on that type. This check
applies with or without a manifest loaded, and creates no exemption to
`F101`/`F201`: a manifest that declares `Attested Computation` still must
declare it exhaustively, and okflint still enforces its own schema on top.
Only fires on a base whose resolved `okf_version` is `"0.2"`.

```yaml
# ❌ F005: Attested Computation without runtime
---
type: Attested Computation
---

# ✅ fixed
---
type: Attested Computation
runtime: dbt/1.8
---
```

**Fix**: set `runtime` on every `Attested Computation` concept.

### `R001` — Frontmatter forbidden in `index.md`

**Severity**: error · **Source**: OKF §8, §11

An `index.md` contains no frontmatter, with one exception: the `index.md` at
the bundle root may carry `okf_version` (and nothing else).

```yaml
# ❌ R001: full frontmatter in an index.md
---
type: Reference
tags: [home]
---

# ✅ allowed only at the bundle root
---
okf_version: "0.1"
---
```

**Fix**: remove the frontmatter from `index.md`, or reduce it to
`okf_version` if it is the root index.

### `R002` — Non-ISO date heading in `log.md`

**Severity**: error · **Source**: OKF §9

In a `log.md`, date headings must be in ISO 8601 `YYYY-MM-DD` format.

```markdown
<!-- ❌ R002 -->
## 22 May 2026

<!-- ✅ fixed -->
## 2026-05-22
```

**Fix**: reformat date headings as `YYYY-MM-DD`.

---

## Stage 2 — Profile

Only fired when the manifest declares a `profile` block. These rules encode
**your** framework: your types, your fields, your controlled vocabularies.
They are not OKF in the strict sense — they are the contractual refinement you
chose, and that `okflint` helps you uphold.

### `F101` — `type` value not in declared types

**Severity**: error

A concept's `type` must be one of the types declared in `profile.types`.
(Only fires if the profile declares a list of types.)

**Fix**: use a declared type, or add the type to the manifest if it is legitimate.

### `F102` — Missing required field

**Severity**: error

Each type declares its `required` fields. A concept of that type must carry
all of them.

```yaml
# profile.types.Decision.required = [type, status, created]
# ❌ F102: created missing
---
type: Decision
status: Accepted
---
```

**Fix**: add the missing field.

### `F105` — Value outside controlled vocabulary

**Severity**: error

Any property may declare a controlled vocabulary by adding a `<prop>_values`
key alongside `required`/`optional` in the type's configuration (e.g.
`status_values` constrains a `status` property). When the property is present
on a concept of that type, its value must belong to the declared list. This is
orthogonal to presence: whether the property is required, optional, or absent
from a concept is governed solely by `required`/`optional` (and, for unlisted
fields, by the `unknown_fields` hygiene setting).

```yaml
# profile.types.Procedure: required/optional include `status`,
# and status_values = [draft, prod, obsolete]
# ❌ F105
---
type: Procedure
status: in-progress
---
```

**Fix**: use a declared value, or extend the vocabulary in the manifest.

### `F106` — Non-normalised `type` spelling

**Severity**: error

If a type declares `aliases`, an alternative spelling is tolerated on reading
but flagged for normalisation (e.g. `adr` → `Decision`).

**Fix**: replace the spelling with the type's canonical name.

### `S102` — Non-ISO date field

**Severity**: error

Fields listed in `profile.date_fields` must be in ISO `YYYY-MM-DD` format
when present.

```yaml
# profile.date_fields = [created, updated]
# ❌ S102
---
type: Decision
created: 2026-5-1
---

# ✅ fixed
created: 2026-05-01
```

**Fix**: reformat the date as `YYYY-MM-DD`.

---

## Stage 3 — Hygiene

Stricter than OKF. OKF explicitly asks consumers to **tolerate** these cases
(« Consumers MUST tolerate broken links »). `okflint` flags them anyway, because
a well-maintained base benefits from fixing them — but as **warnings**, never
errors, and always labelled as out-of-spec. Configurable via the `hygiene` block
in the manifest (`off` | `warn` | `error`).

### `L001` — Broken wikilink

**Severity**: warning (configurable) · **Out-of-spec**

A wikilink `[[Target]]` whose target does not exist in the base. Note: wikilinks
are an Obsidian convention, not OKF (which uses markdown links).

**Fix**: fix the target, or declare the reference in
`base.link_resolution.external_refs` if it is out-of-base and assumed valid.

### `L002` — Broken markdown link

**Severity**: warning (configurable) · **Out-of-spec**

A link `[text](/path.md)` whose target does not exist in the base.

**Fix**: fix the destination path.

### `L003` — Ambiguous wikilink

**Severity**: warning (configurable) · **Out-of-spec**

A wikilink `[[Target]]` that resolves to multiple files in the base (same name
in different directories).

**Fix**: specify the path, or disambiguate file names.

### `S202` — Split candidate (semantic cohesion)

**Severity**: warning (configurable) · **Out-of-spec**

A file whose body decomposes into more than one semantic cluster, detected via
TF-IDF cosine similarity between paragraphs (connected components at a
calibrated similarity threshold). A signal, never an obligation: splitting
remains an editorial choice.

**Fix**: consider splitting the file into multiple concepts, or ignore if the
cohesion justifies keeping it together.

### `R201` — Recommended reserved file missing

**Severity**: warning (configurable, `off` by default) · **Out-of-spec**

An `index.md` or `log.md` is missing at a root's directory level. OKF makes
these files **optional** (§3) and explicitly forbids rejecting a base for their
absence (§11). `okflint` only flags them on request, for producers who adopt an
internal convention of progressive disclosure (one `index.md` per directory).

> ⚠️ Not to be confused with `R001`/`R002` (OKF core): those check the
> **structure** of reserved files *when they exist*; `R201` only concerns
> their **presence**, which remains optional under OKF.

**Fix**: add an `index.md` / `log.md`, or leave `reserved_files: off` in the
manifest if the absence is intentional.

### `F201` — Frontmatter field outside declared schema

**Severity**: warning (configurable, `off` by default) · **Out-of-spec**

A concept carries a frontmatter field absent from `required ∪ optional` for its
type. OKF explicitly allows additional fields (§4.1: *« Producers MAY include any
additional keys »*) and forbids rejecting for this — so never an error. But as a
warning, the rule catches typos (`tag:` instead of `tags:`) and silent schema
drift. Only fires if a profile declares the relevant type.

**Fix**: fix the field name, add it to `optional` in the manifest if legitimate,
or leave `unknown_fields: off` if the base intentionally allows free fields.

### `S203` — `status` outside `draft | stable | deprecated`

**Severity**: warning (configurable, `warn` by default via
`hygiene.okf_v02_shapes`) · **Out-of-spec**

OKF v0.2's default `status` vocabulary is a SHOULD-level recommendation
([SPEC-002](../docs/specs/SPEC-002_okf-v0.2.md) §5.4, not among §11's three
MUSTs), not a structural requirement. It only fires when `status` is present.
**Never fires** if the manifest declares a `status_values` controlled
vocabulary for the concept's type (`F105`, Stage 2): the producer's profile
overrides the spec's default. Only fires on a base whose resolved
`okf_version` is `"0.2"`.

Overriding the vocabulary via `status_values` costs **portability, not
conformance**: a third-party consumer knows what to do with `deprecated`,
not with `archived`. This must be documented as such wherever a profile
overrides `status`. It also means §5.4's default — `status` absent ⇒
`stable` — loses its meaning as soon as the vocabulary is overridden: there
is no longer a single agreed default to fall back to.

```yaml
# ❌ S203
---
type: Reference
status: wip
---

# ✅ fixed
---
type: Reference
status: draft
---
```

**Fix**: use `draft`, `stable`, or `deprecated`, or declare a
`status_values` vocabulary in the manifest if the base uses its own.

### `S204` — `stale_after` incorrectly formatted

**Severity**: warning (configurable, `warn` by default via
`hygiene.okf_v02_shapes`) · **Out-of-spec**

`stale_after`, when present, must be `YYYY-MM-DD`. Does not double-report if
`stale_after` is already listed in `profile.date_fields` (already covered by
`S102`). Only fires on a base whose resolved `okf_version` is `"0.2"`.

```yaml
# ❌ S204
---
type: Reference
stale_after: 01/06/2026
---
```

**Fix**: reformat as `YYYY-MM-DD`.

### `S205` — `generated.at` / `verified[].at` not ISO 8601 datetime

**Severity**: warning (configurable, `warn` by default via
`hygiene.okf_v02_shapes`) · **Out-of-spec**

Unlike `S102`'s date-only fields, `generated.at` and each `verified[].at`
must carry a full ISO 8601 datetime (a date alone does not qualify). `verified`
may be a bare mapping (see below) — its single entry is checked the same way.
Only fires on a base whose resolved `okf_version` is `"0.2"`.

```yaml
# ❌ S205
---
type: Reference
generated:
  by: "human:mdaviaud"
  at: "2026-01-01"
---

# ✅ fixed
---
type: Reference
generated:
  by: "human:mdaviaud"
  at: "2026-01-01T00:00:00Z"
---
```

**Fix**: use a full ISO 8601 datetime, not a bare date.

### `S206` — `generated.by` / `verified[].by` outside the actor convention

**Severity**: warning (configurable, `warn` by default via
`hygiene.okf_v02_shapes`) · **Out-of-spec**

`generated.by` and each `verified[].by` must follow one of the three actor
forms ([SPEC-002](../docs/specs/SPEC-002_okf-v0.2.md) §4):
`<producer>/<version>`, `human:<id>`, `process:<id>`. `okflint` never verifies
that the designated identity actually exists — only the shape. Only fires on
a base whose resolved `okf_version` is `"0.2"`.

```yaml
# ❌ S206
---
type: Reference
generated:
  by: matthieu
  at: "2026-01-01T00:00:00Z"
---

# ✅ fixed
---
type: Reference
generated:
  by: "human:matthieu"
  at: "2026-01-01T00:00:00Z"
---
```

**Fix**: prefix with `human:` or `process:`, or use `<producer>/<version>`.

### `S207` — `Attested Computation` contract shape

**Severity**: warning (configurable, `warn` by default via
`hygiene.okf_v02_shapes`) · **Out-of-spec**

On an `Attested Computation` concept ([SPEC-002](../docs/specs/SPEC-002_okf-v0.2.md)
§7 — beyond `runtime`, which is `F005`, core): `parameters`, if present,
should be a list of `{name, type, required}` entries; `executor`, if present,
should carry `resource` and `receipt`; `attester`, if present, should carry
`resource`; and the computation itself must be provided by **exactly one** of
a `computation` field or a `# Computation` body block — both present or
neither is flagged. `okflint` never requires the paths referenced (`computation`,
`executor.resource`, `attester.resource`) to resolve to an existing file. Only
fires on a base whose resolved `okf_version` is `"0.2"`.

```yaml
# ❌ S207: both a field and a body block
---
type: Attested Computation
runtime: dbt/1.8
computation: /computations/refresh.md
---
# Computation
...
```

**Fix**: pick one of `computation` or a `# Computation` block, complete
`executor`/`attester`/`parameters` per the contract shape above.

### `S208` — legacy OKF v0.1 forms

**Severity**: warning (configurable, `off` by default via
`hygiene.legacy_forms`) · **Out-of-spec**

Flags OKF v0.1 forms that v0.2 superseded ([SPEC-002](../docs/specs/SPEC-002_okf-v0.2.md)
§2): a `timestamp` field used instead of `generated.at`, and a `# Citations`
body heading used instead of the `sources` field. The `timestamp` check is
neutralised if `timestamp` is declared (`required` or `optional`) in the
concept's profile type — a producer may legitimately keep the field under a
different meaning. The `# Citations` check has no such override. Only fires
on a base whose **declared** `okf_version` is exactly `"0.2"` — unlike the
rest of the v0.2 shape family, this does *not* use the resolved version: a
base with no manifest, or no declared version, resolves to `"0.2"` but must
stay silent here, since it predates v0.2 support and never used these forms
on purpose.

```yaml
# ❌ S208
---
type: Reference
timestamp: "2026-01-01"
---
# Citations
- ...
```

```yaml
# ✅ fixed
---
type: Reference
generated:
  by: "human:matthieu"
  at: "2026-01-01T00:00:00Z"
sources:
  - resource: ...
---
```

**Fix**: replace `timestamp` with `generated.at`, replace a `# Citations`
list with the `sources` field.

### `S209` — stale content

**Severity**: warning (configurable, `off` by default via
`hygiene.stale_content`) · **Out-of-spec**

Flags a concept whose `stale_after` date has been reached or passed as of
the evaluation date ([SPEC-002](../docs/specs/SPEC-002_okf-v0.2.md) §6). The
evaluation date is recorded in the diagnostic message so the verdict stays
reproducible after the fact. Malformed `stale_after` values are left to
`S204`/`S102`, not re-reported here. Only fires on a base whose resolved
`okf_version` is `"0.2"`.

```yaml
# ❌ S209 (if evaluated on or after 2026-06-01)
---
type: Reference
stale_after: "2026-06-01"
---
```

**Fix**: refresh the content and move `stale_after` forward, or remove it if
the concept no longer needs a freshness bound.

---

## Quick reference

| Code | Stage | Severity | Summary |
| --- | --- | --- | --- |
| `F001` | OKF core | error | frontmatter absent/unparsable |
| `F002` | OKF core | error | `type` absent or empty |
| `F003` | OKF core | error | `generated` present without `generated.by` (v0.2) |
| `F004` | OKF core | error | `sources` entry without `resource` (v0.2) |
| `F005` | OKF core | error | `Attested Computation` without `runtime` (v0.2) |
| `R001` | OKF core | error | frontmatter forbidden in `index.md` |
| `R002` | OKF core | error | non-ISO date in `log.md` |
| `F101` | Profile | error | `type` not in declared types |
| `F102` | Profile | error | missing required field |
| `F105` | Profile | error | value outside controlled vocabulary |
| `F106` | Profile | error | non-normalised `type` spelling |
| `S102` | Profile | error | non-ISO date field |
| `L001` | Hygiene | warning | broken wikilink |
| `L002` | Hygiene | warning | broken markdown link |
| `L003` | Hygiene | warning | ambiguous wikilink |
| `S202` | Hygiene | warning | split candidate (semantic cohesion) |
| `R201` | Hygiene | warning | recommended reserved file missing |
| `F201` | Hygiene | warning | field outside declared schema |
| `S203` | Hygiene | warning | `status` outside draft\|stable\|deprecated (v0.2) |
| `S204` | Hygiene | warning | `stale_after` incorrectly formatted (v0.2) |
| `S205` | Hygiene | warning | `generated.at`/`verified[].at` not ISO datetime (v0.2) |
| `S206` | Hygiene | warning | `generated.by`/`verified[].by` outside actor convention (v0.2) |
| `S207` | Hygiene | warning | `Attested Computation` contract shape (v0.2) |
| `S208` | Hygiene | warning | legacy v0.1 forms: `timestamp`, `# Citations` (v0.2) |
| `S209` | Hygiene | warning | `stale_after` reached or passed (v0.2) |

---

## Conformance and exit code

- **`exit 0`**: no errors (core + profile). Hygiene warnings may still be present.
- **`exit 1`**: at least one OKF core or profile error.

A base is said to be **OKF-conformant** if it triggers no core errors
(`F001`, `F002`, `R001`, `R002`). It is **profile-conformant** if it additionally
triggers no profile errors. `okflint validate` requires both to return `exit 0`.

`okflint audit` applies these same checks in descriptive mode (`exit 0` always),
with the severities declared in the manifest. The difference with `validate` is
the exit code, not the checks.

`okflint index` generates `index.md` files that are always `R001`-conformant
(no frontmatter, except an optional hand-added `okf_version` at the bundle
root): it introduces no new rule, it only produces output that satisfies the
existing one.
