---
type: ProjectStandards
project: okflint
updated: 2026-08-27
tags: [python]
---

# Standard documentaire

Ce projet documente ses évolutions fonctionnelles avec trois types de
documents Markdown, stockés sous `docs/` (distinct de `docs/code/`, la
documentation technique générée par Sphinx depuis les docstrings).

## Les trois types

| Type | Dossier | Nommage | Rôle |
| --- | --- | --- | --- |
| Spec | `docs/specs/` | `SPEC-<id>_<nom>.md` | Besoin métier avant implémentation |
| Fix | `docs/fixes/` | `FIX-<id>_<nom>.md` | Dysfonctionnement, cause racine, résolution |
| Plan | `docs/plans/` | `PLAN-<id>_<nom>.md` | Mode opératoire d'implémentation d'une Spec ou d'un Fix |

Un Plan référence toujours la Spec ou le Fix qu'il implémente (champ
`implements` du frontmatter). Un Fix référence une Spec si le comportement
attendu en dépend.

## Frontmatter attendu

Chaque document démarre par un frontmatter YAML dont les champs varient
selon le type (`type`, `id`, `title`, `description`, `status`, `tags`,
`timestamp`, `perimeter`, `audience`, et des champs spécifiques : `severity`
et `work-item` pour un Fix, `implements` pour un Plan, `superseded-by` et
`work-item` pour une Spec). Le détail exact de chaque frontmatter est dans
le modèle correspondant.

## Modèles

Chaque nouveau document démarre depuis son modèle dans `docs/_templates/` :

- `docs/_templates/spec.md`
- `docs/_templates/fix.md`
- `docs/_templates/plan.md`

Ne pas réinventer la structure : copier le modèle, renseigner l'`id`, le
`timestamp` et laisser `status: draft` au départ. Les sections comme
`## Non-objectifs` ou `## Choix et contraintes` ne sont jamais laissées
vides — une décision ou un périmètre non écrit est perdu.

## Créer un document

Utiliser la commande `/doc-new` (`.claude/commands/doc-new.md`), qui choisit
le bon modèle, détermine le premier `id` libre dans le dossier cible et
pré-remplit `id`/`timestamp`/`status: draft` sans inventer le contenu des
autres sections.
