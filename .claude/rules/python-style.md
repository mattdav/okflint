---
type: ProjectStandards
project: okflint
updated: 2026-08-27
tags: [python]
---

# Style Python

Règles observables dans ce projet (`pyproject.toml`, `.pre-commit-config.yaml`,
`CONTRIBUTING.md`) — à respecter pour tout code écrit ou modifié sous `src/`.

## Structure du package

```text
src/okflint/
├── cli.py        ← dispatcher CLI : okflint audit | validate | index
├── scanner.py    ← primitives partagées (scan, frontmatter, code-fence, links)
├── audit.py      ← commande audit (descriptive, exit 0 toujours)
├── validate.py   ← commande validate (gate normatif, exit 0/1)
├── index.py      ← commande index (génération OKF §6 index.md)
├── manifest.py   ← chargement + auto-validation du manifeste
├── __init__.py
├── __main__.py   ← python -m okflint
└── py.typed      ← marqueur PEP 561 (paquet typé)
```

okflint est un moteur **générique** : aucun vocabulaire de type n'est
hardcodé, tout vient du manifeste `okf-base.yaml`.

## Qualité

- Type hints obligatoires sur toutes les fonctions et méthodes publiques.
- Docstrings au format Google sur toutes les fonctions et méthodes publiques.
- Aucun `# noqa` ni `# type: ignore` sans commentaire justificatif sur la
  même ligne.
- Éviter `Any` sauf cas justifié.
- Toute fonction publique (non préfixée `_`) est décorée `@beartype`.

## Configuration

- Aucune valeur environnement-spécifique hardcodée dans le paquet (les
  chemins bundle/vault sont des arguments CLI, jamais des constantes).

## Lint

`uv run inv lint` délègue entièrement à `pre-commit run --all-files` (source
unique de vérité, voir `tasks.py` et `.pre-commit-config.yaml`) :

- `ruff check --fix` puis `ruff format` sur `src/`, `tests/`, `tasks.py`.
- `mypy` en mode strict sur `src/`, `tests/`, `tasks.py`.
- `markdownlint-cli2` et `prettier` sur les fichiers Markdown/YAML/JSON.

Cette commande doit passer à zéro avant tout commit.

## Tests

- Un fichier de test par module : `tests/test_<module>.py`.
- Fixtures partagées dans `tests/conftest.py`.
- Nommage explicite : `test_<fonction>_<scenario>_<resultat_attendu>`.
