---
type: Spec
id: SPEC-002
title: "Support d'OKF v0.2 dans okflint"
description: "Rendre la version de spec OKF ciblée explicite et valider les nouvelles familles de frontmatter introduites par OKF v0.2 (provenance, confiance, cycle de vie, fraîcheur, attestation)."
status: accepted
superseded-by:
work-item:
tags: [okf, spec, validation, provenance, attestation]
timestamp: 2026-08-28T14:00:00Z
perimeter: project
audience: [claude-code]
---

# SPEC-002 — Support d'OKF v0.2 dans okflint

## Objectif

Google Cloud a publié OKF v0.2 le 25 juillet 2026, six semaines après la v0.1.
okflint valide aujourd'hui la v0.1 : sa clause de conformité, ses fichiers
réservés, son modèle de liens. Le manifeste porte déjà une clé `okf_version`,
mais le moteur ne s'en sert pas — la version cible est une hypothèse implicite,
jamais une entrée.

Le problème que v0.2 traite est exactement celui qu'okflint sert. Quand un humain
écrit un concept, la responsabilité est implicite : quelqu'un y a mis son nom.
Quand un agent en génère dix mille dans la nuit, cette garantie disparaît, et ce
qui les lira ensuite doit juger chaque concept sur des signaux qu'il peut
réellement voir. v0.2 rend cinq questions répondables depuis le frontmatter :

| Question | Famille |
| --- | --- |
| À partir de quoi ceci a-t-il été créé ? | provenance (`sources`) |
| Quelle confiance lui accorder ? | confiance (`generated`, `verified`) |
| Est-ce encore vrai ? | fraîcheur (`stale_after`) |
| Est-ce la version courante ? | cycle de vie (`status`) |
| Ce chiffre a-t-il été produit comme on avait dit ? | attestation (`Attested Computation`) |

Un linter déterministe est le bon endroit pour vérifier que ces signaux sont
**présents et bien formés**. C'est aussi, et c'est le cœur de cette spec, le
mauvais endroit pour vérifier qu'ils sont **vrais**.

Enjeu de timing : fin juillet 2026, un observateur de l'écosystème relevait que
la quasi-totalité des outils de la liste communautaire de Google ciblait encore
la v0.1. La fenêtre où le support v0.2 différencie okflint est étroite mais
réelle.

## Périmètre

### Inclus

- **Version cible explicite.** Le moteur valide contre la version que la base
  déclare (`okf_version` du manifeste), au lieu de supposer 0.1.
- **Acceptation des deux formes** pour les deux renommages de v0.2, avec
  signalement quand une base déclarant 0.2 utilise encore les formes v0.1.
- **Validation de forme** des familles `sources`, `generated`, `verified`,
  `status`, `stale_after` lorsqu'elles sont présentes.
- **Convention d'acteur** (§7) sur `generated.by` et `verified[].by`.
- **Type `Attested Computation`** : présence et forme des champs de contrat
  (`runtime`, `parameters`, `computation`, `executor`, `attester`).
- **Résolution des liens absolus bundle-relatifs** (`/chemin.md`), forme
  *recommandée* par v0.2 §6.1 — voir « Choix et contraintes ».
- **Mise à jour documentaire** : renumérotation des références de sections dans
  `config/RULES.md` et le manifeste d'exemple (la v0.2 renumérote la clause de
  conformité de §9 vers §11, les fichiers d'index de §6 vers §8, les logs de §7
  vers §9).

### Non-objectifs

Trois lignes que cette spec interdit explicitement de franchir, et qui découlent
toutes du principe directeur d'okflint.

**okflint ne juge jamais la véracité d'un signal de confiance.** `verified` est
le champ le plus porteur de v0.2 précisément parce qu'il sépare *avoir lu* de
*avoir confirmé*. Un outil qui laisserait entendre qu'il a vérifié l'affirmation
sous-jacente rendrait le champ sans valeur en une semaine. Le linter constate la
forme de l'assertion ; seul un humain ou un agent consommateur peut la porter.

