# Changelog

Toutes les modifications notables d'okflint sont documentées dans ce fichier.

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).
Versioning : [Semantic Versioning](https://semver.org/lang/fr/).

Ce fichier est maintenu automatiquement par [commitizen](https://commitizen-tools.github.io/commitizen/).
Ne pas modifier manuellement les sections générées.

---

## v0.1.0 (2026-06-27)

### Nouvelles fonctionnalités

- CLI unifiée `okflint audit | validate`
- Validation en 3 étages : cœur OKF (§9), profil (manifeste), hygiène (opt-in)
- 18 règles cataloguées dans `config/RULES.md`
- Moteur générique piloté par un manifeste YAML (`okf-base.yaml`)
- Validation du manifeste lui-même (`manifest.py`)
- Support des wikilinks Obsidian (audit + résolution de liens)
- Couverture de tests à 93%
- Documentation Sphinx auto-générée
