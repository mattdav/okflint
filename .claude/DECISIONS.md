---
type: ProjectJournal
project: okflint
updated: 2026-08-27
tags: [python]
---

# Décisions d'architecture

Historique des décisions techniques et de leurs raisons. Une décision non
écrite est une décision perdue : documenter même les choix triviaux
("outil déjà maîtrisé", "cohérence avec l'existant").

**Plafond : ~150 lignes.** Au-delà, les entrées les plus anciennes basculent
dans `.claude/DECISIONS-archive.md` (archive froide, non importée dans
`CLAUDE.md`, consultée uniquement à la demande).

Ce fichier est importé dans `CLAUDE.md` via `@.claude/DECISIONS.md` : il est
donc chargé automatiquement dans le contexte de chaque session.

---

## 2026-06-28 — run_audit accepte list[Path] | Path pour bundle_paths et vault_paths (union de types pour rétrocompatibilité)

**Rationale :** Le test existant test_run_audit_smoke appelle run_audit(bundle, bundle) avec des Path singuliers — ne peut pas être modifié. L'union de types permet de supporter l'ancien appel sans toucher aux tests.

## 2026-06-28 — La logique de résolution manifest/bundle/vault appartient à _cmd_audit (cli.py), pas à run_audit (audit.py)

**Rationale :** Invariant architectural explicite : run_audit est une fonction pure sans effet sur les args CLI.

### 2026-08-28 — manifest_okflint.yaml n'importe pas le type WikiPage du template

**Rationale :** okflint n'a aucune fonctionnalité wiki/ingestion — vérifié par grep exhaustif, seuls des wikilinks Obsidian existent dans le code. Importer WikiPage aurait été du scaffolding spéculatif.

### 2026-08-28 — Les pages API Sphinx sont générées automatiquement (sphinx-apidoc via hook builder-inited dans conf.py) plutôt que hand-written et committées

**Rationale :** CI invoque sphinx-build directement, en contournant toute génération qui ne dépendrait que de `inv docs` — le hook garantit qu'aucun build ne publie une doc API amputée. Vérifié que les docstrings de modules contiennent déjà une information équivalente ou supérieure aux .rst manuscrits supprimés.

### 2026-08-28 — cruft link utilise des overrides de contexte explicites (_python_version=3.12, use_wiki=no) plutôt que les défauts du template (3.13, no par défaut)

**Rationale :** Le contexte cruft doit refléter l'identité réelle du projet pour que les futurs `cruft update` calculent des diffs corrects — _python_version doit matcher requires-python/mypy réels, use_wiki doit rester cohérent avec l'exclusion de WikiPage.
