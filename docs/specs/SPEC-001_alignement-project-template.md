---
type: Spec
id: SPEC-001
title: "Alignement d'okflint sur project_template"
description: "Amener le tooling et la structure d'okflint au standard défini par project_template, puis le lier via cruft pour recevoir ses futures évolutions."
status: implemented
superseded-by:
work-item:
tags: [template, cruft, tooling, docs]
timestamp: 2026-08-28T09:31:00Z
perimeter: project
audience: [claude-code]
---

# SPEC-001 — Alignement d'okflint sur project_template

## Objectif

okflint est un paquet PyPI publié, avec des utilisateurs réels et une CI de
release fonctionnelle (Trusted Publisher + garde-fou `smoke-install`). Il a
été créé avant la refonte de `project_template` et n'a jamais été lié à lui
(pas de `.cruft.json`). Le besoin métier est de faire converger son tooling
(lint, tâches invoke, CI, structure `.claude/`, documentation) vers le
standard actuel du template, puis de le lier formellement via `cruft` pour
que ses évolutions futures puissent être tirées automatiquement (`cruft
update`), sans jamais devoir réaligner l'ensemble à la main.

## Périmètre

### Inclus

- Tooling de lint (pre-commit, markdownlint, prettier).
- `tasks.py` (remplacement par la version standard du template).
- Consolidation des workflows CI (5 → 3).
- Restructuration de l'arborescence `.claude/` et `docs/` (système
  documentaire Spec/Fix/Plan, déplacement de `CLAUDE.md` à la racine).
- Alignement de `manifest_okflint.yaml` sur `manifest_project_template.yaml`
  (types de profil, champs requis, valeurs de statut).
- Consolidation de la documentation Sphinx (`docs/code/`, génération
  automatique des pages API).
- Liaison du dépôt au template via `cruft link`.

### Non-objectifs

Cette spec ne couvre pas la logique métier d'okflint (`src/okflint/**`), ni
un changement de version ou de release. Elle ne couvre pas non plus
l'exemple de manifeste (`example/manifest.example.yaml`,
`example/ok-vault.example.json`), qui reste hors périmètre du template.

## Spécification fonctionnelle

- L'alignement DOIT préserver la chaîne de publication PyPI et le job
  `smoke-install` : aucune étape ne DOIT casser la CI de release.
- La surface publique (README, liens de `config/RULES.md`, GitHub Pages,
  entrée dans le listing "okf.md") DOIT rester valide après chaque étape.
- Le hook pre-commit qu'okflint fournit à project_template DOIT continuer
  à invoquer l'installation locale éditable (`uv run okflint validate ...`)
  et NE DOIT PAS être remplacé par `uvx okflint`, car okflint est le seul
  projet à devoir dogfooder sa propre version de développement.
- Chaque élément importé du template DEVRAIT être vérifié empiriquement
  contre l'usage réel d'okflint avant import (ex. exclusion du type
  `WikiPage`, absent de toute fonctionnalité d'okflint).
- Le contexte `cruft` (`.cruft.json`) DOIT refléter l'identité réelle du
  projet (version Python, options activées) plutôt que les valeurs par
  défaut du template, pour que les futurs `cruft update` calculent des
  diffs corrects.

## Choix et contraintes

Découpage en 7 sous-tâches indépendantes, chacune commitée séparément en
anglais (format commitizen), pour permettre une revue et un rollback
granulaires. Le type `WikiPage` du template n'est pas importé : okflint n'a
aucune fonctionnalité wiki/ingestion. La documentation Sphinx bascule vers
une génération API automatique (hook `builder-inited`) plutôt que des
pages `.rst` manuscrites, pour garantir qu'aucun build CI ne publie une
documentation amputée.

## Critères d'acceptation

- [x] `uv run inv lint` passe à zéro.
- [x] `uv run inv test` passe avec une couverture ≥ 93 %.
- [x] `uv run inv docs` passe avec `-W --keep-going`.
- [x] `uv run okflint validate --manifest manifest_okflint.yaml .` sort en 0.
- [x] `uv run cruft check` est propre.
- [x] Un commit par sous-tâche, message en anglais, format commitizen.
- [x] `.claude/progress.log` mis à jour en fin de mission.
