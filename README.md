# okf_converter

A short description of the project.

## Auteur

- [@mattdav](https://github.com/mattdav)

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

---

## Présentation

<!-- Décrivez ici l'objectif du projet, le problème qu'il résout et son contexte. -->

---

## Installation

### Prérequis

- Python 3.10
- [uv](https://docs.astral.sh/uv/)

### Mise en place

```bash
# Cloner le dépôt
git clone <url-du-repo>
cd okf_converter

# Installer les dépendances
uv sync

# Configurer les variables d'environnement
cp .env.example .env
# Éditer .env avec les valeurs réelles
```

---

## Configuration

Ce projet utilise [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
pour gérer la configuration. Toutes les valeurs sensibles ou dépendantes de l'environnement
sont chargées depuis le fichier `.env`.

Copier `.env.example` en `.env` et renseigner les valeurs :

```bash
cp .env.example .env
```

> ⚠️ Ne jamais commiter le fichier `.env`. Il est dans `.gitignore`.

---

## Utilisation

```bash
# Lancer le programme principal
uv run python -m okf_converter

# Lister les tâches disponibles
uv run inv --list
```

---

## Développement

```bash
# Vérifier la qualité du code (ruff + mypy)
uv run inv lint

# Lancer les tests
uv run inv test

# Nettoyer les artefacts
uv run inv clean
```

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour les conventions de contribution.

---

## Structure du projet

```
okf_converter/
├── src/
│   └── okf_converter/
│       ├── bin/             ← scripts exécutables
│       ├── config/          ← configuration (pydantic-settings)
│       ├── data/            ← accès et traitement des données
│       ├── log/             ← configuration du logging
│       ├── __init__.py
│       └── __main__.py      ← point d'entrée
├── tests/
│   ├── unit/
│   └── conftest.py
├── docs/                    ← documentation Sphinx
├── .env.example             ← template des variables d'environnement
├── tasks.py                 ← tâches invoke
└── pyproject.toml
```

---

## Licence

[MIT license](LICENSE)
