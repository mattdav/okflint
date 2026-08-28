---
type: Plan
id: PLAN-002
title: "Implémentation du support OKF v0.2"
description: "Mode opératoire en 7 étapes pour rendre la version de spec cible explicite et valider les familles de frontmatter introduites par OKF v0.2."
status: draft
implements: SPEC-002
tags: [okf, validation, provenance, attestation, roadmap]
timestamp: 2026-08-28T15:00:00Z
perimeter: project
audience: [claude-code]
---

# PLAN-002 — Implémentation du support OKF v0.2

## Périmètre

Ce plan implémente [SPEC-002](../specs/SPEC-002_okf-v0.2.md). Lire la spec en
entier avant de commencer : les non-objectifs (§ « Périmètre ») sont des
interdits, pas des recommandations.

Chaque étape est un commit. Les étapes 1 et 2 sont indépendantes et peuvent
sortir seules. Les étapes 3 à 6 dépendent de l'étape 2. L'étape 7 clôt le
chantier.

Cible de version : **0.4.0** (`minor`). Le chantier est strictement additif :
une base déclarant `okf_version: "0.1"` doit produire, à la fin, exactement les
mêmes diagnostics qu'aujourd'hui.

## Codes de règles introduits

À créer dans `config/RULES.md` au fil des étapes. Ne pas réutiliser un code
existant, ne pas renuméroter l'existant.

| Code | Étage | Sévérité | Objet |
| --- | --- | --- | --- |
| `F003` | Cœur | error | `generated` présent sans `generated.by` |
| `F004` | Cœur | error | entrée de `sources` sans `resource` |
| `F005` | Cœur | error | `Attested Computation` sans `runtime` |
| `S203` | Hygiène | warn | `status` hors de `draft \| stable \| deprecated` |
| `S204` | Hygiène | warn | `stale_after` non conforme à `YYYY-MM-DD` |
| `S205` | Hygiène | warn | `generated.at` / `verified[].at` non ISO 8601 |
| `S206` | Hygiène | warn | valeur d'acteur hors convention §7 |
| `S207` | Hygiène | warn | forme de contrat `Attested Computation` invalide |
| `S208` | Hygiène | off | forme v0.1 résiduelle dans une base 0.2 |
| `S209` | Hygiène | off | concept dont `stale_after` est dépassé |

Nouvelles clés du bloc `hygiene` du manifeste : `okf_v02_shapes` (pilote
`S203`–`S207`, défaut `warn`), `legacy_forms` (`S208`, défaut `off`),
`stale_content` (`S209`, défaut `off`). Toute clé absente d'un manifeste existant
prend son défaut — aucun manifeste en circulation ne doit avoir à être modifié.

**Aucune exemption de `F101` ni de `F201`.** Ces deux règles n'appartiennent pas
au cœur OKF : `F101` est à l'étage profil, `F201` à l'étage hygiène. La spec
interdit à un consommateur de rejeter un type ou un champ inconnu ; elle
n'interdit rien à un producteur qui a écrit son propre contrat. Si un manifeste
existe, il déclare exhaustivement ce que le bundle utilise — y compris
`Attested Computation` et les champs des familles v0.2.

## Étapes

### 1. Liens absolus bundle-relatifs

Indépendant de v0.2, corrige un faux positif présent dès aujourd'hui.

- Fichiers cibles : `src/okflint/scanner.py`
- Action : un lien markdown dont la cible commence par `/` doit être résolu
  contre la racine du bundle (le root du manifeste auquel appartient le
  document), et non contre la racine du système de fichiers ni contre le
  répertoire du document. En multi-root, résoudre contre le root propriétaire du
  fichier source ; si la cible n'y existe pas, tenter les autres roots avant de
  conclure à `L002`, comme le fait déjà la résolution de liens à l'échelle de la
  base.
- Ne pas toucher aux wikilinks (`L001`, `L003`), dont la résolution est
  indépendante.
