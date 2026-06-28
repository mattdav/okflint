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
