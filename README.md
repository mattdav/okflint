# okflint

**Le Ruff de la documentation.** Un linter de conformité déterministe pour bases
documentaires au format [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
![Python](https://img.shields.io/badge/python-3.10+-3670A0?style=flat&logo=python&logoColor=ffdd54)

---

## Pourquoi

Quand la valeur d'un projet migre vers sa base documentaire, cette base doit être
tenue à un standard — comme le code l'est par un linter. `okflint` vérifie, de
façon **déterministe, reproductible et sans LLM**, que des documents Markdown
respectent un standard OKF déclaré dans un manifeste YAML.

Deux commandes :

- **`okflint audit`** — inventaire et diagnostic descriptif d'une base (statistiques,
  liens cassés, candidats au découpage). Toujours `exit 0`.
- **`okflint validate`** — gate normatif de conformité. `exit 0` si conforme,
  `exit 1` sinon. Conçu pour les pre-commit hooks et la CI.

---

## Installation

```bash
# Via uv (recommandé)
uv tool install okflint

# Ou via pip
pip install okflint
```

Pour le développement :

```bash
git clone https://github.com/mattdav/okflint
cd okflint
uv sync --all-extras
uv pip install -e .
```

---

## Démarrage rapide

1. Copiez le manifeste d'exemple à la racine de votre base documentaire :

```bash
cp okf-base.example.yaml /chemin/vers/ma-base/okf-base.yaml
```

2. Adaptez-le à votre taxonomie (types, champs requis, vocabulaire de statut).

3. Validez :

```bash
okflint validate --manifest /chemin/vers/ma-base/okf-base.yaml /chemin/vers/ma-base
```

---

## Le manifeste

`okflint` est un **moteur générique** : il ne connaît aucun vocabulaire de types en
dur. C'est le manifeste `okf-base.yaml` qui définit votre standard. Voir
[`okf-base.example.yaml`](okf-base.example.yaml) pour un modèle commenté.

Chaque type déclare ses champs requis/optionnels et sa politique de statut :

| `statut_values` | Sémantique |
|---|---|
| `[liste]` | champ `statut` **requis**, valeur contrainte à la liste |
| `false` | champ `statut` **interdit** pour ce type |
| `null` (ou absent) | champ `statut` **optionnel**, valeur libre |

---

## Utilisation

### Audit

```bash
# Inventaire descriptif (stats terminal)
okflint audit --bundle /chemin/bundle --vault /chemin/vault

# Écrire le rapport JSON dans outputs/
okflint audit --bundle /chemin/bundle --vault /chemin/vault --apply
```

### Validation

```bash
# Valider un dossier (exit 0/1)
okflint validate --manifest okf-base.yaml /chemin/dossier

# Valider des fichiers précis
okflint validate --manifest okf-base.yaml fichier1.md fichier2.md

# Sortie JSON (pour CI)
okflint validate --manifest okf-base.yaml --json /chemin/dossier
```

---

## Développement

```bash
uv run inv lint     # ruff + mypy
uv run inv clean    # nettoyer les artefacts
uv run inv repomix  # packer la codebase pour un LLM
```

Voir [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Architecture

```
src/okflint/
├── cli.py        ← dispatcher : okflint audit | validate
├── scanner.py    ← primitives partagées (scan, frontmatter, liens)
├── audit.py      ← commande audit (descriptive)
├── validate.py   ← commande validate (gate normatif)
└── __main__.py   ← python -m okflint
```

---

## Licence

[MIT](LICENSE) — [@mattdav](https://github.com/mattdav)