**okflint n'exécute aucune attestation.** Vérifier qu'un `Attested Computation`
est structurellement sain est de l'analyse statique. Exécuter le calcul
sanctionné, ou vérifier au runtime que c'est bien lui qui a tourné, est de
l'orchestration : cela appartient au consommateur de la base. La spec le dit
elle-même — OKF enregistre le calcul et le moyen de le vérifier, il n'exécute
jamais rien.

**okflint ne calcule aucun palier de confiance.** Les *trust tiers* (§5.3 :
unverified / machine-confirmed / human-reviewed) sont dérivés par le
consommateur. okflint valide que `verified` permet cette dérivation, il ne la
restitue pas comme un verdict.

Hors périmètre également : une commande `fix` ou `migrate` (voir « Choix et
contraintes »), et la migration effective des bases de l'auteur, qui relève d'un
chantier distinct.

## Spécification fonctionnelle

### 1. Version de spec cible

- Le manifeste DOIT continuer à porter `okf_version`, désormais avec `"0.1"` ou
  `"0.2"` comme valeurs reconnues.
- Le moteur DOIT refuser une valeur non reconnue avec l'erreur de manifeste
  existante (exit 2), plutôt que de la traiter en silence.
- Une base déclarant `"0.1"` DOIT être validée exactement comme aujourd'hui :
  aucune des règles introduites ici ne se déclenche. Le support v0.2 est
  strictement additif pour l'existant.
- La règle `R001` DOIT accepter `okf_version: "0.2"` dans l'`index.md` racine,
  seul emplacement où v0.2 autorise du frontmatter dans un fichier d'index.
- **En l'absence de manifeste**, le moteur DOIT supposer `"0.2"`. C'est sans
  effet sur une base v0.1 : les règles de forme ne se déclenchent que sur les
  familles présentes, et les règles de forme héritée (§2) exigent une
  déclaration explicite de 0.2.
- Quand le manifeste déclare `"0.1"`, okflint DEVRAIT émettre un message
  d'information — pas un diagnostic : pas de code de règle, pas d'effet sur le
  code de sortie, pas d'entrée dans la liste des violations. Formulation
  factuelle, du type « manifest targets OKF 0.1; 0.2 is the current revision ».
  Émis une fois au chargement du manifeste, jamais par fichier. En sortie
  `--json`, il appartient à l'en-tête de rapport, pas au tableau des
  diagnostics.

### 2. Les deux renommages, et leurs formes de repli

v0.2 remplace deux constructions v0.1 tout en demandant aux consommateurs de
tolérer l'ancienne forme :

| v0.1 | v0.2 |
| --- | --- |
| `timestamp` | `generated.at` |
| liste `# Citations` dans le corps | champ `sources` |

- okflint DOIT reconnaître les deux formes dans les deux cas.
- Quand la base déclare `okf_version: "0.2"` et qu'un concept porte encore une
  forme v0.1, okflint DEVRAIT le signaler en **hygiène** (avertissement), jamais
  en erreur — ce qui reflète la position de repli de la spec elle-même.
- Précision importante : en v0.2, l'attribution par affirmation ne passe plus par
  une liste `# Citations` mais par des **notes de bas de page markdown dont le
  label est un `sources[].id`**. Le label est la clé de jointure ; la prose de la
  note n'est pas analysée. okflint PEUT signaler une note de bas de page dont le
  label ne correspond à aucun `sources[].id`, et NE DOIT PAS exiger de note de
  bas de page.

### 3. Familles optionnelles : forme quand elles sont présentes

Point doctrinal à trancher, et qui structure toute l'implémentation. La clause de
conformité v0.2 (§11) interdit à un consommateur de rejeter un concept pour une
famille optionnelle **absente**, ou pour une clé inconnue. Elle ne dit rien d'une
famille **présente mais malformée** : sur ce point la spec dit que les
producteurs DEVRAIENT (SHOULD) suivre §5 à §10.

okflint DOIT donc distinguer deux niveaux, et les nommer honnêtement :

