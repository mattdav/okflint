# Guide de contribution — okf_converter

>**Merci de contribuer à ce projet. Ce document décrit les conventions et
processus à respecter pour maintenir une base de code cohérente et de qualité.**

---

## Environnement de développement

### Prérequis

- Python 3.10
- [uv](https://docs.astral.sh/uv/) — gestionnaire de paquets
- [invoke](https://www.pyinvoke.org/) — runner de tâches

### Installation

```bash
git clone <url-du-repo>
cd okf_converter
uv sync
cp .env.example .env
```

---

## Configuration et variables d'environnement

**Toute valeur susceptible de changer selon l'environnement doit être externalisée.**
Ce projet utilise [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
pour charger et valider la configuration.

### Règles

- Les secrets et valeurs locales vont dans `.env` (jamais commité, dans `.gitignore`)
- La configuration structurée va dans `config/settings.yaml`
- Les valeurs par défaut non sensibles vont dans `config/settings.default.yaml` (commité)
- `.env.example` liste toutes les variables attendues, sans valeurs sensibles (commité)

### Ce qui doit être variabilisé

- Credentials et secrets (API keys, mots de passe, tokens)
- URLs et endpoints (base URLs, hosts, ports)
- Paramètres d'environnement (timeouts, chemins, feature flags)

### Ce qui ne doit jamais apparaître dans le code

```python
# ❌ Interdit
API_KEY = "sk-1234abcd"
BASE_URL = "https://api.monservice.com"
TIMEOUT = 30

# ✅ Correct
from src.okf_converter.config import settings
response = client.get(settings.base_url, timeout=settings.timeout)
```

### Mise à jour de .env.example

Toute nouvelle variable d'environnement doit être ajoutée dans `.env.example`
avec une description en commentaire :

```bash
# URL de l'API externe (obligatoire)
API_BASE_URL=

# Timeout des requêtes en secondes (défaut : 30)
REQUEST_TIMEOUT=30
```

---

## Qualité du code

### Outils

| Outil | Rôle |
|---|---|
| [ruff](https://docs.astral.sh/ruff/) | Linting et formatting |
| [mypy](https://mypy.readthedocs.io/) | Vérification des types statiques |

### Commande unique

```bash
uv run inv lint
```

Lance en séquence : `ruff check --fix`, `ruff format`, `mypy`.
**Doit passer à zéro avant tout commit.**

### Règles strictes

- Aucun `# noqa` sans commentaire justificatif sur la même ligne
- Aucun `# type: ignore` sans commentaire justificatif sur la même ligne
- Type hints obligatoires sur toutes les fonctions et méthodes publiques
- Éviter `Any` sauf cas justifié

---

## Tests

```bash
uv run inv test
```

### Conventions

- Un fichier de test par module : `tests/unit/test_<module>.py`
- Les fixtures partagées vont dans `tests/conftest.py`
- Nommer les tests de façon explicite : `test_<fonction>_<scenario>_<resultat_attendu>`
- Couvrir les cas limites : `None`, liste vide, valeurs invalides, erreurs

### Règle fondamentale

Les tests ne doivent jamais être supprimés pour faire passer la CI.
Un test qui échoue signale un vrai problème à corriger.

---

## Workflow git

### Branches

| Branche | Usage |
|---|---|
| `main` | Code stable, prêt pour la production |
| `feat/<nom>` | Nouvelle fonctionnalité |
| `fix/<nom>` | Correction de bug |
| `chore/<nom>` | Maintenance, refactoring, CI |

### Format des commits

```
feat: ajouter le chargement de configuration depuis yaml
fix: corriger le timeout des requêtes HTTP
chore: mettre à jour les dépendances
docs: compléter la section installation du README
```

Types acceptés : `feat`, `fix`, `chore`, `docs`, `test`, `refactor`

### Avant de committer

```bash
uv run inv lint   # doit passer à zéro
uv run inv test   # tous les tests doivent passer
```

---

## Structure du projet

```
src/okf_converter/
├── bin/        ← scripts exécutables et points d'entrée CLI
├── config/     ← classe Settings (pydantic-settings) et fichiers yaml
├── data/       ← accès, chargement et transformation des données
├── log/        ← configuration du logging
├── __init__.py
└── __main__.py ← point d'entrée principal
```

Chaque sous-module a sa propre responsabilité. Ne pas mélanger logique métier
et configuration dans le même fichier.

---

## Documentation

```bash
# Générer la documentation Sphinx
cd docs && make html
```

Les docstrings suivent le format [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).

---

## Checklist avant une Pull Request

- [ ] `uv run inv lint` passe à zéro
- [ ] `uv run inv test` passe à zéro
- [ ] Les nouvelles fonctions publiques ont des type hints et une docstring
- [ ] Aucune valeur hardcodée (URL, clé, chemin absolu)
- [ ] `.env.example` mis à jour si de nouvelles variables ont été ajoutées
- [ ] Le CHANGELOG ou les notes de commit reflètent les changements
