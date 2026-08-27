---
type: ProjectStandards
project: okflint
updated: 2026-08-27
tags: [python, cli, linter, okf, open-source]
---

# okflint

Deterministic compliance linter for OKF (Open Knowledge Format) documentary bases.
Verifies that a Markdown base conforms to OKF and to the framework declared in its
manifest. No LLM, no runtime state: a reproducible gate, Ruff-style.

## Structure

```text
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

- `uv run inv lint` — delegates to `pre-commit run --all-files` (ruff+mypy on the
  Python, markdownlint-cli2 on the Markdown, prettier on JSON/YAML — disjoint
  scopes, each tool is sole owner of its file type). Must pass with zero issues.
- `uv run inv test` — pytest with coverage.
- `uv run inv build` — build the package (wheel + sdist) via uv.
- `uv run inv docs` — build the Sphinx documentation as HTML.
- `uv run inv release [--part=patch|minor|major] [--dry-run]` — bump version + push + trigger CI/CD.
- `uv run inv repomix` — pack the codebase as a dated XML in `.repomix/` for an LLM.
- `uv run inv index` — index the codebase in codebase-memory-mcp (improves Claude Code context).
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

- **Runtime**: `pyyaml`, `beartype`.
- **Dev**: `ruff`, `mypy` (lint), `pytest` + `pytest-cov` (tests), `invoke` (tasks).
- **Build**: `hatchling` (>= 1.26 for SPDX licence syntax).

## Conventions

- `uv run` exclusively (never direct `python`/`pip`).
- Strict type hints (`mypy strict`). Google-format docstrings on public functions.
- Comments in English, code in English, documentation in English.
- No environment-specific hardcoded values in the package code
  (bundle/vault paths are CLI arguments, not constants).

## Project memory

- `.claude/progress.log` is versioned and strictly append-only: only add
  entries at the end, never rewrite or delete an existing one.
- `.claude/DECISIONS.md` has a cap of about 150 lines: beyond that, the
  oldest entries move to `.claude/DECISIONS-archive.md`, which is not
  imported below (cold archive, consulted only on request).

@.claude/DECISIONS.md
@.claude/LESSONS.md