- Vérification : fixture avec `[x](/note1.md)` depuis un sous-répertoire → aucun
  `L002`. Fixture avec `[x](/absent.md)` → `L002`.
- Commit `fix:`

### 2. `okf_version` comme entrée du moteur

- Fichiers cibles : `src/okflint/manifest.py`, `src/okflint/validate.py`,
  `src/okflint/audit.py`, `src/okflint/cli.py`
- Action :
  - `manifest.py` accepte `"0.1"` et `"0.2"` ; toute autre valeur lève
    `ManifestError` (exit 2). Exposer la version résolue sur l'objet de config.
  - En l'absence de manifeste, la version supposée est `"0.2"`.
  - `R001` accepte `okf_version: "0.2"` dans l'`index.md` racine.
  - Quand le manifeste déclare `"0.1"`, émettre **un message d'information**
    (`manifest targets OKF 0.1; 0.2 is the current revision`) une seule fois au
    chargement. Ce n'est **pas** un diagnostic : pas de code, pas d'entrée dans
    la liste des violations, aucun effet sur le code de sortie. En `--json`, il
    va dans l'en-tête de rapport, jamais dans le tableau des diagnostics.
- Vérification : `okflint validate` sur les fixtures existantes produit une
  sortie inchangée hors la ligne d'information ; un `okf_version: "0.3"` sort en 2.
- Commit `feat:`

### 3. Règles de cœur conditionnelles — `F003`, `F004`, `F005`

Ces trois règles ne se déclenchent **que si la structure est présente**. Une
famille absente n'est jamais un défaut : §11 de la spec l'interdit explicitement.

- Fichiers cibles : `src/okflint/validate.py` (ou le module de règles de cœur)
- Action :
  - `F003` : `generated` présent → `by` obligatoire. `at` reste optionnel ici
    (son format relève de `S205`).
  - `F004` : chaque entrée de `sources` → `resource` obligatoire. `sources` doit
    être une liste de mappings ; une autre forme déclenche aussi `F004`.
  - `F005` : concept de `type: Attested Computation` → `runtime` obligatoire.
- Vérification : un test déclenchant et un test non déclenchant par règle, plus
  un test confirmant qu'une famille absente ne produit rien.
- Commit `feat:`

### 4. Règles de forme d'hygiène — `S203` à `S207`

- Fichiers cibles : moteur de règles + `src/okflint/manifest.py` (nouvelle clé
  `hygiene.okf_v02_shapes`)
- **Gating.** Comme `F003`–`F005`, ces cinq règles sont gatées sur la version
  résolue : silencieuses sous `"0.1"`, actives sous `"0.2"` (donc actives sans
  manifeste). Sous un manifeste v0.1, ce sont les règles de profil (`F102`,
  `F105`, `S102`) qui tiennent l'utilisateur à ses engagements, plus le message
  INFO. Conséquence à documenter dans `RULES.md` : sous un manifeste v0.1, une
  famille v0.2 employée sans être déclarée n'est contrôlée par rien, `F201`
  étant `off` par défaut. C'est voulu, et c'est ce que le message INFO invite à
  corriger.
