# okf_converter

## Structure
- Package principal : src/okf_converter/
- Config : pyproject.toml

## Commandes
- `uv run inv lint` — ruff + mypy, doit passer à zéro
- `uv run inv build` — build du package
- `uv run inv repomix` — pack la codebase en XML dans `outputs/YYYY-MM-DD_repomix_v<N>.xml` pour consommation LLM (ignore via `.gitignore` + `.repomixignore`)

## Architecture
<!-- À compléter au démarrage du projet -->

## Dépendances notables
<!-- À compléter au démarrage du projet -->

## Suivi de progression
- Lire `claude-progress.txt` en début de session si le fichier existe
- Mettre à jour `claude-progress.txt` en fin de tâche