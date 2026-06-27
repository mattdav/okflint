# okflint

Linter de conformité déterministe pour bases documentaires OKF (Open Knowledge
Format). Vérifie qu'une base Markdown respecte OKF et le cadre déclaré dans son
manifeste. Pas de LLM, pas d'état runtime : un gate reproductible, façon Ruff.

## Structure

```
src/okflint/
├── cli.py        ← dispatcher CLI : okflint audit | validate
├── scanner.py    ← primitives partagées (scan, frontmatter, code-fence, liens)
├── audit.py      ← commande audit (descriptive, exit 0 toujours)
├── validate.py   ← commande validate (gate normatif, exit 0/1)
├── manifest.py   ← chargement + validation du manifeste lui-même
├── __init__.py
├── __main__.py   ← python -m okflint
└── py.typed      ← marqueur PEP 561 (package typé)
```

## Commandes

- `inv lint` — ruff check --fix + ruff format + mypy. Doit passer à zéro.
- `inv test` — pytest avec couverture.
- `inv repomix` — pack la codebase en XML daté dans `.okflint/` pour un LLM.
- `inv release [--part=patch|minor|major] [--dry-run]` — bump version + push + déclenche la CI/CD.
- `uv build` — construit sdist + wheel dans `dist/`.
- `okflint audit --bundle <dir> --vault <dir> [--apply]` — audit descriptif.
- `okflint validate --manifest <okf-base.yaml> <targets...>` — gate de conformité.

## Architecture

Validation en **3 étages** (catalogue complet dans `config/RULES.md`) :
1. **Cœur OKF** — codé en dur, la clause de conformité §9 de la spec (F001, F002, R001, R002).
2. **Profil** — piloté par le manifeste, les règles type-aware de la base (F101-F106, S101, S102).
3. **Hygiène** — opt-in, plus strict qu'OKF, en avertissement (L001-L003, S201, R201, F201).

Le moteur est **générique** : aucun vocabulaire de types n'est codé en dur. Tout
(types, champs, statuts, nom du champ de statut) vit dans le manifeste `okf-base.yaml`.
`manifest.py` valide le manifeste lui-même avant de l'appliquer.

Doctrine : **déterministe d'abord, LLM jamais dans le moteur.** Ce qui relève du
jugement (découper, réécrire, router) appartient au consommateur de la base, pas au
linter. Voir `ROADMAP.md` pour la frontière okflint / harness.

## Dépendances notables

- **Runtime** : `pyyaml` (seule dépendance de production).
- **Dev** : `ruff`, `mypy` (lint), `pytest` + `pytest-cov` (tests), `invoke` (tasks).
- **Build** : `hatchling` (>= 1.26 pour la syntaxe SPDX de licence).

## Conventions

- `uv run` exclusivement (jamais `python`/`pip` directs).
- Type hints stricts (`mypy strict`). Docstrings format Google sur les fonctions publiques.
- Commentaires en français, code en anglais.
- Aucune valeur hardcodée spécifique à un environnement dans le code du package
  (les chemins de bundle/vault sont des arguments CLI, pas des constantes).

## Suivi de progression

- Lire `.claude/progress.log` en début de session si le fichier existe.
- Mettre à jour `.claude/progress.log` en fin de tâche.
