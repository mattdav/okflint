# Roadmap okflint

Ce document trace les évolutions envisagées au-delà de la v0.1. Il n'engage aucun
calendrier — c'est un backlog de réflexion, pas un plan de release.

okflint suit une ligne directrice stable : **valider de façon déterministe la
conformité d'une base documentaire à OKF et au cadre que la base s'est elle-même
donné dans son manifeste.** Toute évolution doit rester dans ce périmètre — pas de
jugement LLM dans le moteur, pas de logique d'exécution runtime. Ce qui relève du
jugement ou de l'orchestration appartient au *consommateur* de la base (un agent,
un harness), pas au linter.

---

## v0.1 — État actuel

- Validation en 3 étages : cœur OKF (§9), profil (manifeste), hygiène (opt-in)
- 18 règles cataloguées (voir [`config/RULES.md`](config/RULES.md))
- CLI unifiée `okflint audit | validate`
- Moteur générique piloté par un manifeste YAML (`okf-base.yaml`)
- Validation du manifeste lui-même (`manifest.py`)

---

## Chantier A — Cohésion sémantique pour un découpage déterministe plus fin

**Problème.** La règle actuelle `S201` (candidat au découpage) repose sur des
signaux structurels grossiers : présence de plusieurs `# H1`, ou liste homogène de
`## H2`. Elle rate les fichiers qui ont une structure d'apparence cohérente mais
mélangent des **thématiques trop éloignées** — typiquement le genre de fichier qui
fait mal réagir un agent (skills mal activées, contexte superflu chargé).

**Direction.** Ajouter des règles de cohésion sémantique **mesurées de façon
déterministe**, sans LLM, par exemple :

- **Cohésion lexicale inter-sections** : vectorisation TF-IDF par section, mesure de
  similarité inter-sections. Une cohésion faible (sections au vocabulaire disjoint)
  signale un fichier hétérogène → candidat au découpage. Reproductible, auditable.
- **Divergence des familles de liens entrants** : si différentes sections d'un
  fichier sont citées par des familles de concepts disjointes (section A pointée par
  les `Decision`, section B par les `Procedure`), c'est probablement deux concepts.
- **Divergence de tags intra-fichier** : si un fichier porte (ou ses sections
  portent) des tags thématiquement éloignés.

Ces signaux donneraient une ou plusieurs règles d'hygiène supplémentaires
(ex. `S202` — hétérogénéité thématique élevée). Le **jugement final** (faut-il
découper, comment nommer les morceaux) reste hors okflint : il appartient à
l'humain ou à un agent qui consomme le diagnostic.

**Frontière.** okflint *signale* un candidat au découpage avec des métriques ; il
ne *décide* ni *n'exécute* le découpage.

---

## Chantier B — Attendus d'une grille de lecture vérifiables par le manifeste

**Contexte.** Un agent qui exploite une base a besoin d'une *grille de lecture* :
à partir des frontmatter (types, tags), savoir quels concepts consulter pour une
intention donnée, dans quel ordre, en récupérant le moins de contexte superflu
possible. Cette grille est un travail méthodologique propre à chaque organisation —
elle n'est pas du ressort d'okflint.

**Ce qu'okflint PEUT faire.** De la même façon qu'il ne décide pas quels types
existent (le manifeste le déclare) mais vérifie que la base les respecte, okflint
peut vérifier que la base contient **tout ce qu'il faut pour qu'une grille de
lecture fonctionne**, dès lors que le manifeste déclare les attendus de cette
grille. Exemples d'attendus déclarables et vérifiables :

- « Tout concept de type `Procedure` doit porter un tag de `domaine` pour être
  routable » → règle de champ requis conditionnel.
- « Les valeurs du champ `domaine` appartiennent à un vocabulaire fermé » → règle de
  vocabulaire contrôlé sur un champ arbitraire.
- « Tout concept routable déclare une `intention` » → règle de présence.

Cela suppose d'étendre le manifeste avec une section décrivant ces attendus (un
bloc `routing` ou `grid`, à concevoir), et d'ajouter les règles de validation
correspondantes au catalogue.

**Frontière — essentielle.** okflint vérifie que la base est **structurée pour être
routable** (les champs, tags, vocabulaires nécessaires sont présents et cohérents).
Il ne **parcourt pas** la grille : le parcours fléché « pour l'intention A, lis X
puis Y » est de la logique d'orchestration *runtime*, exécutée par l'agent dans son
harness. okflint est statique ; il valide une base au repos. La grille rend la base
*routable* ; le harness *route*.