- Action :
  - `S203` : `status` hors de `draft | stable | deprecated`. **Ne se déclenche
    pas** si le manifeste déclare un `status_values` pour le type du concept —
    le profil du producteur l'emporte sur le vocabulaire par défaut de la spec,
    qui n'est qu'une préconisation (§5.4, sans mot-clé RFC 2119, absent des trois
    MUST de §11).
  - `S204` : `stale_after` non conforme à `YYYY-MM-DD`. Ne pas doubler `S102`
    si `stale_after` figure dans `profile.date_fields`.
  - `S205` : `generated.at` et `verified[].at` non parsables en ISO 8601. **Les
    deux formes sont acceptées** — date seule (`2026-08-28`) comme datetime
    complet. `stale_after` reste strictement date-only, contrôlé par `S204` :
    ce n'est pas une incohérence, c'est ce que pose la spec.
  - `S206` : `generated.by` et `verified[].by` hors des trois formes de la
    convention d'acteur. Formes acceptées :
    - `human:<id>` et `process:<id>` — préfixe **sensible à la casse**,
      identifiant non vide ;
    - `<producteur>/<version>` — deux segments non vides, sans espace, aucune
      validation du format de version.
    Tout le reste déclenche. Délibérément permissif sur la troisième forme : le
    but est d'attraper `by: Matthieu` ou `by: gpt-4`, pas de valider un
    identifiant. La sensibilité à la casse est la raison d'être de la règle : un
    `Human:matthieu` fait silencieusement sortir le concept du palier de
    confiance le plus élevé. Ne jamais vérifier que l'identité désignée existe.
  - `S207` : forme de contrat `Attested Computation` — `parameters` non liste de
    `{name, type, required}` ; `executor` sans `resource` ou sans `receipt` ;
    `attester` sans `resource` ; champ `computation` **et** bloc `# Computation`
    présents simultanément ; ni l'un ni l'autre.
- **`verified` accepte les deux formes** : liste de `{by, at}`, ou mapping nu
  traité comme une liste à un élément. La forme abrégée ne produit **aucun**
  diagnostic — c'est le seul MUST que §11 adresse directement aux consommateurs.
- Vérification : couverture déclenchante/non déclenchante par règle ; test
  explicite sur `verified` en mapping nu ; test explicite sur `S203` neutralisé
  par un `status_values` de profil ; test explicite confirmant le silence total
  des cinq règles sous un manifeste `okf_version: "0.1"`.
- **Granularité** : les cinq règles partagent la clé `hygiene.okf_v02_shapes`.
  Promouvoir `S207` en `error` promeut aussi `S203`. Compromis assumé — codes
  séparés pour la lisibilité du catalogue, clé unique pour la configuration — à
  écrire dans `RULES.md` pour que personne ne cherche une clé par règle.
- Commit `feat:`

### 5. Formes héritées et fraîcheur — `S208`, `S209`

- Fichiers cibles : moteur de règles + `manifest.py` (clés `legacy_forms`,
  `stale_content`)
- Action :
  - `S208` : `timestamp` au lieu de `generated.at`, ou liste `# Citations` dans
    le corps au lieu du champ `sources`. **Ne se déclenche que si la base
    déclare explicitement `okf_version: "0.2"`** — jamais sur la version
    supposée par défaut, sans quoi toutes les bases existantes se mettraient à
    signaler du jour au lendemain.
  - `S209` : concept dont `stale_after` est atteint ou dépassé à la date
    d'exécution. La **date d'évaluation** doit figurer dans la sortie texte et
    dans le JSON — c'est ce qui rend un verdict reproductible a posteriori.
- Les deux règles acceptent `off | warn | error` comme les autres.
- Vérification : `S209` testée avec une date injectée, jamais avec `date.today()`
  en dur dans le test.
- Commit `feat:`

### 6. Le type `Attested Computation`

- Fichiers cibles : moteur de règles
- Action :
  - Le type est connu du moteur pour la seule règle de cœur `F005` (étape 3) :
    un concept portant `type: Attested Computation` doit porter `runtime`. Ce
    contrôle s'applique avec ou sans manifeste, au même titre que les fichiers
    réservés sont codés en dur.
  - **Ne créer aucune exemption.** `F101` continue de remonter en erreur un
    `Attested Computation` non déclaré dans un manifeste qui existe. `F201`
    continue de remonter les champs des familles v0.2 absents du schéma déclaré.
    C'est le comportement voulu : un manifeste déclare exhaustivement ce que le
    bundle utilise.
  - Les cibles de `computation`, `executor.resource` et `attester.resource` ne
    sont **pas** des concepts OKF : ne pas les scanner, ne pas exiger leur
    existence, ne pas leur appliquer `F001`/`F002`.