**a) Cœur OKF, conditionnel — erreur.** Les champs que la spec déclare REQUIRED
*à l'intérieur* d'une structure. Ils ne se déclenchent que si la structure est
présente ; alors leur absence est une violation d'un MUST, pas une option non
renseignée.

- `generated` présent sans `generated.by`.
- Une entrée de `sources` sans `resource`.
- Un concept de `type: Attested Computation` sans `runtime`.

**b) Hygiène — avertissement configurable.** Tout ce que la spec formule en
SHOULD, ou qui relève d'un vocabulaire. Le producteur qui veut un gate strict le
passe en `error` dans son manifeste.

- `status` hors de `draft | stable | deprecated`. Le vocabulaire de la spec
  n'est qu'une préconisation : §5.4 le pose sans mot-clé RFC 2119, et §11 ne le
  compte pas parmi les trois MUST de la clause de conformité. La règle NE DOIT
  donc PAS se déclencher quand le manifeste déclare un `status_values` pour le
  type du concept : le profil du producteur l'emporte. Le coût de la surcharge
  est de la portabilité, pas de la conformité — un consommateur tiers sait quoi
  faire de `deprecated`, pas de `archived` — et DOIT être documenté comme tel.
  À documenter aussi : §5.4 pose `status` absent ⇒ `stable`, défaut qui perd son
  sens dès que le vocabulaire est surchargé.
- `stale_after` non conforme à `YYYY-MM-DD`.
- `generated.at` / `verified[].at` non conformes à ISO 8601.
- `generated.by` / `verified[].by` hors de la convention d'acteur (§4 ci-dessous).
- Forme v0.1 résiduelle dans une base déclarant 0.2 (§2 ci-dessus).
- Concept dont `stale_after` est dépassé à la date d'exécution (§6 ci-dessous).

Cette séparation NE DOIT PAS être arbitrée par le manifeste : c'est la spec qui
dit ce qui est MUST et ce qui est SHOULD, et `config/RULES.md` DOIT citer la
section correspondante pour chaque règle, comme il le fait déjà.

### 4. Convention d'acteur

Les champs d'identité (`generated.by`, `verified[].by`) suivent une convention
unique (§7) :

- `<producteur>/<version>` pour un agent ou un outil, ex. `reference_agent/gemini-2.5-pro`
- `human:<id>` pour une personne
- `process:<id>` pour un processus automatisé

Le préfixe `human:` est la clé sur laquelle les consommateurs classent le palier
de confiance le plus élevé. okflint DEVRAIT signaler une valeur qui ne correspond
à aucune des trois formes, et NE DOIT PAS vérifier que l'identité désignée existe.

### 5. Forme de `verified`

- `verified` est une **liste** d'événements `{ by, at }`.
- Une forme abrégée est autorisée : un seul vérificateur PEUT être écrit comme un
  mapping nu, sans tiret de liste. La spec impose (MUST) au consommateur de
  traiter ce mapping nu comme une liste à un élément.
- okflint DOIT donc accepter les deux formes sans distinction, et NE DOIT PAS
  signaler la forme abrégée.

C'est le seul MUST que §11 adresse directement aux consommateurs : il vaut pour
okflint comme pour n'importe quel autre lecteur.

### 6. Fraîcheur

- `stale_after` est une date absolue (`YYYY-MM-DD`), pas un TTL relatif : un
  concept est périmé quand `aujourd'hui >= stale_after`.
- okflint DEVRAIT proposer une règle d'hygiène signalant les concepts périmés,
  désactivée par défaut.
- **Arbitrage retenu.** La règle est une règle d'hygiène ordinaire, `off` par
  défaut, promotable en `warn` ou `error` comme les autres. Elle n'est PAS
  réservée à `audit` : préserver l'alignement `audit` / `validate` posé en 0.2.0
  prime sur le risque d'une CI mal configurée. En contrepartie, la date
  d'évaluation DOIT figurer dans la sortie, texte comme JSON, pour qu'un verdict
  reste reproductible a posteriori.

