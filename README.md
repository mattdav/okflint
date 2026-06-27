# okflint

**Le Ruff de la documentation.** Un linter de conformité déterministe pour bases
documentaires au format [Open Knowledge Format (OKF)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](https://choosealicense.com/licenses/mit/)
![Python](https://img.shields.io/badge/python-3.12+-3670A0?style=flat&logo=python&logoColor=ffdd54)

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

## Concepts clés

| Terme | Définition |
|---|---|
| **bundle** | Le dossier racine de la base documentaire à auditer ou valider. Tous les fichiers `.md` qu'il contient (récursivement) sont analysés. |
| **vault** | Le dossier racine de l'ensemble de vos Markdown (qui peut être plus grand que le bundle). Sert uniquement à résoudre les wikilinks `[[...]]` : un lien est considéré valide si la cible existe quelque part dans la vault, même hors du bundle. Si vous n'utilisez pas les wikilinks Obsidian, passez le même chemin que le bundle. |
| **manifest** | Le fichier `okf-base.yaml` que vous rédigez pour décrire votre standard : quels types de concepts vous utilisez, quels champs sont requis, quel vocabulaire de statut. Voir `okf-base.example.yaml` pour un modèle commenté. |
| **target** | Pour `validate` uniquement : un ou plusieurs chemins vers des dossiers ou des fichiers `.md` à valider. Si vous passez un dossier, tous les `.md` qu'il contient (récursivement) sont validés. Si vous passez un fichier, seul ce fichier est validé. |

---

## Utilisation

### `okflint audit` — Inventaire et diagnostic

`audit` scanne un bundle et produit un rapport descriptif : statistiques de conformité OKF, wikilinks cassés, liens markdown cassés, candidats au découpage. Cette commande est **toujours exit 0** — c'est un outil d'observation, pas un gate.

```bash
# Rapport en console (dry-run)
okflint audit --bundle /chemin/vers/ma-base --vault /chemin/vers/ma-vault

# Écrire le rapport JSON complet dans .okflint/ (rapport daté auto-incrémenté)
okflint audit --bundle /chemin/vers/ma-base --vault /chemin/vers/ma-vault --apply
```

**Options :**

| Option | Requis | Description |
|---|---|---|
| `--bundle <chemin>` | oui | Dossier racine de la base à auditer |
| `--vault <chemin>` | oui | Dossier racine de la vault pour la résolution des wikilinks |
| `--apply` | non | Écrit le rapport JSON complet dans `.okflint/YYYY-MM-DD_audit_vN.json` |

**Exemple concret — vault Obsidian :**
```bash
okflint audit \
  --bundle ~/Obsidian/Mon-projet/docs \
  --vault ~/Obsidian \
  --apply
# Produit : .okflint/2026-06-27_audit_v1.json
```

**Exemple concret — bundle = vault (pas de wikilinks) :**
```bash
okflint audit --bundle ./docs --vault ./docs
```

---

### `okflint validate` — Gate de conformité

`validate` vérifie la conformité de fichiers Markdown à OKF et au profil déclaré dans votre manifeste. Retourne **exit 0** si aucune erreur, **exit 1** sinon. Conçu pour les pre-commit hooks et la CI.

```bash
# Valider toute une base
okflint validate --manifest okf-base.yaml /chemin/vers/ma-base

# Valider un seul sous-dossier
okflint validate --manifest okf-base.yaml /chemin/vers/ma-base/ADR

# Valider des fichiers précis
okflint validate --manifest okf-base.yaml concept1.md concept2.md

# Sortie JSON machine-readable (pour CI, scripts)
okflint validate --manifest okf-base.yaml --json /chemin/vers/ma-base
```

**Options :**

| Option | Requis | Défaut | Description |
|---|---|---|---|
| `--manifest <chemin>` | non | `okf-base.yaml` | Chemin du manifeste OKF |
| `--json` | non | — | Sortie JSON au lieu du texte lisible |
| `<targets...>` | oui | — | Un ou plusieurs chemins (dossiers ou fichiers `.md`) à valider |

**Codes de sortie :**

| Code | Signification |
|---|---|
| `0` | Aucune erreur (des warnings peuvent subsister) |
| `1` | Au moins une erreur de conformité |
| `2` | Manifeste invalide ou illisible |

**Exemple concret — intégration CI GitHub Actions :**
```yaml
- name: Validate docs
  run: |
    pip install okflint
    okflint validate --manifest docs/okf-base.yaml docs/
```

**Exemple concret — pre-commit hook git :**
```bash
# .git/hooks/pre-commit
okflint validate --manifest okf-base.yaml docs/ || exit 1
```

---

## Développement

```bash
inv lint     # ruff + mypy
inv clean    # nettoyer les artefacts
inv repomix  # packer la codebase pour un LLM
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

Manifeste de la validation : `manifest.py` (chargement + validation du contrat).

---

## Roadmap

Les évolutions envisagées au-delà de la v0.1 (cohésion sémantique pour un
découpage plus fin, attendus de grille de lecture vérifiables) sont décrites dans
[ROADMAP.md](ROADMAP.md).

---

## Ce qu'okflint ne fait pas

okflint est un **gate statique et déterministe**. Par principe, il ne fera jamais :

- **Exécuter un parcours de lecture** pour un agent — c'est le rôle du harness.
- **Juger le contenu** d'un concept par LLM (résumer, classer, réécrire).
- **Décider** d'un découpage ou d'une réorganisation — il signale, ne tranche pas.
- **Imposer une convention** non déclarée par votre manifeste — pas de vocabulaire
  en dur, pas de langue imposée.

---

## Licence

[MIT](LICENSE) — [@mattdav](https://github.com/mattdav)
