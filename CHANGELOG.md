---
type: ProjectLifeCycle
project: okflint
status: active
updated: 2026-06-28
tags: [python, cli, linter, okf, open-source]
---

# Changelog

All notable changes to okflint are documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning: [Semantic Versioning](https://semver.org/).

This file is maintained automatically by [commitizen](https://commitizen-tools.github.io/commitizen/).
Do not manually edit the generated sections.

---

## v0.3.1 (2026-07-20)

### Fix

- **audit**: exempter les fichiers réservés de F001 en mode sans manifeste
- **validate**: normaliser les targets CLI en chemins absolus
- déclarer beartype en dépendance runtime

## v0.3.0 (2026-07-08)

### BREAKING CHANGE

- the S201 rule is removed. The split_candidates hygiene key is
retained but now backs S202 with different (semantic) semantics. Bases relying
on S201's structural detection will see different split diagnostics.

### Feat

- **rules**: replace S201 with S202 semantic-cohesion split candidate

### Fix

- **release**: make `inv release --dry-run` faithfully preview the bump
- **ci**: update sphinx source path to docs/code/sphinx after docs reorg

## v0.2.0 (2026-07-04)

### BREAKING CHANGE

- manifest schema changed. `base.status_field` removed; per-type
`status_values` replaced by a generic `<prop>_values` on any declared property.
Rules F103/F104/S101 removed (catalogue 18→15). Migration: drop `status_field`,
rename `status_values` to `<statuskey>_values`, and remove `type` from `required`
lists (now implicit, controlled by F002/F101).

### Feat

- **index**: add `okflint index` command (OKF §6 index.md generation, dry-run default)
- **audit**: align audit checks with validate (descriptive, exit 0)
- **manifest**: modèle de vocabulaire contrôlé générique via suffixe _values

### Fix

- **scanner**: strip URL fragment before markdown link resolution
- **docs**: corrige les liens cassés après la réorganisation documentaire

## v0.1.3 (2026-06-28)

### Feat

- ajout de exclude_patterns par racine dans le manifeste (Track F)
- ajoute le support des vault manifests (okf-vault.json) — Track E

### Fix

- résout les roots du manifeste relativement au fichier manifeste

## v0.1.2 (2026-06-28)

### Feat

- scan multi-root via manifest (Track D) + fix inv index sur Windows

## v0.1.1 (2026-06-27)

### Fix

- **docs**: add .nojekyll for GitHub Pages, fix _static serving
- fix codebase-memory-mcp index cmd, add docs link to README

## v0.1.0 (2026-06-27)

### New features

- Unified CLI `okflint audit | validate`
- 3-stage validation: OKF core (§9), profile (manifest), hygiene (opt-in)
- 18 rules catalogued in `config/RULES.md`
- Generic engine driven by a YAML manifest (`okf-base.yaml`)
- Manifest self-validation (`manifest.py`)
- Obsidian wikilinks support (audit + link resolution)
- 93% test coverage
- Auto-generated Sphinx documentation
