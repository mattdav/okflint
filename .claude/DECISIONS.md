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
