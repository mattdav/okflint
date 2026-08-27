---
type: Plan
id: PLAN-<featureID|fixID>
title: "<Ce qui est implémenté>"
description: "<Une phrase : le mode opératoire couvert>"
status: draft            # draft | active | done | deprecated
implements:              # SPEC-xxx ou FIX-xxx — obligatoire
tags: []
timestamp: <ISO 8601>
perimeter: project
audience: []
---

# <Titre>

## Périmètre

Ce que ce plan implémente, par référence à `implements`.

## Étapes

### 1. <Intitulé>

- Fichiers cibles : `chemin/en/slash.py`
- Action : ...
- Vérification : commande ou critère observable

### 2. <Intitulé>

## Mise à jour documentaire

- [ ] `README.md` du produit mis à jour si le fonctionnement change
- [ ] Statut du document `implements` passé à `implemented` / `fixed`

Cette étape n'est pas optionnelle : sans elle, le corpus de deltas
devient illisible en quelques mois.

## Vérification finale

Commandes ou contrôles attestant que le plan est complètement déroulé.
