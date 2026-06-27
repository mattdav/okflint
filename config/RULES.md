# Règles okflint

`okflint` vérifie qu'une base documentaire est conforme à
[OKF v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
**et** au cadre que cette base s'est elle-même donné dans son manifeste.

Ce document liste tous les points de contrôle, leur code, leur sévérité, et
comment corriger chaque cas.

---

## Philosophie : trois étages

OKF est délibérément minimal — sa clause de conformité (§9) n'impose que trois
règles. Mais la spec invite explicitement chaque producteur à affiner son cadre
au-delà (« anything beyond that is left to the producer »). `okflint` matérialise
cette invitation en trois étages d'autorité distincte :

| Étage | Autorité | Préfixe sortie | Sévérité | Effet exit code |
|---|---|---|---|---|
| **Cœur OKF** | la spec OKF v0.1 §9 (universel, non négociable) | `OKF non-conforme` | erreur | `exit 1` |
| **Profil** | le manifeste que *vous* avez déclaré | `Profil non respecté` | erreur | `exit 1` |
| **Hygiène** | plus strict qu'OKF (opt-in) | `hygiène (hors-spec)` | avertissement | `exit 0` |

Le point essentiel : violer **la spec** et violer **votre contrat déclaré** sont
deux choses différentes. Au sens strict d'OKF, une base qui déclare un manifeste
mais ne le respecte pas reste *littéralement* parsable — mais elle trahit l'esprit
OKF (une base auto-descriptive doit tenir ses propres promesses). `okflint`
signale les deux, en les nommant distinctement.

Le cœur est codé en dur. Le profil et l'hygiène ne se déclenchent que si votre
manifeste les déclare : une base minimale (manifeste réduit au strict nécessaire)
ne sera contrôlée que sur le cœur OKF.

---

## Étage 1 — Cœur OKF

Toujours actif. Codé en dur. Correspond mot pour mot à la clause de conformité
OKF v0.1 (§9) et aux contraintes structurelles des fichiers réservés (§6, §7, §11).

### `F001` — Frontmatter absent ou non parsable

**Sévérité** : erreur · **Source** : OKF §9.1

Tout fichier `.md` non réservé doit commencer par un bloc de frontmatter YAML
délimité par `---`, et ce bloc doit être parsable.

```markdown
<!-- ❌ F001 : pas de frontmatter -->
# Mon concept
...

<!-- ✅ corrigé -->
---
type: Reference
---

# Mon concept
...
```

**Correction** : ajouter un bloc frontmatter valide en tête de fichier.

### `F002` — Champ `type` absent ou vide

**Sévérité** : erreur · **Source** : OKF §9.2

Le frontmatter doit contenir un champ `type` non vide. C'est le **seul** champ
qu'OKF rend obligatoire.

```yaml
# ❌ F002 : type manquant
---
title: Mon concept
---

# ✅ corrigé
---
type: Reference
title: Mon concept
---
```

**Correction** : renseigner un `type` descriptif. OKF n'impose aucune valeur
particulière ; si un profil est déclaré, voir `F101`.

### `R001` — Frontmatter interdit dans un `index.md`

**Sévérité** : erreur · **Source** : OKF §6, §11

Un `index.md` ne contient pas de frontmatter, à une seule exception : l'`index.md`
de la racine du bundle peut porter `okf_version` (et rien d'autre).

```yaml
# ❌ R001 : frontmatter complet dans un index.md
---
type: Reference
tags: [accueil]
---

# ✅ autorisé uniquement à la racine du bundle
---
okf_version: "0.1"
---
```

**Correction** : retirer le frontmatter de l'`index.md`, ou le réduire à
`okf_version` s'il s'agit de l'index racine.

### `R002` — Heading de date non ISO dans un `log.md`

**Sévérité** : erreur · **Source** : OKF §7

Dans un `log.md`, les titres de date doivent être au format ISO 8601
`YYYY-MM-DD`.

```markdown
<!-- ❌ R002 -->
## 22 mai 2026

<!-- ✅ corrigé -->
## 2026-05-22
```

**Correction** : reformater les headings de date en `YYYY-MM-DD`.

---

## Étage 2 — Profil

Ne se déclenchent que si le manifeste déclare un bloc `profile`. Ces règles
encodent **votre** cadre : vos types, vos champs, votre vocabulaire de statut.
Elles ne sont pas OKF au sens strict — elles sont l'affinement contractuel que
vous avez choisi, et qu'`okflint` vous aide à tenir.

### `F101` — Valeur `type` hors des types déclarés

**Sévérité** : erreur

Le `type` d'un concept doit faire partie des types déclarés dans
`profile.types`. (Ne se déclenche que si le profil déclare une liste de types.)

**Correction** : utiliser un type déclaré, ou ajouter le type au manifeste s'il
est légitime.

### `F102` — Champ requis manquant

**Sévérité** : erreur

Chaque type déclare ses champs `required`. Un concept de ce type doit les porter
tous.

```yaml
# profile.types.Decision.required = [type, statut, created]
# ❌ F102 : created manquant
---
type: Decision
statut: Accepté
---
```

**Correction** : ajouter le champ manquant.

### `F103` — Statut présent mais interdit

**Sévérité** : erreur

Quand un type déclare `status_values: false`, le champ de statut ne doit pas
exister sur ses concepts (ex. une entrée de journal datée n'a pas de statut).

**Correction** : retirer le champ de statut du concept.

### `F104` — Statut requis manquant

**Sévérité** : erreur

Quand un type déclare `status_values: [liste]`, le champ de statut est requis.

**Correction** : ajouter le champ de statut avec une valeur de la liste.

### `F105` — Valeur de statut hors vocabulaire

**Sévérité** : erreur

La valeur du champ de statut doit appartenir à la liste déclarée pour ce type.

```yaml
# profile.types.Procedure.status_values = [draft, prod, obsolète]
# ❌ F105
---
type: Procedure
statut: en-cours
---
```

**Correction** : utiliser une valeur déclarée, ou étendre le vocabulaire dans le
manifeste.

### `F106` — Casse ou graphie du `type` non normalisée

**Sévérité** : erreur

Si un type déclare des `aliases`, une graphie alternative est tolérée à la
lecture mais signalée pour normalisation (ex. `adr` → `Decision`).

**Correction** : remplacer la graphie par le nom canonique du type. Corrigeable
automatiquement (voir `okflint fix`, à venir).

### `S101` — Champ de statut mal nommé

**Sévérité** : erreur

Le champ de statut doit porter le nom déclaré dans `base.status_field`. Par
exemple, si une base a déclaré `status_field: "statut"`, un concept qui utilise
`status` au lieu de `statut` est un écart au contrat.

**Correction** : renommer le champ vers le nom déclaré. Corrigeable
automatiquement.

### `S102` — Champ de date non ISO

**Sévérité** : erreur

Les champs listés dans `profile.date_fields` doivent être au format ISO
`YYYY-MM-DD` quand ils sont présents.

```yaml
# profile.date_fields = [created, updated]
# ❌ S102
---
type: Decision
created: 2026-5-1
---

# ✅ corrigé
created: 2026-05-01
```

**Correction** : reformater la date en `YYYY-MM-DD`. Corrigeable
automatiquement.

---

## Étage 3 — Hygiène

Plus strict qu'OKF. OKF demande explicitement aux consommateurs de **tolérer**
ces cas (« Consumers MUST tolerate broken links »). `okflint` les signale quand
même, parce qu'une base soignée gagne à les corriger — mais en **avertissement**,
jamais en erreur, et toujours étiquetés comme hors-spec. Activables/désactivables
via le bloc `hygiene` du manifeste (`off` | `warn` | `error`).

### `L001` — Wikilink cassé

**Sévérité** : avertissement (configurable) · **Hors-spec**

Un wikilink `[[Cible]]` dont la cible n'existe pas dans la base. Note : les
wikilinks sont une convention Obsidian, pas OKF (qui utilise les liens markdown).

**Correction** : corriger la cible, ou déclarer la référence dans
`base.link_resolution.external_refs` si elle est hors-base et assumée.

### `L002` — Lien markdown cassé

**Sévérité** : avertissement (configurable) · **Hors-spec**

Un lien `[texte](/chemin.md)` dont la cible n'existe pas dans la base.

**Correction** : corriger le chemin de destination.

### `L003` — Wikilink ambigu

**Sévérité** : avertissement (configurable) · **Hors-spec**

Un wikilink `[[Cible]]` qui résout vers plusieurs fichiers de la base (même nom
dans des dossiers différents).

**Correction** : préciser le chemin, ou désambiguïser les noms de fichiers.

### `S201` — Candidat au découpage

**Sévérité** : avertissement (configurable) · **Hors-spec**

Un fichier qui contient plusieurs concepts distincts (plusieurs `# H1`, ou une
liste homogène de `## H2` décrivant des entités séparables). Signal, jamais
obligation : un découpage reste un choix éditorial.

**Correction** : envisager d'éclater le fichier en plusieurs concepts, ou ignorer
si la cohésion justifie le maintien.

### `R201` — Fichier réservé recommandé absent

**Sévérité** : avertissement (configurable, `off` par défaut) · **Hors-spec**

Un `index.md` ou un `log.md` est absent à la racine d'un root. OKF rend ces
fichiers **optionnels** (§3) et interdit explicitement de rejeter une base pour
leur absence (§9). `okflint` ne les signale donc que sur demande, pour les
producteurs qui adoptent une convention interne de progressive disclosure (un
`index.md` par dossier).

> ⚠️ À ne pas confondre avec `R001`/`R002` (cœur OKF) : ceux-là vérifient la
> **structure** des fichiers réservés *quand ils existent* ; `R201` ne concerne
> que leur **présence**, qui reste optionnelle au sens d'OKF.

**Correction** : ajouter un `index.md` / `log.md`, ou laisser `reserved_files: off`
dans le manifeste si l'absence est assumée.

### `F201` — Champ de frontmatter hors du schéma déclaré

**Sévérité** : avertissement (configurable, `off` par défaut) · **Hors-spec**

Un concept porte un champ de frontmatter absent de `required ∪ optional` pour son
type. OKF autorise explicitement les champs additionnels (§4.1 : *« Producers MAY
include any additional keys »*) et interdit de rejeter pour ça — donc jamais une
erreur. Mais en avertissement, la règle attrape les coquilles (`tag:` au lieu de
`tags:`) et la dérive silencieuse du schéma. Ne se déclenche que si un profil
déclare le type concerné.

**Correction** : corriger le nom du champ, l'ajouter à `optional` dans le manifeste
s'il est légitime, ou laisser `unknown_fields: off` si la base assume des champs
libres.

---

## Référence rapide

| Code | Étage | Sévérité | Résumé |
|---|---|---|---|
| `F001` | Cœur OKF | erreur | frontmatter absent/non parsable |
| `F002` | Cœur OKF | erreur | `type` absent ou vide |
| `R001` | Cœur OKF | erreur | frontmatter interdit dans `index.md` |
| `R002` | Cœur OKF | erreur | date non ISO dans `log.md` |
| `F101` | Profil | erreur | `type` hors des types déclarés |
| `F102` | Profil | erreur | champ requis manquant |
| `F103` | Profil | erreur | statut présent mais interdit |
| `F104` | Profil | erreur | statut requis manquant |
| `F105` | Profil | erreur | valeur de statut hors vocabulaire |
| `F106` | Profil | erreur | graphie de `type` non normalisée |
| `S101` | Profil | erreur | champ de statut mal nommé |
| `S102` | Profil | erreur | champ de date non ISO |
| `L001` | Hygiène | warning | wikilink cassé |
| `L002` | Hygiène | warning | lien markdown cassé |
| `L003` | Hygiène | warning | wikilink ambigu |
| `S201` | Hygiène | warning | candidat au découpage |
| `R201` | Hygiène | warning | fichier réservé recommandé absent |
| `F201` | Hygiène | warning | champ hors du schéma déclaré |

---

## Conformité et code de sortie

- **`exit 0`** : aucune erreur (cœur + profil). Des avertissements d'hygiène
  peuvent subsister.
- **`exit 1`** : au moins une erreur de cœur OKF ou de profil.

Une base est dite **OKF-conforme** si elle ne déclenche aucune erreur de cœur
(`F001`, `F002`, `R001`, `R002`). Elle est **conforme à son profil** si elle ne
déclenche en plus aucune erreur de profil. `okflint validate` exige les deux pour
retourner `exit 0`.
