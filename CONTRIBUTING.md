# Guide de contribution — okflint

> **Merci de contribuer à okflint. Ce document décrit les conventions et processus
> à respecter pour maintenir une base de code cohérente et de qualité.**

---

## Environnement de développement

### Prérequis

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) — gestionnaire de paquets
- [invoke](https://www.pyinvoke.org/) — runner de tâches (installé via les dev deps)

### Installation

```bash
git clone https://github.com/mattdav/okflint
cd okflint
uv sync --all-extras
uv pip install -e .
```

Vérifier que tout fonctionne :

```bash
inv lint        # doit passer à zéro
inv test        # tous les tests doivent passer
uv run okflint --help
```

---

## Architecture du projet

```
src/okflint/
├── cli.py        ← dispatcher CLI : okflint audit | validate
├── scanner.py    ← primitives partagées (scan, frontmatter, code-fence, liens)
├── audit.py      ← commande audit (descriptive)
├── validate.py   ← commande validate (gate normatif)
├── manifest.py   ← chargement + validation du manifeste
├── __init__.py
├── __main__.py   ← python -m okflint
└── py.typed
```

okflint est un **moteur générique** : aucun vocabulaire de types n'est codé en dur.
Tout le standard d'une base (types, champs, statuts) est déclaré dans son manifeste
`okf-base.yaml`. Le catalogue des règles de validation est documenté dans
[`config/RULES.md`](config/RULES.md) — c'est la spec de référence. Toute nouvelle règle
doit y être documentée avec son code, son étage et sa sévérité.

### Doctrine

- **Déterministe d'abord.** Le moteur ne contient aucun appel LLM. Une règle qui
  exigerait du jugement n'a pas sa place dans le cœur ou le profil.
- **Honnêteté OKF.** okflint distingue ce qui est *vraiment* OKF (cœur, §9 de la
  spec) de ce qui est une convention de la base (profil) ou un choix plus strict
  (hygiène). Ne jamais présenter une convention locale comme une exigence OKF.
- Voir [`ROADMAP.md`](ROADMAP.md) pour la frontière entre okflint (validation
  statique) et le harness d'un agent (orchestration runtime).

---

## Qualité du code

### Outils

| Outil | Rôle |
|---|---|
| [ruff](https://docs.astral.sh/ruff/) | Linting et formatting |
| [mypy](https://mypy.readthedocs.io/) | Vérification des types statiques (mode strict) |

### Commande unique

```bash
inv lint        # doit passer à zéro
```

Lance en séquence : `ruff check --fix`, `ruff format`, `mypy`.
**Doit passer à zéro avant tout commit.**

### Règles strictes

- Aucun `# noqa` sans commentaire justificatif sur la même ligne.
- Aucun `# type: ignore` sans commentaire justificatif sur la même ligne.
- Type hints obligatoires sur toutes les fonctions et méthodes publiques.
- Éviter `Any` sauf cas justifié.
- Commentaires en français, code (noms, identifiants) en anglais.

### beartype

**Toutes les fonctions publiques** (non préfixées par `_`) doivent être décorées avec `@beartype`.
Ce décorateur valide les types à l'exécution en complément de mypy (statique).
Ne pas décorer les fonctions privées ni les tasks invoke (signature incompatible).

---

## Tests

```bash
inv test
```

### Conventions

- Un fichier de test par module : `tests/test_<module>.py`.
- Les fixtures partagées vont dans `tests/conftest.py`.
- Nommer les tests explicitement : `test_<fonction>_<scenario>_<resultat_attendu>`.
- Couvrir les cas limites : absence de frontmatter, YAML invalide, manifeste
  malformé, valeurs de statut interdites, liens cassés vs références externes.

### Règle fondamentale

Chaque règle du catalogue (`config/RULES.md`) doit être couverte par au moins un test
qui vérifie qu'elle se déclenche sur un cas non conforme et ne se déclenche pas sur
un cas conforme. Les tests ne doivent jamais être supprimés pour faire passer la CI.

---

## Workflow git

### Branches

| Branche | Usage |
|---|---|
| `main` | Code stable, prêt pour publication |
| `feat/<nom>` | Nouvelle fonctionnalité |
| `fix/<nom>` | Correction de bug |
| `chore/<nom>` | Maintenance, refactoring, CI |

### Format des commits

```
feat: ajouter la règle S202 de cohésion sémantique
fix: corriger la distinction False/None pour status_values
chore: mettre à jour les dépendances
docs: compléter le catalogue de règles
test: couvrir les cas limites du parsing de manifeste
```

Types acceptés : `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.

### Avant de committer

```bash
inv lint   # doit passer à zéro
inv test   # tous les tests doivent passer
```

---

## Process de release

### Prérequis

- Être sur la branche `main` avec un working tree propre
- Avoir les droits de push sur le repo
- Avoir configuré le **Trusted Publisher** sur pypi.org (Settings du repo GitHub)

### Format des messages de commit

okflint utilise [commitizen](https://commitizen-tools.github.io/commitizen/) pour
valider les messages et générer automatiquement le CHANGELOG.

**Format obligatoire** :
```
<type>(<scope optionnel>): <description>
```

Types acceptés : `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`, `build`, `style`.

Exemples valides :
```
feat: ajouter la règle S202 de cohésion sémantique
fix(manifest): corriger la distinction False/None pour status_values
docs: mettre à jour le README
chore: mettre à jour les dépendances
```

### Déclencher une release

Une seule commande lance tout le processus :

```bash
inv release               # patch (0.1.0 → 0.1.1) — corrections de bugs
inv release --part=minor  # minor (0.1.0 → 0.2.0) — nouvelles fonctionnalités
inv release --part=major  # major (0.1.0 → 1.0.0) — breaking changes
inv release --dry-run     # simulation sans rien modifier
```

**Ce que fait `inv release` :**
1. Vérifie que vous êtes sur `main` avec un tree propre
2. Lance lint + tests (sécurité avant publication)
3. Bumpe la version via commitizen + met à jour `CHANGELOG.md`
4. Crée un commit de release + un tag `vX.Y.Z`
5. Pousse le commit ET le tag vers `origin/main`
6. Le tag déclenche automatiquement le workflow `release.yml` qui :
   - Build sdist + wheel
   - Publie sur PyPI via Trusted Publisher
   - Crée la GitHub Release avec notes auto-générées

### Trusted Publisher PyPI (configuration une fois)

Pour que `release.yml` puisse publier sans token :
1. Aller sur https://pypi.org/manage/account/publishing/
2. Ajouter un Trusted Publisher :
   - Owner : `mattdav`
   - Repository : `okflint`
   - Workflow : `release.yml`
   - Environment : `pypi`

---

## Checklist avant une Pull Request

- [ ] `uv run inv lint` passe à zéro
- [ ] `uv run inv test` passe à zéro
- [ ] Toute nouvelle règle est documentée dans `config/RULES.md` (code, étage, sévérité)
- [ ] Toute nouvelle règle est couverte par un test (cas conforme + cas non conforme)
- [ ] Les nouvelles fonctions publiques ont des type hints et une docstring Google
- [ ] Aucune valeur spécifique à un environnement n'est hardcodée dans le package
