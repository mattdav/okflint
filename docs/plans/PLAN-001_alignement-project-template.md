---
type: Plan
id: PLAN-001
title: "Exécution de l'alignement d'okflint sur project_template"
description: "Sept étapes ordonnées, chacune commitée séparément, pour aligner okflint sur project_template puis le lier via cruft."
status: done
implements: SPEC-001
tags: [template, cruft, tooling, docs]
timestamp: 2026-08-28T09:31:00Z
perimeter: project
audience: [claude-code]
---

# PLAN-001 — Exécution de l'alignement d'okflint sur project_template

## Périmètre

Implémente [[SPEC-001_alignement-project-template]]. Sept sous-tâches indépendantes, exécutées dans
l'ordre ci-dessous car chacune dépend de l'état laissé par la précédente
(tooling avant CI, structure `.claude/`/`docs/` avant le manifeste qui la
documente, documentation avant la liaison cruft finale).

## Étapes

### 1. Tooling de lint

- Fichiers cibles : `.pre-commit-config.yaml`, config markdownlint/prettier
- Action : adopter le socle pre-commit + markdownlint + prettier du template
- Vérification : `uv run inv lint` passe
- Commit : `0f10ee6` — chore: adopt template lint tooling

### 2. Remplacement de `tasks.py`

- Fichiers cibles : `tasks.py`
- Action : adopter la version standard du template (lint via pre-commit,
  `precommit_install`, `build`)
- Vérification : `uv run inv --list` expose les mêmes tâches que le template
- Commit : `dd81e18` — chore: adopt template tasks.py

### 3. Consolidation CI

- Fichiers cibles : `.github/workflows/*.yml`
- Action : réduire 5 workflows à 3, lint délégué à pre-commit
- Vérification : CI GitHub Actions verte sur la branche
- Commit : `b212485` — ci: consolidate workflows into ci.yml

### 4. Restructuration `.claude/` et `docs/`

- Fichiers cibles : `.claude/**`, `CLAUDE.md`, `docs/specs/`, `docs/fixes/`,
  `docs/plans/`
- Action : déplacer `CLAUDE.md` à la racine, adopter le système
  documentaire Spec/Fix/Plan et les sous-dossiers `docs/` du template
- Vérification : arborescence conforme à celle du template
- Commit : `758af4b` — docs: align .claude/ tree and docs/ structure

### 5. Alignement du manifeste OKF

- Fichiers cibles : `manifest_okflint.yaml`
- Action : diff contre `manifest_project_template.yaml` — compléter
  `exclude_patterns`, resserrer les champs requis de `Spec`/`Fix`/`Plan`
  (`timestamp`, `perimeter`), ajouter les `status_values`/`severity_values` ;
  exclure délibérément `WikiPage` (aucun usage dans okflint, vérifié par
  grep)
- Vérification : `uv run okflint validate --manifest manifest_okflint.yaml .`
  sort en 0
- Commit : `0425261` — docs: align manifest_okflint.yaml profile types

### 6. Consolidation Sphinx

- Fichiers cibles : `docs/code/` (aplati depuis `docs/code/sphinx/`),
  `docs/code/conf.py`, `.gitignore`, `.github/workflows/docs.yml`,
  `tasks.py`
- Action : générer les pages API automatiquement via un hook
  `builder-inited` (source unique, `inv docs` n'appelle plus
  `sphinx-apidoc`) ; supprimer l'orphelin mort `docs/code/source/`
- Vérification : `uv run inv docs` passe avec `-W --keep-going`
- Commit : `4952df6` — docs: flatten docs/code/sphinx to docs/code

### 7. Liaison cruft

- Fichiers cibles : `.cruft.json`
- Action : `cruft link` vers `project_template` avec des surcharges de
  contexte reflétant l'identité réelle du projet (`_python_version: 3.12`
  au lieu du défaut `3.13` ; `use_wiki: no`, cohérent avec l'étape 5)
- Vérification : `uv run cruft check` est propre
- Commit : `d4d6381` — chore: link okflint to project_template via cruft

## Mise à jour documentaire

- [x] `README.md` — non impacté (aucun changement de surface publique)
- [x] Statut de [[SPEC-001_alignement-project-template]] passé à `implemented`
- [x] `.claude/progress.log` mis à jour (commit `df2fb32`)

## Vérification finale

Les cinq commandes ci-dessous passent simultanément avec les 7 commits en
place (`0f10ee6` → `d4d6381`) :

```bash
uv run inv lint
uv run inv test          # 276 passed, couverture 94 %
uv run inv docs
uv run okflint validate --manifest manifest_okflint.yaml .
uv run cruft check
```
