---
type: ProjectStandards
project: okflint
updated: 2026-07-03
tags: [python, cli, linter, okf, open-source]
---

# okflint

Deterministic compliance linter for OKF (Open Knowledge Format) documentary bases.
Verifies that a Markdown base conforms to OKF and to the framework declared in its
manifest. No LLM, no runtime state: a reproducible gate, Ruff-style.

## Structure

```
src/okflint/
├── cli.py        ← CLI dispatcher: okflint audit | validate | index
├── scanner.py    ← shared primitives (scan, frontmatter, code-fence, links)
├── audit.py      ← audit command (descriptive, always exit 0)
├── validate.py   ← validate command (normative gate, exit 0/1)
├── index.py      ← index command (OKF §6 index.md generation, dry-run default)
├── manifest.py   ← manifest loading + self-validation
├── __init__.py
├── __main__.py   ← python -m okflint
└── py.typed      ← PEP 561 marker (typed package)
```

## Commands

- `inv lint` — ruff check --fix + ruff format + mypy. Must pass with zero issues.
- `inv test` — pytest with coverage.
- `inv repomix` — pack the codebase as a dated XML in `.repomix/` for an LLM.
- `inv index` — index the codebase in codebase-memory-mcp (improves Claude Code context).
- `inv release [--part=patch|minor|major] [--dry-run]` — bump version + push + trigger CI/CD.
- `uv build` — build sdist + wheel in `dist/`.
- `okflint audit --bundle <dir> --vault <dir> [--apply]` — descriptive audit.
- `okflint validate --manifest <okf-base.yaml> <targets...>` — compliance gate.
- `okflint index --manifest <okf-base.yaml> [--apply]` — OKF §6 index.md generation (dry-run by default).

## Architecture

Validation in **3 stages** (full catalogue in `config/RULES.md`):
1. **OKF core** — hardcoded, the §9 compliance clause of the spec (F001, F002, R001, R002).
2. **Profile** — manifest-driven, type-aware rules for the base (F101, F102, F105, F106, S102).
3. **Hygiene** — opt-in, stricter than OKF, as warnings (L001-L003, S202, R201, F201).

The engine is **generic**: no type vocabulary is hardcoded. Everything
(types, fields, controlled vocabularies) lives in the `okf-base.yaml` manifest.
`manifest.py` validates the manifest itself before applying it.

Doctrine: **deterministic first, never LLM in the engine.** What requires
judgment (splitting, rewriting, routing) belongs to the consumer of the base, not the
linter. See `docs/project/ROADMAP.md` for the okflint / harness boundary.

## Notable dependencies

- **Runtime**: `pyyaml` (sole production dependency).
- **Dev**: `ruff`, `mypy` (lint), `pytest` + `pytest-cov` (tests), `invoke` (tasks).
- **Build**: `hatchling` (>= 1.26 for SPDX licence syntax).

## Conventions

- `uv run` exclusively (never direct `python`/`pip`).
- Strict type hints (`mypy strict`). Google-format docstrings on public functions.
- Comments in English, code in English.
- No environment-specific hardcoded values in the package code
  (bundle/vault paths are CLI arguments, not constants).

## Progress tracking

- Read `.claude/progress.log` at the start of a session if the file exists.
- Update `.claude/progress.log` at the end of a task.