- Vérification : test avec manifeste à liste de types fermée + concept
  `Attested Computation` → un `F101` en erreur, et `F005` s'applique quand même.
  Test sans manifeste + même concept → `F005` seul, aucun `F101`.
- Commit `feat:`

### 7. Documentation

- Fichiers cibles : `config/RULES.md`, `okf-base.example.yaml` (ou
  `example/manifest.example.yaml`), `README.md`, `docs/code/guides/rules.rst`,
  `docs/code/guides/manifest.rst`
- Action :
  - `config/RULES.md` : ajouter les 11 règles avec code, étage, sévérité, exemple
    conforme/non conforme, et **la section v0.2 qui les autorise**. Mettre à jour
    le tableau de référence rapide et la section « Conformance and exit code ».
  - **Renuméroter les références de sections** : la clause de conformité passe de
    §9 à §11, les fichiers d'index de §6 à §8, les logs de §7 à §9. Le lien vers
    la spec en tête de fichier passe de « OKF v0.1 » à « OKF v0.2 ».
  - Écrire explicitement, dans `config/RULES.md`, que `Attested Computation` est
    le seul vocabulaire de type codé en dur, et pourquoi : il vient de la spec,
    pas du producteur, exactement comme `index.md` et `log.md`. Sans cette note,
    le point sera relu plus tard comme une régression doctrinale. Préciser dans
    la foulée que ce codage en dur ne vaut que pour `F005` (cœur) et ne crée
    aucune exemption à `F101` ni `F201`.
  - Documenter la règle d'usage : sans manifeste, okflint ne contrôle que le
    cœur, sur la seule base de ce que les documents contiennent ; avec
    manifeste, celui-ci doit déclarer exhaustivement ce que le bundle utilise.
  - Documenter, sur `S203`, que la surcharge du vocabulaire de `status` coûte de
    la portabilité et non de la conformité (un consommateur tiers sait quoi faire
    de `deprecated`, pas de `archived`), et que le défaut « `status` absent ⇒
    `stable` » de §5.4 perd son sens dès que le vocabulaire est surchargé.
  - Manifeste d'exemple : documenter les trois nouvelles clés d'hygiène
    (`okf_v02_shapes`, `legacy_forms`, `stale_content`) avec leurs défauts, et
    passer `okf_version` à `"0.2"`.
  - `README.md` : supprimer la mention périmée d'une commande `fix` générique
    dans la section Roadmap (Track E a été abandonné).
- Commit `docs:`

## Mise à jour documentaire

- [ ] `README.md` mis à jour (nouvelles règles mentionnées si pertinent, mention
      `fix` supprimée)
- [ ] `config/RULES.md` complet et renuméroté sur v0.2
- [ ] Statut de `SPEC-002` passé à `implemented`
- [ ] Statut de ce plan passé à `done`
- [ ] Track F retiré de `ROADMAP.md` (convention du projet : une section est
      supprimée une fois livrée) et reporté dans « v0.4 — Current state »

## Vérification finale

- `uv run inv lint` à zéro
- `uv run inv test`, couverture ≥ 93 %
- `uv run inv docs` avec `-W --keep-going`
- `uv run okflint validate --manifest manifest_okflint.yaml .` → exit 0
- **Non-régression** : sur une base déclarant `okf_version: "0.1"`, la sortie est
  identique à celle produite avant le chantier, hors ligne d'information. À
  vérifier explicitement, pas à supposer.
- Un commit par étape, message en anglais, format commitizen
- `.claude/progress.log` mis à jour

## Hors périmètre — ne pas faire

- Aucune commande `fix` ou `migrate` : okflint signale, il ne réécrit pas.
- Ne pas juger la véracité d'un signal de confiance, ne pas dériver de *trust
  tier*, ne pas exécuter d'attestation.
- Ne pas migrer les manifestes de l'auteur vers `okf_version: "0.2"` : chantier
  distinct, à mener après la release.
- Ne pas renuméroter ni modifier les règles existantes hors des références de
  sections de l'étape 7.
