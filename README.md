# okf_converter

Outillage Python d'OKF-ification d'une vault Obsidian selon la spec
[Open Knowledge Format v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

## Auteur

- [@mattdav](https://github.com/mattdav)

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

---

## Présentation

Outillage pour auditer et migrer un bundle Obsidian vers le format OKF v0.1.
Bundle cible : `Home Lab/` dans la vault Nextcloud.

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

### Audit d'un bundle

```bash
# Dry-run : affiche les stats dans le terminal
uv run okf-audit

# Écrire le rapport JSON dans outputs/
uv run okf-audit --apply

# Bundle et vault personnalisés
uv run okf-audit --bundle /chemin/bundle --vault /chemin/vault --apply
```

Le rapport est écrit dans `outputs/YYYY-MM-DD_audit_vN.json` (auto-incrémenté).

### Validation normative

```bash
# Valider un dossier (exit 0 si conforme, exit 1 sinon)
uv run okf-validate chemin/vers/dossier/

# Valider des fichiers spécifiques
uv run okf-validate fichier1.md fichier2.md

# Sortie JSON des erreurs
uv run okf-validate --json chemin/vers/dossier/

# Manifeste personnalisé (défaut : okf-base.yaml)
uv run okf-validate --manifest mon-manifeste.yaml chemin/
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
│       ├── bin/
│       │   ├── audit.py     ← okf-audit CLI
│       │   ├── scanner.py   ← primitives partagées de scan Markdown
│       │   └── validate.py  ← okf-validate CLI
│       ├── config/          ← configuration (pydantic-settings)
│       ├── log/             ← configuration du logging
│       └── __init__.py
├── okf-base.yaml            ← manifeste OKF du bundle Home Lab
├── tasks.py                 ← tâches invoke (lint, clean, repomix)
└── pyproject.toml
```

---

## Licence

[MIT license](LICENSE)
