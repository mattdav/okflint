---
type: Spec
id: SPEC-<featureID>
title: "<Titre fonctionnel de la feature>"
description: "<Une phrase : ce que la feature apporte au métier>"
status: draft            # draft | accepted | implemented | superseded
superseded-by:           # SPEC-xxx si remplacée, sinon vide
work-item:               # ID du work item Azure DevOps
tags: []
timestamp: <ISO 8601>
perimeter: project
audience: []
---

# <Titre>

## Objectif

Le besoin métier en 3 à 5 lignes. Pourquoi cette feature existe,
quel problème elle résout, pour qui.

## Périmètre

### Inclus

- ...

### Non-objectifs

Ce que la feature ne couvre volontairement pas. Deux lignes suffisent,
mais cette section n'est jamais vide : c'est elle qui évite les malentendus
de périmètre en recette.

## Spécification fonctionnelle

Règles de gestion, sources de données, grain, indicateurs, restitution attendue.
Vocabulaire RFC 2119 : DOIT / DEVRAIT / PEUT, pour lever l'ambiguïté sur le
caractère obligatoire de chaque règle.

## Choix et contraintes

Trois lignes maximum. Les décisions structurantes et leur raison, même
triviale. Réponses acceptables : « outil déjà maîtrisé par l'équipe »,
« contrainte de licence », « cohérence avec le flux X ».
Ne pas laisser vide : une décision non écrite est une décision perdue.

## Critères d'acceptation

- [ ] ...
Formulés de manière vérifiable (une personne tierce doit pouvoir statuer).
