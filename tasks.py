import shutil
import subprocess
from pathlib import Path

from invoke import Context, task

# ================ Config ================= #
RELEASE_BRANCH = "main"  # reference branch for releases
CLEAN_DIRS: list[str] = [
    "build",  # Build artefacts
    "dist",  # Packaged distributions
    ".pytest_cache",  # pytest cache
    ".ruff_cache",  # Ruff cache
    ".mypy_cache",  # mypy cache
    ".okflint",  # JSON audit reports (regeneratable)
    "htmlcov",  # HTML coverage report
    "__pycache__",  # Python cache (root)
]

CLEAN_FILES: list[str] = [
    ".coverage",  # pytest-cov coverage data
]


# ================ Helper Functions ================= #
@task
def clean(c: Context) -> None:
    """Remove build artifacts and caches."""
    for directory in CLEAN_DIRS:
        path: Path = Path(directory)
        if path.exists():
            print(f"  - Removing {directory}")
            shutil.rmtree(path, ignore_errors=True)

    for filename in CLEAN_FILES:
        path = Path(filename)
        if path.exists():
            print(f"  - Removing {filename}")
            path.unlink(missing_ok=True)

    # Recursively clean __pycache__
    for path in Path(".").rglob("__pycache__"):
        print(f"  - Removing {path}")
        shutil.rmtree(path, ignore_errors=True)

    # Clean *.egg-info
    for path in Path(".").rglob("*.egg-info"):
        print(f"  - Removing {path}")
        shutil.rmtree(path, ignore_errors=True)

    # Clean .pyc files
    for path in Path(".").rglob("*.pyc"):
        print(f"  - Removing {path}")
        path.unlink(missing_ok=True)

    print("🗑 Clean task Done!")


# ================ Quality test ================= #
@task
def index(c: Context) -> None:
    """Index the codebase in codebase-memory-mcp to improve Claude Code context.

    Uses the CLI mode of the codebase-memory-mcp binary to index the current
    project into the persistent knowledge graph. The index survives session
    restarts and allows Claude Code to make structural queries
    (call graph, dependencies, etc.) with ~99% fewer tokens than a file-by-file
    exploration.

    Re-run after every significant change to the codebase.
    """
    import json

    binary = Path(
        r"C:\Users\matth\AppData\Local\Programs\codebase-memory-mcp\codebase-memory-mcp.exe"
    )
    if not binary.exists():
        print(f"❌ codebase-memory-mcp binary not found: {binary}")
        print("   Install from: https://github.com/DeusData/codebase-memory-mcp")
        return

    repo_path = str(Path.cwd()).replace("\\", "/")
    payload = json.dumps({"repo_path": repo_path})

    print("🧠 Indexing codebase in codebase-memory-mcp...")
    print(f"   Project: {repo_path}")
    result = subprocess.run(
        [str(binary), "cli", "index_repository", payload],
        shell=False,
    )
    if result.returncode == 0:
        print("✅ Index updated. Claude Code can now query the knowledge graph.")
    else:
        print("❌ Indexing failed.")


@task
def lint(c: Context) -> None:
    """Run linting checks."""
    result = 0
    print("Running Ruff check...")
    check_command = subprocess.run("uv run ruff check --fix src/.", shell=True)
    if check_command.returncode != 0:
        result += check_command.returncode
    print("\nRunning Ruff format check...")
    format_command = subprocess.run("uv run ruff format src/.", shell=True)
    if format_command.returncode != 0:
        result += format_command.returncode
    print("\nRunning mypy...")
    # uv run mypy fails on Windows with compiled mypy (Failed to canonicalize script path)
    # Using python -m mypy as a workaround
    mypy_command = subprocess.run("uv run python -m mypy src/.", shell=True)
    if mypy_command.returncode != 0:
        result += mypy_command.returncode
    if result != 0:
        print("❌ Linting issues found!")
    else:
        print("🔎 Linting Task Done!")


@task
def test(c: Context, verbose: bool = False, coverage: bool = True) -> None:
    """Run the pytest test suite."""
    print("🧪 Running test suite...")

    # Build the command
    cmd = "uv run python -m pytest"
    if verbose:
        cmd += " -v"
    if not coverage:
        # pyproject.toml enables coverage by default via addopts
        cmd += " --no-cov"

    # Execute
    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        print("❌ Tests failed!")
    else:
        print("✅ All tests passed!")
        html_report = Path("htmlcov") / "index.html"
        if html_report.exists():
            print(f"📊 HTML report: {html_report.resolve()}")


@task
def docs(c: Context, open_browser: bool = False) -> None:
    """Build the Sphinx documentation as HTML."""
    src = Path("docs/sphinx")
    out = src / "_build" / "html"
    out.mkdir(parents=True, exist_ok=True)

    print("📖 Building Sphinx documentation...")
    result = subprocess.run(
        f'uv run sphinx-build -b html "{src}" "{out}"',
        shell=True,
    )
    if result.returncode != 0:
        print("❌ Sphinx build failed!")
        return

    index_html = out / "index.html"
    print(f"✅ Documentation built: {index_html.resolve()}")

    # Optionally open in browser
    if open_browser:
        import webbrowser

        webbrowser.open(index_html.as_uri())


