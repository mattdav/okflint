---
type: Fix
id: FIX-001
title: "Rapport d'audit vide et faussement vert quand --manifest et --bundle sont combinés"
description: "okflint audit --manifest ... --bundle <chemin relatif> scanne 0 fichier et rend un rapport vert sans erreur ni exit code non-zéro."
status: fixed
severity: major
work-item:
tags: [audit, cli, bundle, manifest, exit-code]
timestamp: 2026-08-29T00:00:00Z
perimeter: project
audience: [claude-code]
---

# FIX-001 — Rapport d'audit vide et faussement vert quand `--manifest` et `--bundle` sont combinés

## Symptôme

```text
$ uv run okflint audit --bundle . --vault . --manifest manifest_okflint.yaml
Warning: Both --manifest and --bundle provided; --bundle used as target filter over manifest roots.
📦 Scanning bundle: 1 root
0 files found
Diagnostics: 0 errors, 0 warnings (core=0/profile=0/hygiene=0)
```

La même commande sans `--bundle` scanne 22 fichiers. Avec `--bundle .`, elle en
rend 0, sans aucune erreur ni exit code non-zéro : le rapport est vert alors que
la base n'a pas été examinée.

## Reproduction

Base avec un manifeste déclarant `roots: [{path: "."}]` (racine relative au
manifeste), exécutée depuis le répertoire courant :

```bash
okflint audit --manifest manifest_okflint.yaml --bundle .
```

`--bundle ./docs`, ou tout autre chemin relatif, reproduit le même défaut.

## Comportement attendu

Filtrer une racine « `.` » avec `--bundle .` doit rendre l'intégralité de la
base couverte par cette racine (22 fichiers dans le cas de `manifest_okflint.yaml`),
au même titre qu'un `--bundle` en chemin absolu équivalent.

Un `--bundle` qui ne recoupe aucune racine du manifeste ne doit jamais produire
un rapport vert : c'est une erreur de configuration, pas un résultat valide.

## Analyse

Dans `cli.py`, le filtre `--bundle` est construit sans jamais être résolu :

```python
target_filter = Path(args.bundle)          # jamais .resolve()
target_filter_orig = Path(args.bundle)     # même défaut, branche parallèle
```

Il est ensuite comparé à des `md_file` toujours absolus (`audit.py:264`,
`md_file.is_relative_to(target_filter)`), car les racines du manifeste sont
résolues en chemin absolu au chargement (`manifest.py:385`).
`Path.is_relative_to()` renvoie `False` dès que les ancres des deux chemins
diffèrent (absolu vs relatif), indépendamment de toute inclusion réelle :
un filtre relatif ne peut donc jamais matcher une racine absolue, quel que
soit son contenu littéral.

Le correctif suit une convention déjà établie ailleurs dans la codebase
(`validate.py:1263`, `vault.py:107` : résoudre avant de comparer).

**Périmètre exact du défaut** (vérifié dans le code, pas supposé) :

| Cas | Avant correctif |
| --- | --- |
| `--manifest` + `--bundle .` | Cassé — 0 fichier, exit 0 |
| `--manifest` + `--bundle ./docs` (tout chemin relatif) | Cassé — même mécanisme |
| `--manifest` + `--bundle <chemin absolu>` | Déjà correct |
| `--bundle` + `--vault` sans `--manifest` | Non affecté (pas de filtre appliqué) |
| `--bundle` (même absolu) hors de toute racine | Déjà 0 fichier / exit 0 — défaut distinct, additionnel |
| Multi-root, `--bundle` absolu sur une seule racine | Déjà correct |
| `validate` | N'accepte pas `--bundle` — non concerné par ce défaut |

`scanner.py` ne contient aucune logique de normalisation liée à ce filtre
(uniquement la résolution des wikilinks).

## Impact

Toute base utilisant un manifeste avec `--bundle` en chemin relatif produit un
audit silencieusement vide et vert. Risque direct : un pipeline CI qui se fie à
l'exit code 0 d'`okflint audit` croit la base conforme alors qu'elle n'a pas
été scannée.

## Résolution

Deux correctifs, indépendants et complémentaires :

1. **Normalisation** — `target_filter`/`target_filter_orig` sont résolus en
   chemin absolu (`Path(args.bundle).resolve()`) dans `cli.py`, avant d'être
   comparés aux racines (déjà absolues) dans `run_audit`.
2. **Garde-fou** — `run_audit` lève désormais `AuditError` (nouvelle exception
   dans `audit.py`) quand un `target_filter` est fourni mais ne recoupe aucune
   racine (0 fichier trouvé). `cli.py` intercepte `AuditError` dans les deux
   branches (`audit --vault <json>` et `audit --vault <dossier>`) et rend un
   exit code 2 avec un message explicite, au lieu d'un rapport vert.

Le warning existant (« Both --manifest and --bundle provided ») est conservé
inchangé.

`validate` n'accepte pas `--bundle` et ne partage pas ce chemin de code — non
concerné, aucun changement.

Tests : `tests/test_audit.py::TestRunAuditExclude::test_target_filter_no_overlap_raises_audit_error`
et `tests/test_cli.py::TestCmdAuditBundleFilterNormalization` (5 scénarios :
`--bundle .` plein périmètre, sous-dossier relatif, équivalence
relatif/absolu, hors-racine → exit 2, multi-root avec filtre relatif).
