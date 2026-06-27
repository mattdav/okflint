import shutil
import subprocess
from datetime import date
from pathlib import Path

from invoke import Context, task

# ================ Config ================= #
RELEASE_BRANCH = "main"  # branche de référence pour les releases
CLEAN_DIRS: list[str] = [
    "build",          # Artéfacts de build
    "dist",           # Distributions packagées
    ".pytest_cache",  # Cache de pytest
    ".ruff_cache",    # Cache de Ruff
    ".mypy_cache",    # Cache de mypy
    ".okflint",       # Rapports d'audit JSON (régénérables)
    "htmlcov",        # Rapport de couverture HTML
    "__pycache__",    # Cache Python (racine)
]

CLEAN_FILES: list[str] = [
    ".coverage",  # Données de couverture pytest-cov
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

    # Nettoyer récursivement les __pycache__
    for path in Path(".").rglob("__pycache__"):
        print(f"  - Removing {path}")
        shutil.rmtree(path, ignore_errors=True)

    # Nettoyer les *.egg-info
    for path in Path(".").rglob("*.egg-info"):
        print(f"  - Removing {path}")
        shutil.rmtree(path, ignore_errors=True)

    # Nettoyer les fichiers .pyc
    for path in Path(".").rglob("*.pyc"):
        print(f"  - Removing {path}")
        path.unlink(missing_ok=True)

    print("🗑 Clean task Done!")


@task
def repomix(c: Context, output: str | None = None) -> None:
    """Pack la codebase en un fichier XML pour consommation LLM.

    Output par défaut : .repomix/YYYY-MM-DD_repomix_v<N>.xml (auto-incrémenté).
    Utiliser --output pour forcer un nom de fichier dans .repomix/.
    """
    outputs_dir: Path = Path(".repomix")
    outputs_dir.mkdir(exist_ok=True)

    if output is None:
        today: str = date.today().strftime("%Y-%m-%d")
        v: int = 1
        while (outputs_dir / f"{today}_repomix_v{v}.xml").exists():
            v += 1
        output_path: Path = outputs_dir / f"{today}_repomix_v{v}.xml"
    else:
        output_path = outputs_dir / output

    print(f"📦 Packing codebase to {output_path}...")
    result = subprocess.run(
        f'repomix --output "{output_path}"',
        shell=True,
    )
    if result.returncode == 0:
        print(f"✅ Repomix output saved to {output_path}")
    else:
        print("❌ Repomix failed!")


# ================ Quality test ================= #
@task
def index(c: Context) -> None:
    """Indexe la codebase dans codebase-memory-mcp pour améliorer le contexte Claude Code.

    Utilise le mode CLI du binaire codebase-memory-mcp pour indexer le projet
    courant dans le knowledge graph persistant. L'index survit aux redémarrages
    de session et permet à Claude Code de faire des requêtes structurelles
    (call graph, dépendances, etc.) avec ~99% moins de tokens qu'une exploration
    fichier par fichier.

    À relancer après chaque modification significative de la codebase.
    """
    import json

    binary = Path(
        r"C:\Users\matth\AppData\Local\Programs\codebase-memory-mcp\codebase-memory-mcp.exe"
    )
    if not binary.exists():
        print(f"❌ Binaire codebase-memory-mcp introuvable : {binary}")
        print("   Installer depuis : https://github.com/DeusData/codebase-memory-mcp")
        return

    repo_path = str(Path.cwd()).replace("\\", "/")
    payload = json.dumps({"repo_path": repo_path})

    print(f"🧠 Indexation de la codebase dans codebase-memory-mcp...")
    print(f"   Projet : {repo_path}")
    result = subprocess.run(
        f'"{binary}" cli index_repository \'{payload}\'',
        shell=True,
    )
    if result.returncode == 0:
        print("✅ Index mis à jour. Claude Code peut maintenant interroger le knowledge graph.")
    else:
        print("❌ Indexation échouée.")


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
    # uv run mypy échoue sur Windows avec mypy compilé (Failed to canonicalize script path)
    # On passe par python -m mypy pour contourner le problème
    mypy_command = subprocess.run("uv run python -m mypy src/.", shell=True)
    if mypy_command.returncode != 0:
        result += mypy_command.returncode
    if result != 0:
        print("❌ Linting issues found!")
    else:
        print("🔎 Linting Task Done!")


@task
def test(c: Context, verbose: bool = False, coverage: bool = True) -> None:
    """Lance la suite de tests pytest."""
    print("🧪 Running test suite...")

    # 🔎 Construction de la commande
    cmd = "uv run python -m pytest"
    if verbose:
        cmd += " -v"
    if not coverage:
        # pyproject.toml active la couverture par défaut via addopts
        cmd += " --no-cov"

    # 📦 Exécution
    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        print("❌ Tests failed!")
    else:
        print("✅ All tests passed!")
        html_report = Path("htmlcov") / "index.html"
        if html_report.exists():
            print(f"📊 HTML report : {html_report.resolve()}")


@task
def docs(c: Context, open_browser: bool = False) -> None:
    """Construit la documentation Sphinx en HTML."""
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
    print(f"✅ Documentation built : {index_html.resolve()}")

    # 🔎 Ouverture optionnelle dans le navigateur
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
    """Orchestre une release : bump version, changelog, commit, tag, push.

    Séquence :
      1. Vérifie qu'on est sur la branche main et que le working tree est propre
      2. Lance lint + tests (sécurité avant publication) — sauf si --skip-tests
      3. Bumpe la version via commitizen (patch | minor | major)
      4. Crée un commit de release + un tag signé vX.Y.Z
      5. Pousse le commit ET le tag vers origin/main
      6. Le tag déclenche automatiquement le workflow GitHub Actions release.yml
         qui build, publie sur PyPI, et crée la GitHub Release.

    Usage :
        inv release                  # bump patch (0.1.0 → 0.1.1)
        inv release --part=minor     # bump minor (0.1.0 → 0.2.0)
        inv release --part=major     # bump major (0.1.0 → 1.0.0)
        inv release --dry-run        # simule sans rien modifier
        inv release --skip-tests     # pour développer en local seulement
    """

    def _run(cmd: str, check: bool = True) -> int:
        """Exécute une commande shell, affiche le résultat, retourne le code de sortie."""
        if dry_run:
            print(f"[dry-run] {cmd}")
            return 0
        result = subprocess.run(cmd, shell=True)
        if check and result.returncode != 0:
            print(f"\n\u274c Échec : {cmd}")
            raise SystemExit(result.returncode)
        return result.returncode

    print("\n🔍 Release workflow")
    print(f"  Bump type  : {part}")
    print(f"  Dry run    : {dry_run}")
    print(f"  Branch     : {RELEASE_BRANCH}")

    # ── Étape 0 : vérifications préalables ───────────────────────────────────────
    print("\n📦 Étape 1/5 : vérifications...")

    # Branche courante
    current_branch = subprocess.run(
        "git rev-parse --abbrev-ref HEAD", shell=True, capture_output=True, text=True
    ).stdout.strip()
    if not dry_run and current_branch != RELEASE_BRANCH:
        print(f"❌ Vous êtes sur '{current_branch}', pas sur '{RELEASE_BRANCH}'.")
        print("   Faites 'git checkout main' avant de releaser.")
        raise SystemExit(1)

    # Working tree propre
    dirty = subprocess.run(
        "git status --porcelain", shell=True, capture_output=True, text=True
    ).stdout.strip()
    if not dry_run and dirty:
        print("❌ Le working tree n'est pas propre. Commitez ou stashez d'abord.")
        print(dirty)
        raise SystemExit(1)

    print("✅ Branche et working tree OK")

    # ── Étape 1 : lint + tests ───────────────────────────────────────────────
    if not skip_tests:
        print("\n📦 Étape 2/5 : lint + tests...")
        _run("uv run ruff check src/")
        _run("uv run ruff format --check src/")
        _run("uv run python -m mypy src/")
        _run("uv run python -m pytest --cov=src/okflint --cov-fail-under=85 -q")
        print("✅ Lint et tests OK")
    else:
        print("\n⚠️  Étape 2/5 : lint + tests ignorés (--skip-tests)")

    # ── Étape 2 : bump version + changelog ─────────────────────────────────
    print(f"\n📦 Étape 3/5 : bump version ({part})...")
    bump_cmd = f"uv run cz bump --increment {part.upper()}"
    if dry_run:
        bump_cmd += " --dry-run"
    _run(bump_cmd)
    print("✅ Version bumpée + CHANGELOG.md mis à jour")

    # Récupère la nouvelle version après le bump
    new_version = subprocess.run(
        "uv run cz version --project", shell=True, capture_output=True, text=True
    ).stdout.strip()
    print(f"   Nouvelle version : {new_version}")

    # ── Étape 3 : push commit + tag ──────────────────────────────────────────
    print("\n📦 Étape 4/5 : push commit + tag...")
    _run(f"git push origin {RELEASE_BRANCH}")
    _run(f"git push origin v{new_version}")
    print("✅ Commit + tag poussés")

    # ── Étape 4 : résumé ──────────────────────────────────────────────────
    print("\n📦 Étape 5/5 : résumé...")
    print(f"🎉 Release v{new_version} lancée !")
    print("   → GitHub Actions release.yml va builder et publier sur PyPI")
    print("   → Suivre sur : https://github.com/mattdav/okflint/actions")
    if not dry_run:
        print(f"   → PyPI : https://pypi.org/project/okflint/{new_version}/")
