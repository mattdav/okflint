# Log — Journal structurel du bundle okflint

## 2026-07-05

**Mise en conformité OKF du bundle.**

Retrait de `.claude/**` des `exclude_patterns` du manifeste (exclusion trop large,
issue d'une confusion avec le `.gitignore`) : `.claude/DECISIONS.md` est désormais
indexé et conforme au type `ProjectJournal`. Génération des `index.md` du bundle
(racine et sous-dossiers) via `okflint index --apply`. Création de ce `log.md`.
