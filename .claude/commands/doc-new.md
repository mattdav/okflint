---
type: Command
description: Crée un nouveau document (spec, fix ou plan) depuis son modèle
argument-hint: <spec|fix|plan> <nom-court-en-kebab-case>
---

# Nouveau document

Crée un nouveau document documentaire à partir de `$ARGUMENTS`.

Le premier mot de `$ARGUMENTS` est le type (`spec`, `fix` ou `plan`), le
second est un nom court en kebab-case pour le fichier.

Déroule ces étapes, dans l'ordre, sans en sauter aucune :

1. **Résous le type vers son dossier et son modèle.** Le mapping est fixe,
   ne le devine pas autrement :
   - `spec` → dossier `docs/specs/`, modèle `docs/_templates/spec.md`,
     préfixe d'id `SPEC-`
   - `fix` → dossier `docs/fixes/`, modèle `docs/_templates/fix.md`,
     préfixe d'id `FIX-`
   - `plan` → dossier `docs/plans/`, modèle `docs/_templates/plan.md`,
     préfixe d'id `PLAN-`

   Si le type n'est aucun de ces trois, arrête-toi et demande une
   clarification plutôt que de deviner.

2. **Lis le modèle** correspondant dans `docs/_templates/` intégralement.

3. **Détermine le premier id libre** dans le dossier cible : liste les
   fichiers existants `<PREFIX>-<n>_*.md`, prends le plus grand `n` observé
   et utilise `n + 1` (ou `1` si le dossier est vide, hors `.gitkeep`).

4. **Écris le nouveau fichier** `docs/<dossier>/<PREFIX>-<n>_<nom-court>.md`
   en copiant le modèle tel quel, en ne renseignant que :
   - `id` : `<PREFIX>-<n>`
   - `timestamp` : date et heure courantes au format ISO 8601
   - `status` : `draft`

   N'invente rien dans les autres champs du frontmatter ni dans le corps du
   document (`title`, `description`, sections `## Objectif`, `## Symptôme`,
   `## Périmètre`, etc. restent tels que dans le modèle, à charge de
   l'utilisateur de les compléter).

5. **Confirme** le chemin du fichier créé.