@task
def release(
    c: Context,
    part: str = "patch",
    dry_run: bool = False,
    skip_tests: bool = False,
) -> None:
    """Orchestrate a release: bump version, changelog, commit, tag, push.

    Sequence:
      1. Verify we are on the main branch with a clean working tree
      2. Run lint + tests (safety before publishing) — unless --skip-tests
      3. Bump the version via commitizen (patch | minor | major)
      4. Create a release commit + a signed vX.Y.Z tag
      5. Push the commit AND the tag to origin/main
      6. The tag automatically triggers the GitHub Actions release.yml workflow
         which builds, publishes to PyPI, and creates the GitHub Release.

    Usage:
        inv release                  # bump patch (0.1.0 → 0.1.1)
        inv release --part=minor     # bump minor (0.1.0 → 0.2.0)
        inv release --part=major     # bump major (0.1.0 → 1.0.0)
        inv release --dry-run        # simulate without modifying anything
        inv release --skip-tests     # for local development only
    """

    def _run(cmd: str, check: bool = True) -> int:
        """Execute a shell command, display the result, return the exit code."""
        if dry_run:
            print(f"[dry-run] {cmd}")
            return 0
        result = subprocess.run(cmd, shell=True)
        if check and result.returncode != 0:
            print(f"\n\u274c Failed: {cmd}")
            raise SystemExit(result.returncode)
        return result.returncode

    print("\n🔍 Release workflow")
    print(f"  Bump type  : {part}")
    print(f"  Dry run    : {dry_run}")
    print(f"  Branch     : {RELEASE_BRANCH}")

    # ── Step 0: pre-flight checks ─────────────────────────────────────────────
    print("\n📦 Step 1/5: pre-flight checks...")

    # Current branch
    current_branch = subprocess.run(
        "git rev-parse --abbrev-ref HEAD", shell=True, capture_output=True, text=True
    ).stdout.strip()
    if not dry_run and current_branch != RELEASE_BRANCH:
        print(f"❌ You are on '{current_branch}', not on '{RELEASE_BRANCH}'.")
        print("   Run 'git checkout main' before releasing.")
        raise SystemExit(1)

    # Clean working tree
    dirty = subprocess.run(
        "git status --porcelain", shell=True, capture_output=True, text=True
    ).stdout.strip()
    if not dry_run and dirty:
        print("❌ Working tree is not clean. Commit or stash first.")
        print(dirty)
        raise SystemExit(1)

    print("✅ Branch and working tree OK")

    # ── Step 1: lint + tests ──────────────────────────────────────────────────
    if not skip_tests:
        print("\n📦 Step 2/5: lint + tests...")
        _run("uv run ruff check src/")
        _run("uv run ruff format --check src/")
        _run("uv run python -m mypy src/")
        _run("uv run python -m pytest --cov=src/okflint --cov-fail-under=85 -q")
        print("✅ Lint and tests OK")
    else:
        print("\n⚠️  Step 2/5: lint + tests skipped (--skip-tests)")

    # ── Step 2: bump version + changelog ─────────────────────────────────────
    print(f"\n📦 Step 3/5: bump version ({part})...")
    bump_cmd = f"uv run cz bump --increment {part.upper()}"
    if dry_run:
        bump_cmd += " --dry-run"
        # cz bump --dry-run is itself non-destructive, so run it directly
        # instead of letting _run swallow it — this is what actually surfaces
        # the target version + changelog preview.
        preview = subprocess.run(bump_cmd, shell=True)
        if preview.returncode != 0:
            print(f"\n❌ Failed: {bump_cmd}")
            raise SystemExit(preview.returncode)
    else:
        _run(bump_cmd)
    print("✅ Version bumped + CHANGELOG.md updated")

    # Get the new version after the bump. In dry-run nothing was actually
    # bumped, so this is still the current version — don't mislabel it as new.
    new_version = subprocess.run(
        "uv run cz version --project", shell=True, capture_output=True, text=True
    ).stdout.strip()
    if not dry_run:
        print(f"   New version: {new_version}")

    # ── Step 3: push commit + tag ─────────────────────────────────────────────
    print("\n📦 Step 4/5: push commit + tag...")
    _run(f"git push origin {RELEASE_BRANCH}")
    _run(f"git push origin v{new_version}")
    print("✅ Commit + tag pushed")

    # ── Step 4: summary ───────────────────────────────────────────────────────
    print("\n📦 Step 5/5: summary...")
    print(f"🎉 Release v{new_version} launched!")
    print("   → GitHub Actions release.yml will build and publish to PyPI")
    print("   → Follow at: https://github.com/mattdav/okflint/actions")
    if not dry_run:
        print(f"   → PyPI: https://pypi.org/project/okflint/{new_version}/")
