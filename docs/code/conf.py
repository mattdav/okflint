"""Sphinx configuration for okflint documentation."""

from __future__ import annotations

import sys
from pathlib import Path

from sphinx.application import Sphinx

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

project = "okflint"
author = "Matthieu Daviaud"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx.ext.intersphinx",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}

napoleon_google_docstring = True
napoleon_numpy_docstring = False

html_theme = "sphinx_rtd_theme"

templates_path = ["_templates"]
exclude_patterns = ["_build"]


# -- API page generation ------------------------------------------------
#
# `docs/code/api/` is generated, so it is not versioned (see .gitignore). If
# generation only ran from `inv docs`, CI — which invokes `sphinx-build`
# directly — would publish an API doc amputated of everything, without
# failing. Hooking generation on the `builder-inited` event guarantees every
# build triggers it, wherever it comes from. This is also why `inv docs` no
# longer calls `sphinx-apidoc` itself: one single source of truth.


def _run_apidoc(app: Sphinx) -> None:
    """Generate the API pages before every build, locally and in CI."""
    from sphinx.ext.apidoc import main

    package = Path(__file__).parent.parent.parent / "src" / "okflint"
    output = Path(__file__).parent / "api"
    main(["--force", "--separate", "--module-first", "-o", str(output), str(package)])


def setup(app: Sphinx) -> None:
    """Register API generation on the `builder-inited` event."""
    app.connect("builder-inited", _run_apidoc)
