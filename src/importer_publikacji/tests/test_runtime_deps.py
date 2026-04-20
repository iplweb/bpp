"""Regression: production app-ready imports must stay in runtime deps.

`importer_publikacji.apps.ImporterPublikacjiConfig.ready()` imports
`providers.www` at Django app startup, which in turn does
`from bs4 import BeautifulSoup` at module import time. If `bs4`
lives only in the `dev` extra, `uv sync --frozen` on a production
image crashes before the process even serves a request (observed in
GitHub Actions build job on 2026-04-18 — `ModuleNotFoundError:
No module named 'bs4'`).

This is a guard: every package name below must be declared in
`[project.dependencies]` (not `[project.optional-dependencies].dev`
and not only a transitive pull-in).
"""

from __future__ import annotations

import re
from pathlib import Path

import tomllib


def _project_root() -> Path:
    # tests/ → importer_publikacji/ → src/ → repo root
    return Path(__file__).resolve().parents[3]


def _runtime_requirement_names() -> set[str]:
    pyproject = _project_root() / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    names: set[str] = set()
    # PEP 508 requirement → canonical lowercase project name; strip
    # extras, markers and version specifiers. Examples:
    #   'Django>=5.2,<5.3' → 'django'
    #   'channels[daphne]>=4,<5' → 'channels'
    #   'twisted[http2,tls]>=24.3.0' → 'twisted'
    pattern = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
    for requirement in data["project"]["dependencies"]:
        match = pattern.match(requirement)
        if match:
            names.add(match.group(1).lower().replace("_", "-"))
    return names


def test_bs4_is_runtime_dep():
    """Regression: bs4 must be runtime (not dev)."""
    assert "beautifulsoup4" in _runtime_requirement_names(), (
        "beautifulsoup4 must be in [project.dependencies] because "
        "importer_publikacji.providers.www imports it at app-ready time; "
        "a dev-only pin leaves production images broken on startup."
    )


def test_providers_www_module_imports():
    """Sanity: the module that needs bs4 at import time actually imports."""
    # noqa: F401 — we only care about the import side effect.
    from importer_publikacji.providers import www  # noqa: F401