Cette règle est **dépendante de la date d'exécution**, donc non reproductible au
sens strict où les autres règles le sont : deux exécutions à deux mois d'écart
peuvent diverger sur une base inchangée. Elle DOIT donc être documentée comme
telle dans `config/RULES.md`, et sa sortie DOIT porter la date d'évaluation. Elle
reste déterministe (même base + même date ⇒ même verdict), ce qui suffit à la
faire entrer dans le périmètre — mais l'ambiguïté mérite d'être écrite plutôt que
découverte par un utilisateur dont la CI change d'avis toute seule.

### 7. Le type `Attested Computation`

v0.2 introduit un unique type de concept prescrit par la spec. C'est une exception
notable à la doctrine « aucun vocabulaire de types codé en dur » : ici le
vocabulaire vient de la spec, pas du manifeste, exactement comme `index.md` et
`log.md` sont des noms de fichiers codés en dur parce que la spec les réserve.

Quand un concept porte `type: Attested Computation` et que la base déclare 0.2 :

- `runtime` DOIT être présent (REQUIRED pour ce type).
- `parameters`, s'il est présent, DOIT être une liste d'entrées `{ name, type, required }`.
- `executor`, s'il est présent, DEVRAIT porter `resource` et `receipt` (liste de
  noms de champs).
- `attester`, s'il est présent, DEVRAIT porter `resource`.
- Le calcul est fourni **soit** par un bloc de code sous `# Computation` dans le
  corps, **soit** par un chemin dans le champ `computation`. okflint DEVRAIT
  signaler le cas où les deux sont présents, et le cas où aucun ne l'est.
- Les champs de chemin (`computation`, `executor.resource`, `attester.resource`)
  suivent §6.2 : URL absolue, chemin bundle-relatif commençant par `/`, ou chemin
  relatif. okflint NE DOIT PAS exiger que la cible existe (la spec ne l'exige
  pas), mais PEUT le signaler en hygiène au même titre qu'un lien cassé.

okflint NE DOIT PAS interpréter le contenu du calcul, ni valider la syntaxe SQL,
dbt ou Python qu'il contient. Les cibles de `computation`, `executor.resource` et
`attester.resource` NE SONT PAS des concepts OKF : ce sont des fichiers sans
frontmatter, hors du corpus validé.

**Trois situations, selon le manifeste.** Le type venant de la spec et non du
producteur, il est codé en dur dans le moteur pour les règles de cœur, au même
titre que `index.md` et `log.md` :

1. **Aucun manifeste** — les contrôles de cœur s'appliquent (`F005` : `runtime`
   obligatoire). Rien d'autre à vérifier : le producteur n'a pris aucun
   engagement.
2. **Le manifeste déclare `Attested Computation`** — contrôles de cœur, plus les
   contrôles de profil que le manifeste ajoute par-dessus (champs `required`
   supplémentaires, vocabulaires `<prop>_values`). Empilement normal.
3. **Le manifeste existe mais ne déclare pas le type, et un concept l'utilise**
   — contrôles de cœur, plus `F101` en **erreur**, comme pour n'importe quel
   autre type non déclaré.

**Aucune exemption.** `F101` (type hors des types déclarés) et `F201` (champ hors
du schéma déclaré) NE DOIVENT PAS exempter `Attested Computation` ni les champs
des familles v0.2. La raison est structurelle : ces deux règles n'appartiennent
pas au cœur OKF. `F101` est à l'étage profil, `F201` à l'étage hygiène. La spec
interdit à un *consommateur* de rejeter un type ou un champ inconnu ; elle
n'interdit rien à un producteur qui a écrit son propre contrat et demande qu'on
l'y tienne. Exempter reviendrait à importer une contrainte de consommateur dans
des étages qui n'en relèvent pas.

La règle d'usage qui en découle, et qui DOIT être documentée : **si un manifeste
existe, il déclare exhaustivement ce que le bundle utilise.** Sans manifeste,
okflint ne contrôle que le cœur, sur la seule base de ce que les documents
contiennent. Avec manifeste, le producteur prend des engagements et okflint l'y
tient.

### 8. Liens absolus bundle-relatifs

