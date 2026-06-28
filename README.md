---
type: ProjectDescription
project: okflint
updated: 2026-06-28
tags: [python, cli, linter, okf, open-source]
---

# okflint

**The Ruff of documentation.** A deterministic compliance linter for documentary
bases in [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
![Python](https://img.shields.io/badge/python-3.12+-3670A0?style=flat&logo=python&logoColor=ffdd54)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-blue)](https://mattdav.github.io/okflint/)

---

## Why

When a project's value migrates into its documentary base, that base must be held
to a standard — just as code is by a linter. `okflint` verifies, in a
**deterministic, reproducible, LLM-free** way, that Markdown documents conform to
an OKF standard declared in a YAML manifest.

Two commands:

- **`okflint audit`** — inventory and descriptive diagnostic of a base (statistics,
  broken links, split candidates). Always `exit 0`.
- **`okflint validate`** — normative compliance gate. `exit 0` if conformant,
  `exit 1` otherwise. Designed for pre-commit hooks and CI.

---

## Installation

```bash
# Via uv (recommended)
uv tool install okflint

# Or via pip
pip install okflint
```

For development:

```bash
git clone https://github.com/mattdav/okflint
cd okflint
uv sync --all-extras
uv pip install -e .
```

---

## Quick start

1. Copy the example manifest to the root of your documentary base:

```bash
cp okf-base.example.yaml /path/to/my-base/okf-base.yaml
```

2. Adapt it to your taxonomy (types, required fields, status vocabulary).

3. Validate:

```bash
okflint validate --manifest /path/to/my-base/okf-base.yaml /path/to/my-base
```

---

## The manifest

`okflint` is a **generic engine**: it knows no type vocabulary in hard code.
The `okf-base.yaml` manifest defines your standard. See
[`okf-base.example.yaml`](okf-base.example.yaml) for an annotated template.

Each type declares its required/optional fields and its status policy:

| `status_values` | Semantics |
|---|---|
| `[list]` | `status` field **required**, value constrained to the list |
| `false` | `status` field **forbidden** for this type |
| `null` (or absent) | `status` field **optional**, value free |

> **OKF resources** —
> [Official Google Cloud spec](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
> · [openknowledgeformat.com](https://openknowledgeformat.com/) (examples, templates, online validator)
> · [okf.md](https://okf.md/spec/) (annotated guide)

---

## Key concepts

| Term | Definition |
|---|---|
| **bundle** | A root folder of the documentary base to audit or validate. All `.md` files it contains (recursively) are analysed. Multiple bundles can be declared via `base.roots` in the manifest. |
| **vault** | The root folder(s) of all your Markdown (may be larger than the bundle). Used only to resolve `[[...]]` wikilinks. When using `--manifest`, all roots serve as the vault automatically. |
| **vault manifest** | An `okf-vault.json` file listing multiple bundles in a workspace. Passing it to `--vault` enables audit/validate across all bundles at once, with a shared union wikilink-resolution index. |
| **manifest** | The `okf-base.yaml` file you write to describe your standard: which concept types you use, which fields are required, which status vocabulary applies. Declares one or more roots via `base.roots`. See `okf-base.example.yaml` for an annotated template. |
| **target** | For `validate` only: one or more paths to folders or `.md` files to validate. If omitted, all roots declared in the manifest are validated. |

---

## Usage

### `okflint audit` — Inventory and diagnostic

`audit` scans one or more bundle roots and produces a descriptive report: OKF
conformance statistics, broken wikilinks, broken Markdown links, split candidates.
This command is **always exit 0** — it is an observation tool, not a gate.

```bash
# Multi-root scan from the manifest (recommended)
okflint audit --manifest /path/to/okf-base.yaml

# Write the full JSON report to .okflint/
okflint audit --manifest /path/to/okf-base.yaml --apply

# Single-root scan (legacy form, backward compatible)
okflint audit --bundle /path/to/my-base --vault /path/to/my-vault

# Manifest + --bundle as a sub-filter (scans only files under --bundle)
okflint audit --manifest /path/to/okf-base.yaml --bundle /path/to/sub-folder

# Audit every bundle in a vault manifest (union wikilink index)
okflint audit --vault /path/to/okf-vault.json
okflint audit --vault /path/to/okf-vault.json --apply
```

Either `--manifest`, both `--bundle` and `--vault` (folder), or `--vault` pointing to
an `okf-vault.json` file must be provided.

**Options:**

| Option | Required | Description |
|---|---|---|
| `--manifest <path>` | conditional | OKF manifest; `base.roots` defines the bundle and vault roots |
| `--bundle <path>` | conditional | Root folder to audit; acts as a sub-filter when `--manifest` is also set |
| `--vault <path>` | conditional | Vault folder for wikilink resolution, **or** an `okf-vault.json` file for multi-bundle mode |
| `--apply` | no | Writes the full JSON report to `.okflint/YYYY-MM-DD_audit_vN.json` |

When scanning multiple roots, the console output includes per-root file counts.
In vault JSON mode, each bundle is printed under its own `=== name ===` header,
followed by a `=== Total vault ===` aggregate.

**Concrete example — Obsidian vault:**
```bash
okflint audit \
  --bundle ~/Obsidian/My-project/docs \
  --vault ~/Obsidian \
  --apply
# Produces: .okflint/2026-06-28_audit_v1.json
```

**Concrete example — multi-root from manifest:**
```bash
okflint audit --manifest ./okf-base.yaml --apply
```

**Concrete example — multi-bundle workspace:**
```bash
# okf-vault.json lists several bundles, each with its own okf-base.yaml
okflint audit --vault ./okf-vault.json --apply
# Produces: .okflint/2026-06-28_vault_audit_v1.json
```

**`okf-vault.json` format:**
```json
{
  "okf_vault_version": "0.1",
  "name": "my-workspace",
  "bundles": [
    { "path": "projects/alpha" },
    { "path": "projects/beta", "manifest": "okf-base.yaml" }
  ]
}
```

Each bundle entry requires a `path` field (absolute or relative to the vault file).
The optional `manifest` field names the manifest file inside the bundle directory
(defaults to `okf-base.yaml`).

---

### `okflint validate` — Compliance gate

`validate` checks the conformance of Markdown files to OKF and to the profile
declared in your manifest. Returns **exit 0** if no errors, **exit 1** otherwise.
Designed for pre-commit hooks and CI.

```bash
# Validate all roots declared in the manifest (no explicit targets)
okflint validate --manifest okf-base.yaml

# Validate an entire base
okflint validate --manifest okf-base.yaml /path/to/my-base

# Validate a single sub-folder
okflint validate --manifest okf-base.yaml /path/to/my-base/ADR

# Validate specific files
okflint validate --manifest okf-base.yaml concept1.md concept2.md

# Machine-readable JSON output (for CI, scripts)
okflint validate --manifest okf-base.yaml --json /path/to/my-base

# Validate every bundle in a vault (each bundle uses its own manifest)
okflint validate --vault /path/to/okf-vault.json

# Validate with a specific manifest but use the vault's union index
okflint validate --vault /path/to/okf-vault.json --manifest /path/to/okf-base.yaml
```

**Options:**

| Option | Required | Default | Description |
|---|---|---|---|
| `--manifest <path>` | no | `okf-base.yaml` | Path to the OKF manifest |
| `--vault <path>` | no | — | `okf-vault.json` file: without `--manifest` validates each bundle with its own manifest; with `--manifest` uses the vault union index |
| `--json` | no | — | JSON output instead of human-readable text |
| `<targets...>` | no | all manifest roots | One or more paths (folders or `.md` files) to validate |

**Exit codes:**

| Code | Meaning |
|---|---|
| `0` | No errors (warnings may still be present) |
| `1` | At least one conformance error |
| `2` | Invalid or unreadable manifest / vault config error |

In vault JSON mode without `--manifest`, errors are prefixed with `[bundle_name]`
and the exit code is the maximum across all bundles.

**Concrete example — CI GitHub Actions integration:**
```yaml
- name: Validate docs
  run: |
    pip install okflint
    okflint validate --manifest docs/okf-base.yaml docs/
```

**Concrete example — git pre-commit hook:**
```bash
# .git/hooks/pre-commit
okflint validate --manifest okf-base.yaml docs/ || exit 1
```

---

## Development

```bash
inv lint     # ruff + mypy
inv clean    # clean build artefacts
inv repomix  # pack the codebase for an LLM
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide,
the release process, and commit conventions.

The **full API documentation** (generated from docstrings) is available at
[mattdav.github.io/okflint](https://mattdav.github.io/okflint/).

---

## Architecture

```
src/okflint/
├── cli.py        ← dispatcher: okflint audit | validate
├── scanner.py    ← shared primitives (scan, frontmatter, links)
├── audit.py      ← audit command (descriptive)
├── validate.py   ← validate command (normative gate)
├── vault.py      ← okf-vault.json loading (VaultConfig, load_vault)
└── __main__.py   ← python -m okflint
```

Bundle manifest: `manifest.py` (contract loading + validation).

---

## Roadmap

Envisioned evolutions beyond v0.1 (semantic cohesion for finer splitting,
verifiable reading-grid expectations) are described in [ROADMAP.md](ROADMAP.md).

---

## What okflint does not do

okflint is a **static, deterministic gate**. By design, it will never:

- **Execute a reading traversal** for an agent — that is the harness's role.
- **Judge the content** of a concept via LLM (summarise, classify, rewrite).
- **Decide** on a split or reorganisation — it signals, it does not rule.
- **Impose a convention** not declared by your manifest — no hardcoded vocabulary,
  no imposed language.

---

## License

[MIT](LICENSE) — [@mattdav](https://github.com/mattdav)
