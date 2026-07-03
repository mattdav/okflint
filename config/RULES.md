---
type: ProjectStandards
project: okflint
updated: 2026-06-28
tags: [lint, rules]
---


# okflint rules

`okflint` verifies that a documentary base conforms to [OKF v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md) **and** to the framework the base has itself declared in its manifest.

This document lists all check points, their code, their severity, and how to fix each case.

---

## Philosophy: three stages

OKF is deliberately minimal — its conformance clause (§9) imposes only three
rules. But the spec explicitly invites each producer to refine their framework
beyond that (« anything beyond that is left to the producer »). `okflint`
materialises this invitation as three stages of distinct authority:

| Stage | Authority | Output prefix | Severity | Exit code effect |
|---|---|---|---|---|
| **OKF core** | OKF v0.1 spec §9 (universal, non-negotiable) | `OKF non-conformant` | error | `exit 1` |
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

---

## Stage 1 — OKF core

Always active. Hardcoded. Corresponds word-for-word to the OKF v0.1 conformance
clause (§9) and to the structural constraints of reserved files (§6, §7, §11).

### `F001` — Frontmatter absent or unparsable

**Severity**: error · **Source**: OKF §9.1

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

**Severity**: error · **Source**: OKF §9.2

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

### `R001` — Frontmatter forbidden in `index.md`

**Severity**: error · **Source**: OKF §6, §11

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

**Severity**: error · **Source**: OKF §7

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
**your** framework: your types, your fields, your status vocabulary.
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

### `F103` — Status present but forbidden

**Severity**: error

When a type declares `status_values: false`, the status field must not exist
on its concepts (e.g. a dated journal entry has no status).

**Fix**: remove the status field from the concept.

### `F104` — Required status missing

**Severity**: error

When a type declares `status_values: [list]`, the status field is required.

**Fix**: add the status field with a value from the list.

### `F105` — Status value outside vocabulary

**Severity**: error

The value of the status field must belong to the list declared for that type.

```yaml
# profile.types.Procedure.status_values = [draft, prod, obsolete]
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

**Fix**: replace the spelling with the type's canonical name. Auto-fixable
(see `okflint fix`, coming soon).

### `S101` — Incorrectly named status field

**Severity**: error

The status field must use the name declared in `base.status_field`. For
example, if a base declared `status_field: "status"`, a concept using
`statut` instead of `status` is a contract deviation.

**Fix**: rename the field to the declared name. Auto-fixable.

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

**Fix**: reformat the date as `YYYY-MM-DD`. Auto-fixable.

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

### `S201` — Split candidate

**Severity**: warning (configurable) · **Out-of-spec**

A file containing multiple distinct concepts (multiple `# H1`, or a homogeneous
list of `## H2` describing separable entities). A signal, never an obligation:
splitting remains an editorial choice.

**Fix**: consider splitting the file into multiple concepts, or ignore if the
cohesion justifies keeping it together.

### `R201` — Recommended reserved file missing

**Severity**: warning (configurable, `off` by default) · **Out-of-spec**

An `index.md` or `log.md` is missing at a root's directory level. OKF makes
these files **optional** (§3) and explicitly forbids rejecting a base for their
absence (§9). `okflint` only flags them on request, for producers who adopt an
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

---

## Quick reference

| Code | Stage | Severity | Summary |
|---|---|---|---|
| `F001` | OKF core | error | frontmatter absent/unparsable |
| `F002` | OKF core | error | `type` absent or empty |
| `R001` | OKF core | error | frontmatter forbidden in `index.md` |
| `R002` | OKF core | error | non-ISO date in `log.md` |
| `F101` | Profile | error | `type` not in declared types |
| `F102` | Profile | error | missing required field |
| `F103` | Profile | error | status present but forbidden |
| `F104` | Profile | error | required status missing |
| `F105` | Profile | error | status value outside vocabulary |
| `F106` | Profile | error | non-normalised `type` spelling |
| `S101` | Profile | error | incorrectly named status field |
| `S102` | Profile | error | non-ISO date field |
| `L001` | Hygiene | warning | broken wikilink |
| `L002` | Hygiene | warning | broken markdown link |
| `L003` | Hygiene | warning | ambiguous wikilink |
| `S201` | Hygiene | warning | split candidate |
| `R201` | Hygiene | warning | recommended reserved file missing |
| `F201` | Hygiene | warning | field outside declared schema |

---

## Conformance and exit code

- **`exit 0`**: no errors (core + profile). Hygiene warnings may still be present.
- **`exit 1`**: at least one OKF core or profile error.

A base is said to be **OKF-conformant** if it triggers no core errors
(`F001`, `F002`, `R001`, `R002`). It is **profile-conformant** if it additionally
triggers no profile errors. `okflint validate` requires both to return `exit 0`.