v0.2 **recommande** la forme absolue `[texte](/tables/customers.md)`, interprétée
relativement à la racine du bundle, parce qu'elle survit au déplacement d'un
document. La forme relative reste supportée.

okflint DOIT résoudre un lien commençant par `/` contre la racine du bundle, et
non contre la racine du système de fichiers ni contre le répertoire du document.
Une base qui suit la recommandation de la spec NE DOIT PAS voir ses liens
remontés en `L002`.

**Constat à l'implémentation (2026-08-28).** La résolution mono-root était déjà
correcte, y compris depuis un sous-répertoire. Le défaut réel était
**multi-root** : `extract_markdown_links` ne testait que le root propriétaire du
fichier source, si bien qu'un lien `/x.md` dont la cible existait dans un autre
root du même manifeste était remonté en `L002` à tort. Corrigé par un paramètre
optionnel `other_roots`, câblé depuis `validate.py` et `audit.py`.

## Choix et contraintes

**Pas de commande `fix`.** La migration v0.1 → v0.2 (renommer `timestamp` en
`generated.at`, convertir une liste `# Citations` en champ `sources`) est un
réécriture déterministe, et aurait pu justifier une commande `fix`. Ce chantier a
été écarté du périmètre d'okflint : le linter signale, il ne réécrit pas. Les
deux règles du catalogue portant aujourd'hui la mention « auto-fixable » (`F106`,
`S102`) doivent être corrigées en conséquence.

**Un seul type prescrit, assumé comme tel.** `Attested Computation` est codé en
dur parce que la spec le prescrit. La doctrine « aucun vocabulaire codé en dur »
vise le vocabulaire *du producteur*, pas celui de la spec — la même raison qui
fait que `index.md` est codé en dur. Ce point DOIT être écrit explicitement dans
`config/RULES.md` pour qu'il ne soit pas relu plus tard comme une régression.

**Rétrocompatibilité totale.** Une base déclarant `okf_version: "0.1"`, ou un
manifeste écrit avant ce chantier, DOIT produire exactement les mêmes
diagnostics qu'avant. Aucune règle nouvelle ne se déclenche sans déclaration
explicite de 0.2. Le chantier est donc `minor`, pas `major`.

**Découverte traitée séparément.** La résolution des liens absolus (§8) était un
faux positif présent *avant* ce chantier, indépendamment de v0.2 : une base v0.1
multi-root utilisant déjà `/chemin.md` voyait ses liens inter-root remontés en
`L002`. Traitée en premier et sortie seule (PLAN-002 étape 1).

## Critères d'acceptation

- [ ] `okf_version: "0.2"` est accepté dans le manifeste et dans l'`index.md`
      racine ; une valeur non reconnue sort en exit 2.
- [ ] Une base déclarant `"0.1"` produit un diagnostic identique à celui produit
      avant le chantier (test de non-régression sur une fixture existante).
- [ ] `timestamp` et `generated.at` sont tous deux reconnus ; la forme v0.1 dans
      une base 0.2 produit un avertissement, jamais une erreur.
- [ ] `verified` est accepté sous forme de liste **et** sous forme de mapping nu,
      sans avertissement dans les deux cas.
- [ ] `generated` sans `by`, une entrée `sources` sans `resource`, et un
      `Attested Computation` sans `runtime` produisent chacun une erreur de cœur.
- [ ] `status`, `stale_after`, la convention d'acteur et les formes v0.1
      résiduelles produisent des avertissements configurables, jamais des erreurs
      par défaut.
- [ ] Un lien `[x](/chemin.md)` vers une cible existante du bundle ne produit
      plus de `L002`.
- [ ] Chaque règle nouvelle est documentée dans `config/RULES.md` avec son code,
      son étage, sa sévérité et la **section v0.2 qui l'autorise**.
- [ ] Chaque règle nouvelle est couverte par un test déclenchant sur un cas non
      conforme et ne déclenchant pas sur un cas conforme.
- [ ] `inv lint`, `inv test` (couverture ≥ 93 %), `inv docs` et
      `okflint validate --manifest manifest_okflint.yaml .` passent.
