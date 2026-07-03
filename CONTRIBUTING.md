---
type: ProjectStandards
project: okflint
updated: 2026-07-03
tags: [python, contributing]
---

# Contribution guide — okflint

> **Thank you for contributing to okflint. This document describes the conventions and
> processes to follow in order to maintain a consistent, high-quality codebase.**

---

## Development environment

### Prerequisites

- Python ≥ 3.10
- [uv](https://docs.astral.sh/uv/) — package manager
- [invoke](https://www.pyinvoke.org/) — task runner (installed via dev deps)

### Installation

```bash
git clone https://github.com/mattdav/okflint
cd okflint
uv sync --all-extras
uv pip install -e .
```

Verify everything works:

```bash
inv lint        # must pass with zero issues
inv test        # all tests must pass
uv run okflint --help
```

---

## Project architecture

```
src/okflint/
├── cli.py        ← CLI dispatcher: okflint audit | validate
├── scanner.py    ← shared primitives (scan, frontmatter, code-fence, links)
├── audit.py      ← audit command (descriptive)
├── validate.py   ← validate command (normative gate)
├── manifest.py   ← manifest loading + validation
├── __init__.py
├── __main__.py   ← python -m okflint
└── py.typed
```

okflint is a **generic engine**: no type vocabulary is hardcoded.
The entire standard of a base (types, fields, statuses) is declared in its
`okf-base.yaml` manifest. The catalogue of validation rules is documented in
[`config/RULES.md`](config/RULES.md) — this is the reference spec. Every new rule
must be documented there with its code, stage, and severity.

### Doctrine

- **Deterministic first.** The engine contains no LLM calls. A rule that
  requires judgment has no place in the core or the profile.
- **OKF honesty.** okflint distinguishes what is *truly* OKF (core, §9 of the
  spec) from what is a base convention (profile) or a stricter choice
  (hygiene). Never present a local convention as an OKF requirement.
- See [`ROADMAP.md`](docs/project/ROADMAP.md) for the boundary between okflint (static validation)
  and an agent harness (runtime orchestration).

---

## Code quality

### Tools

| Tool | Role |
|---|---|
| [ruff](https://docs.astral.sh/ruff/) | Linting and formatting |
| [mypy](https://mypy.readthedocs.io/) | Static type checking (strict mode) |

### Single command

```bash
inv lint        # must pass with zero issues
```

Runs in sequence: `ruff check --fix`, `ruff format`, `mypy`.
**Must pass with zero issues before any commit.**

### Strict rules

- No `# noqa` without a justification comment on the same line.
- No `# type: ignore` without a justification comment on the same line.
- Type hints required on all public functions and methods.
- Avoid `Any` except in justified cases.
- Comments in English, code (names, identifiers) in English.

### beartype

**All public functions** (not prefixed with `_`) must be decorated with `@beartype`.
This decorator validates types at runtime, complementing mypy (static).
Do not decorate private functions or invoke tasks (incompatible signature).

---

## Tests

```bash
inv test
```

### Conventions

- One test file per module: `tests/test_<module>.py`.
- Shared fixtures go in `tests/conftest.py`.
- Name tests explicitly: `test_<function>_<scenario>_<expected_result>`.
- Cover edge cases: missing frontmatter, invalid YAML, malformed manifest,
  forbidden status values, broken links vs external references.

### Fundamental rule

Each rule in the catalogue (`config/RULES.md`) must be covered by at least one test
that verifies it triggers on a non-conforming case and does not trigger on a
conforming case. Tests must never be deleted to make CI pass.

---

## Git workflow

### Branches

| Branch | Usage |
|---|---|
| `main` | Stable code, ready for release |
| `feat/<name>` | New feature |
| `fix/<name>` | Bug fix |
| `chore/<name>` | Maintenance, refactoring, CI |

### Commit format

```
feat: add S202 semantic cohesion rule
fix: correct exclude_patterns matching on nested roots
chore: update dependencies
docs: complete the rules catalogue
test: cover manifest parsing edge cases
```

Accepted types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.

### Before committing

```bash
inv lint   # must pass with zero issues
inv test   # all tests must pass
```

---

## Release process

### Prerequisites

- Be on the `main` branch with a clean working tree
- Have push rights on the repository
- Have configured the **Trusted Publisher** on pypi.org (GitHub repo Settings)

### Commit message format

okflint uses [commitizen](https://commitizen-tools.github.io/commitizen/) to
validate messages and automatically generate the CHANGELOG.

**Required format**:
```
<type>(<optional scope>): <description>
```

Accepted types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`, `perf`, `ci`, `build`, `style`.

Valid examples:
```
feat: add S202 semantic cohesion rule
fix(manifest): correct exclude_patterns matching on nested roots
docs: update README
chore: update dependencies
```

### Triggering a release

A single command launches the entire process:

```bash
inv release               # patch (0.1.0 → 0.1.1) — bug fixes
inv release --part=minor  # minor (0.1.0 → 0.2.0) — new features
inv release --part=major  # major (0.1.0 → 1.0.0) — breaking changes
inv release --dry-run     # simulation without modifying anything
```

**What `inv release` does:**
1. Verifies you are on `main` with a clean tree
2. Runs lint + tests (safety before publishing)
3. Bumps the version via commitizen + updates `CHANGELOG.md`
4. Creates a release commit + a `vX.Y.Z` tag
5. Pushes the commit AND the tag to `origin/main`
6. The tag automatically triggers the `release.yml` workflow which:
   - Builds sdist + wheel
   - Publishes to PyPI via Trusted Publisher
   - Creates the GitHub Release with auto-generated notes

### Trusted Publisher PyPI (one-time setup)

To allow `release.yml` to publish without a token:
1. Go to https://pypi.org/manage/account/publishing/
2. Add a Trusted Publisher:
   - Owner: `mattdav`
   - Repository: `okflint`
   - Workflow: `release.yml`
   - Environment: `pypi`

---

## Pull Request checklist

- [ ] `uv run inv lint` passes with zero issues
- [ ] `uv run inv test` passes with zero issues
- [ ] Every new rule is documented in `config/RULES.md` (code, stage, severity)
- [ ] Every new rule is covered by a test (conforming case + non-conforming case)
- [ ] New public functions have type hints and a Google docstring
- [ ] No environment-specific values are hardcoded in the package
